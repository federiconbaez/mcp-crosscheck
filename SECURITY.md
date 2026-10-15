# SECURITY.md - mcp-crosscheck

`mcp-crosscheck` is a test tool, not a service. It listens on nothing itself; it starts the family servers it tests on `127.0.0.1`
(ephemeral ports) and stdio pipes, in throw-away temp directories that it deletes afterwards.

## What it does that you should know about

* Spawns processes (`python3 -m mcpforge|mcpmem|mcpauth|mcpres ...`) from the sibling project directories with `PYTHONPATH` set to that project.
  It never uses `shell=True`, `exec`, `eval` or dynamic imports (enforced by `tools/check_stdlib_only.py`).
* Generates **random** HS256 secrets per run (`secrets.token_hex`) and passes them to the servers by environment variable; secrets and
  tokens are never written to the evidence files (the JSON report stores outcomes, codes and server error messages only; token
  *claims* are not stored either).
* The HTTP servers bind loopback only; other local users on a multi-user machine could connect to those ephemeral ports during a run
  but would need a valid token (the servers' own auth), and the data dirs are mode-default temp dirs (`tempfile.mkdtemp`, 0700).
* Negative tests send hostile inputs (oversized bodies, invalid UTF-8, forged/`alg=none` tokens, foreign `Origin`) **to the local test
  servers only**. `tools/mutation_sanity.py` and `demo.py` copy servers to temp dirs and patch the **copies**; the originals are never modified.

## Not covered / weaknesses

* It is not a security scanner: it does not test timing side channels, TLS, resource exhaustion beyond one 1 MiB body, or concurrency
  beyond 8 clients.
* It trusts the servers' own CLIs to mint tokens; a bug common to all four `mint-token` implementations would not be detected by the
  matrix (the tokens would still be mutually consistent). The bit-flip / `alg=none` / expired / wrong-audience / wrong-issuer checks
  are built independently from `mcpcross/jwtkit.py`, but they start from a server-minted token.
* The four servers share an ancestor; common-mode defects (the same bug in all four) are invisible to *differential* testing by construction.
  The shared battery is the only defence against those, and it was written by the same author.
* Evidence is not signed; `MANIFEST.sha256` detects accidental change, not a capable attacker.
