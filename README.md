# RepoBrain

[![CI](https://github.com/b-amit11/repobrain/actions/workflows/ci.yml/badge.svg)](https://github.com/b-amit11/repobrain/actions/workflows/ci.yml)

A working local foundation for codebase intelligence: tree-sitter Python parsing, incremental commit snapshots, BM25 search, source citations, optional Claude answers, and a read-only MCP server.

**Stack:** Python · FastAPI · tree-sitter · SQLite FTS5 (BM25) · Model Context Protocol · Claude API · pytest · GitHub Actions

## Run

Requires Python 3.11+ and Git. From this directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,mcp]'
repobrain demo
repobrain serve
```

Open http://127.0.0.1:8765. The sample shop is an actual local Git repository, not canned search results. Ask “How does API key authentication work?” or “Who can cancel an order?”. Use **Index a repository** with an absolute checkout path to explore your own Python project. To use a GitHub repository, clone it with your normal Git credentials first.

```sh
repobrain index /absolute/path/to/checkout
pytest -q
repobrain eval examples/benchmark.json --repo 1
```

`--repo` is the repository ID printed by indexing; a fresh demo database uses 1. The four-case demo benchmark measures retrieval recall@5, not answer correctness or real-world quality. Add independently labeled cases for your repositories before drawing conclusions.

## Optional AI answers

Export `ANTHROPIC_API_KEY` and `REPOBRAIN_MODEL` (an available Claude model ID from your account), then restart the server. The app does not load `.env` files automatically. Never commit credentials.

Without both variables, the app runs in explicitly labeled **evidence mode**. With both, questions and up to six bounded source excerpts are sent to Anthropic. Responses must contain valid citation numbers or the app falls back to evidence. Citation-number validation does not prove that the cited code supports a claim. Provider billing applies; the live provider path needs your credentials to test.

## MCP

Install the `mcp` extra, then configure your MCP client to run:

```json
{
  "mcpServers": {
    "repobrain": {
      "command": "/absolute/path/to/repobrain/.venv/bin/repobrain",
      "args": ["mcp"],
      "env": {"REPOBRAIN_DATA": "/absolute/path/to/repobrain/.repobrain"}
    }
  }
}
```

Tools: `list_repositories`, `search_code`, `read_source`. Use the same absolute data directory for the server and CLI. MCP exposes the existing local index, not arbitrary filesystem reads or code execution.

## Architecture and guarantees

- **FastAPI + static browser UI:** a single process serves the local workspace and JSON API. The frontend is plain JavaScript/CSS to keep this milestone easy to run; no Next.js build is required.
- **tree-sitter:** extracts Python functions, classes, decorated definitions, and module statements with original line ranges. Call references are syntax-derived and unresolved; they are not claimed to be a semantic call graph. Syntax-error files are skipped with visible warnings.
- **Immutable Git snapshots:** reads blobs from a captured HEAD commit, never the working tree. Updates reuse unchanged file parses by blob hash. Renames and deletions produce a new snapshot; old source remains available for existing citations. A transaction changes the active snapshot only after indexing succeeds.
- **SQLite FTS5 / BM25:** tokenizes identifiers including snake_case/camelCase; weights symbols and paths above body text. This is keyword retrieval, not hybrid or vector search. FTS term statistics currently span all snapshots; per-snapshot ranking isolation is future work.
- **Local persistence:** `.repobrain/index.sqlite3`; override with `REPOBRAIN_DATA`. Old snapshots grow storage; automatic retention is not implemented.
- **Background indexing:** single worker, progress polling, capped job history. Jobs are process-local, not durable. Restart and retry interrupted work; the prior completed index remains usable.
- **Bounded ingestion:** committed regular Python files only; skips symlinks, common dependency folders, invalid UTF-8, and files over 500 KB. Limits: 3,000 candidate files / 25 MB per snapshot.
- **Local use only:** server binds to loopback, restricts Host and cross-origin requests, renders source as text, and never executes repository code. It has no user authentication or tenant isolation. Do not put it behind a public reverse proxy.

## Next milestones

1. Broaden the evaluation corpus; measure retrieval recall, citation support, latency, and cost. Compare keyword search against hybrid retrieval before adding infrastructure.
2. GitHub App installation, signed webhook handling, durable and idempotent jobs, installation-scoped credentials, explicit branch/PR snapshot selection.
3. Postgres/pgvector, embeddings, rank fusion, reranking, language-specific symbol resolution, and graph expansion.
4. Review drafts on PR diffs, precision evaluation, deduplicated findings, then authorized inline comments.
5. Next.js frontend as UI complexity grows, multi-tenant auth and repository access enforcement, observability, and deployment.

This milestone does not implement a GitHub App, automatic push ingestion, PR review, vector retrieval, production tenancy, or an eval dashboard. The bundled eval command establishes a small inspectable baseline.

## References

- [tree-sitter Python bindings](https://tree-sitter.github.io/py-tree-sitter/)
- [FastAPI static files](https://fastapi.tiangolo.com/tutorial/static-files/)
- [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Claude API](https://platform.claude.com/docs/en/api/overview)

## License

[MIT](LICENSE)
