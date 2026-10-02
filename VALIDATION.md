# Validation

- Six pytest tests passed: parser ranges and nesting, immutable citations, incremental reuse, deletion/rename handling, symlink exclusion, parse failures, API indexing/search/source, origin and host checks, query escaping, and invalid model citation fallback.
- Browser: demo question returns real source excerpts; View source opens the correct immutable commit and highlights lines 13–19.
- MCP: initialized through stdio, listed all three tools, and successfully called search_code.
- JavaScript syntax check passed.
- Four-case sample retrieval benchmark: mean recall@5 = 0.875. The permission question misses auth.py:require_admin. This is a tiny smoke benchmark, not evidence of general quality.
- Live Claude synthesis was not tested: no API credentials configured. Fallback behavior was tested with a mocked invalid response.
- Tests emit one upstream Starlette warning about its HTTPX test client.

The preview runs at http://127.0.0.1:8765 while the local server remains active. See README.md to restart or configure another repository.
