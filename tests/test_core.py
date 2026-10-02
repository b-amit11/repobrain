import json
from pathlib import Path
import subprocess
import time

from fastapi.testclient import TestClient
import pytest

from repobrain.app import create_app
from repobrain.answers import answer
from repobrain.parser import parse
from repobrain.store import Store


def run(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True).stdout.decode().strip()


def commit(repo):
    run(repo, 'add', '.')
    run(repo, '-c', 'user.name=Test', '-c', 'user.email=test@localhost', 'commit', '-m', 'snapshot')


@pytest.fixture
def setup(tmp_path):
    repo = tmp_path / 'checkout'
    repo.mkdir()
    run(repo, 'init')
    (repo / 'auth.py').write_text('def authenticate(api_key):\n    """Validate API key authentication."""\n    return api_key == "example"\n')
    (repo / 'orders.py').write_text('from auth import authenticate\n\ndef create_order(key):\n    return authenticate(key)\n')
    commit(repo)
    return repo, Store(tmp_path / 'data' / 'index.db')


def test_parser_decorators_nested_unicode():
    code = '# café\n@decorator\ndef outer():\n    def inner():\n        target()\n    return inner()\n'
    chunks = parse(code, 'test.py')
    outer = next(c for c in chunks if c['symbol'] == 'outer')
    inner = next(c for c in chunks if c['symbol'] == 'outer.inner')
    assert outer['start'] == 2 and outer['end'] == 6
    assert outer['calls'] == ['inner']
    assert inner['calls'] == ['target']
    assert outer['content'] == '\n'.join(code.splitlines()[1:6])


def test_immutable_incremental_deletions_and_renames(setup):
    repo, store = setup
    first = store.index(repo)
    hits = store.search(first['repo_id'], 'API key authentication')
    citation = next(h for h in hits if h['symbol'] == 'authenticate')
    assert first['parsed'] == 2
    assert citation['sha'] == run(repo, 'rev-parse', 'HEAD')
    (repo / 'auth.py').write_text('def replaced():\n    return 42\n')
    # Working tree edits must not affect indexed HEAD or a pinned citation.
    assert store.index(repo)['unchanged']
    assert 'api_key' in store.source(citation['id'])['source']
    commit(repo)
    second = store.index(repo)
    assert second['parsed'] == 1 and second['reused'] == 1
    assert all(h['symbol'] != 'authenticate' for h in store.search(first['repo_id'], 'authentication'))
    assert 'api_key' in store.source(citation['id'])['source']
    (repo / 'auth.py').unlink()
    (repo / 'orders.py').rename(repo / 'checkout.py')
    commit(repo)
    store.index(repo)
    assert {h['path'] for h in store.search(first['repo_id'], 'authenticate')} == {'checkout.py'}
    run(repo, 'checkout', first['sha'])
    store.index(repo)
    assert store.repositories()[0]['sha'] == first['sha']


def test_symlinks_and_invalid_python_skipped(setup):
    repo, store = setup
    (repo / 'link.py').symlink_to('/etc/passwd')
    (repo / 'broken.py').write_text('def broken(:\n')
    commit(repo)
    result = store.index(repo)
    assert len(result['warnings']) == 1
    assert store.repositories()[0]['files'] == 2


def test_api_index_search_source_and_origin_guard(setup, monkeypatch):
    repo, store = setup
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    with TestClient(create_app(store)) as client:
        assert client.get('/').status_code == 200
        assert client.post('/api/index', json={'path':str(repo)}, headers={'origin':'https://evil.example'}).status_code == 403
        assert client.get('/api/repos', headers={'host':'evil.example'}).status_code == 400
        response = client.post('/api/index', json={'path':str(repo)})
        assert response.status_code == 202
        for _ in range(100):
            job = client.get('/api/jobs/' + response.json()['job_id']).json()
            if job['status'] not in ('queued', 'running'):
                break
            time.sleep(.02)
        assert job['status'] == 'completed'
        result = client.post('/api/ask', json={'repo_id':job['result']['repo_id'], 'question':'API key authentication'}).json()
        assert result['mode'] == 'evidence'
        assert result['evidence']
        assert client.get('/api/source/' + str(result['evidence'][0]['id'])).status_code == 200
        assert client.post('/api/ask', json={'repo_id':999, 'question':'authentication'}).status_code == 404
        assert client.post('/api/ask', json={'repo_id':1, 'question':''}).status_code == 422


def test_empty_and_query_escaping(setup):
    repo, store = setup
    rid = store.index(repo)['repo_id']
    assert store.search(rid, 'the and how') == []
    assert store.search(rid, '" OR * : authenticate --')
    assert store.search(rid, 'nonexistentunicorn') == []


def test_invalid_model_citations_fall_back(setup, monkeypatch):
    repo, store = setup
    rid = store.index(repo)['repo_id']
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test')
    monkeypatch.setenv('REPOBRAIN_MODEL', 'test-model')
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'content':[{'type':'text','text':'Unsupported claim [99]'}]}
    monkeypatch.setattr('repobrain.answers.httpx.post', lambda *a, **kw: Response())
    result = answer(store, rid, 'API key authentication')
    assert result['mode'] == 'evidence'
    assert result['warning']
    assert 'Unsupported claim' not in result['answer']
