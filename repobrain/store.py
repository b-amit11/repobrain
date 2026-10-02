import json
from contextlib import contextmanager
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import threading
import time
from urllib.parse import quote

from .parser import parse, terms

STOP = set("a an the how does do is are in this that repo repository work works what where who when to of for and with me explain please".split())
INDEX_LOCK = threading.Lock()


def git(path, *args):
    result = subprocess.run(["git", "-C", str(path), *args], capture_output=True, timeout=30)
    if result.returncode:
        raise ValueError("Git could not read this checkout. Choose a repository with at least one commit.")
    return result.stdout


def remote_url(path):
    try:
        remote = git(path, "remote", "get-url", "origin").decode().strip()
    except ValueError:
        return None
    match = re.fullmatch(r"(?:https://github\.com/|git@github\.com:)([\w.-]+/[\w.-]+?)(?:\.git)?", remote)
    return "https://github.com/" + match[1] if match else None


class Store:
    def __init__(self, location):
        self.location = Path(location)
        self.location.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS repositories (
                    id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
                    remote TEXT, snapshot INTEGER);
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY, repo INTEGER NOT NULL, sha TEXT NOT NULL,
                    created REAL NOT NULL, files INTEGER NOT NULL, parsed INTEGER NOT NULL,
                    reused INTEGER NOT NULL, warnings TEXT NOT NULL, UNIQUE(repo,sha));
                CREATE TABLE IF NOT EXISTS files (
                    snapshot INTEGER, path TEXT, blob TEXT, content TEXT,
                    PRIMARY KEY(snapshot,path));
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY, snapshot INTEGER, path TEXT, symbol TEXT,
                    kind TEXT, start INTEGER, end INTEGER, content TEXT, calls TEXT);
                CREATE INDEX IF NOT EXISTS chunk_snapshot ON chunks(snapshot);
                CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(
                    symbol, path, content, snapshot UNINDEXED,
                    tokenize='porter unicode61');
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.location, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def repositories(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("""
                SELECT r.*, s.sha, s.created, s.files, s.parsed, s.reused,
                (SELECT count(*) FROM chunks c WHERE c.snapshot=r.snapshot) AS symbols
                FROM repositories r LEFT JOIN snapshots s ON s.id=r.snapshot ORDER BY r.id
            """)]

    def index(self, path):
        path = Path(path).expanduser().resolve()
        root = Path(git(path, "rev-parse", "--show-toplevel").decode().strip()).resolve()
        sha = git(root, "rev-parse", "HEAD^{commit}").decode().strip()
        with INDEX_LOCK, self.connect() as db:
            db.execute("INSERT OR IGNORE INTO repositories(path,name,remote) VALUES(?,?,?)", (str(root), root.name, remote_url(root)))
            repo = db.execute("SELECT * FROM repositories WHERE path=?", (str(root),)).fetchone()
            existing = db.execute("SELECT id FROM snapshots WHERE repo=? AND sha=?", (repo["id"], sha)).fetchone()
            if existing:
                db.execute("UPDATE repositories SET snapshot=? WHERE id=?", (existing[0], repo["id"]))
                return {"repo_id": repo["id"], "snapshot": existing[0], "sha": sha, "unchanged": True}
            listing = git(root, "ls-tree", "-rz", sha).split(b"\0")
            candidates = []
            for entry in listing:
                if not entry:
                    continue
                header, filename = entry.split(b"\t", 1)
                mode, kind, blob = header.decode().split()
                name = filename.decode("utf-8", errors="replace")
                if mode not in {"100644", "100755"} or not name.endswith(".py"):
                    continue
                if any(part in {".venv", "venv", "node_modules", "vendor", "__pycache__"} for part in name.split("/")):
                    continue
                candidates.append((name, blob))
            if len(candidates) > 3000:
                raise ValueError("This local MVP supports up to 3,000 Python files per repository.")
            snapshot = db.execute("INSERT INTO snapshots(repo,sha,created,files,parsed,reused,warnings) VALUES(?,?,?,0,0,0,'[]')", (repo["id"], sha, time.time())).lastrowid
            parsed = reused = total_bytes = 0
            warnings = []
            for name, blob in candidates:
                old = db.execute("SELECT * FROM files WHERE snapshot=? AND path=? AND blob=?", (repo["snapshot"], name, blob)).fetchone()
                size = int(git(root, "cat-file", "-s", blob))
                if size > 500_000:
                    warnings.append(f"Skipped oversized file: {name}")
                    continue
                total_bytes += size
                if total_bytes > 25_000_000:
                    raise ValueError("This local MVP supports up to 25 MB of Python source per repository.")
                if old:
                    content = old["content"]
                    chunks = [dict(c) for c in db.execute("SELECT * FROM chunks WHERE snapshot=? AND path=?", (repo["snapshot"], name))]
                    reused += 1
                else:
                    try:
                        content = git(root, "cat-file", "blob", blob).decode("utf-8")
                        chunks = parse(content, name)
                    except (UnicodeDecodeError, ValueError) as exc:
                        warnings.append(f"Skipped {name}: {exc}")
                        continue
                    parsed += 1
                db.execute("INSERT INTO files VALUES(?,?,?,?)", (snapshot, name, blob, content))
                for chunk in chunks:
                    calls = chunk["calls"] if isinstance(chunk["calls"], str) else json.dumps(chunk["calls"])
                    cid = db.execute("INSERT INTO chunks(snapshot,path,symbol,kind,start,end,content,calls) VALUES(?,?,?,?,?,?,?,?)",
                                     (snapshot, name, chunk["symbol"], chunk["kind"], chunk["start"], chunk["end"], chunk["content"], calls)).lastrowid
                    db.execute("INSERT INTO search(rowid,symbol,path,content,snapshot) VALUES(?,?,?,?,?)",
                               (cid, " ".join(terms(chunk["symbol"])), " ".join(terms(name)), " ".join(terms(chunk["content"])), snapshot))
            db.execute("UPDATE snapshots SET files=?,parsed=?,reused=?,warnings=? WHERE id=?", (parsed + reused, parsed, reused, json.dumps(warnings), snapshot))
            db.execute("UPDATE repositories SET snapshot=?,remote=? WHERE id=?", (snapshot, remote_url(root), repo["id"]))
            return {"repo_id": repo["id"], "snapshot": snapshot, "sha": sha, "parsed": parsed, "reused": reused, "warnings": warnings, "unchanged": False}

    def search(self, repo_id, question, limit=6):
        tokens = list(dict.fromkeys(t for t in terms(question) if t not in STOP))[:30]
        with self.connect() as db:
            repo = db.execute("SELECT r.*,s.sha FROM repositories r JOIN snapshots s ON s.id=r.snapshot WHERE r.id=?", (repo_id,)).fetchone()
            if not repo:
                raise ValueError("Repository has not been indexed.")
            if not tokens:
                return []
            query = " OR ".join('"' + token + '"' for token in tokens)
            rows = db.execute("""SELECT c.*, bm25(search,5,2,1) AS rank FROM search
                JOIN chunks c ON c.id=search.rowid WHERE search MATCH ? AND c.snapshot=?
                ORDER BY rank,c.id LIMIT ?""", (query, repo["snapshot"], min(max(limit, 1), 20))).fetchall()
            results = []
            for row in rows:
                item = dict(row)
                item["calls"] = json.loads(item["calls"])
                item["sha"] = repo["sha"]
                item["url"] = f'{repo["remote"]}/blob/{repo["sha"]}/{quote(item["path"], safe="/")}#L{item["start"]}-L{item["end"]}' if repo["remote"] else None
                results.append(item)
            return results

    def source(self, chunk_id):
        with self.connect() as db:
            row = db.execute("""SELECT c.*, f.content AS source, s.sha FROM chunks c
                JOIN files f ON f.snapshot=c.snapshot AND f.path=c.path
                JOIN snapshots s ON s.id=c.snapshot WHERE c.id=?""", (chunk_id,)).fetchone()
            if row is None:
                raise ValueError("Source not found.")
            return dict(row)


def default_store():
    return Store(Path(os.environ.get("REPOBRAIN_DATA", ".repobrain")) / "index.sqlite3")
