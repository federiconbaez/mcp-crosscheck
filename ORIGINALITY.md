# ORIGINALITY.md - provenance of mcp-crosscheck (and what the evidence cannot prove)

## What was done

* Written by an AI assistant (Grok Bot) for Federico N. Báez Rizzo, in the working session recorded in the git history below.
* **Written fresh in this repository:** all of `mcpcross/` (wire framing, launcher, client, battery, differential, cross-token engine,
  report, CLI), all of `tests/`, `demo.py`, `tools/mutation_sanity.py`, `tools/build_evidence.sh`. Unlike the four servers, this
  project does **not** start from a copy of `mcp-forge`.
* **Adapted from the user's mcp-forge / earlier family tooling (stated plainly):** the *ideas* of the black-box harness (spawn a server, talk raw
  JSON-RPC over stdio / HTTP) and the four generic tools copied from the family: `tools/check_stdlib_only.py`,
  `tools/make_manifest.py`, `tools/gen_originality.py`, `tools/check_doc_refs.py` (only project-name strings changed). The battery's
  check bodies were **not** copied from the servers' own conformance modules; they were written anew against the specs (the server
  suites were consulted only to avoid duplicating *bugs*, not code). There is no `adaptation_report` for this repo because there is no
  shared package to diff; compare `mcpcross/battery.py` with `mcp-base/mcpforge/conformance.py` yourself if this matters to you.
* No code was copied from any MCP SDK or other public implementation, no package was installed, and no web search/fetch was performed
  for this project. Protocol facts come from the author's prior knowledge of JSON-RPC 2.0, MCP 2024-11-05 / 2025-03-26 / 2025-06-18 and
  RFC 6750/7519. Overlap with other implementations in method names, field names and error codes is dictated by those specs.
* Dependencies: **zero** (standard library only).

## What the evidence below can and cannot show

| Evidence | Shows | Does NOT show |
|---|---|---|
| `tools/check_stdlib_only.py` (AST) | no third-party import, no `exec/eval/__import__/importlib`, no dependency manifest | that algorithms are dissimilar to anyone else's |
| SDK-identifier scan | no `modelcontextprotocol`/`fastmcp`/`from mcp` in source | the same |
| git history | incremental construction, bug fixes found by the tests | immutability (unsigned history) |
| Source sha256 manifest + `MANIFEST.sha256` | the files are byte-identical to what was verified | authorship |
| Mutation check (`evidence/mutation_report.txt`) | crosscheck notices each of the injected server bugs | that it notices every bug |

**The evidence cannot prove dissimilarity to code you have not shown me.** Only a similarity tool run by a third party against the
corpus you care about (MOSS, JPlag, Simian ...) can say something about that; the author has not run one and claims no negative
result. The claim is limited to *provenance*: new code written in this session plus four small generic tools from the user's own
family; no third-party code imported, vendored or knowingly reproduced.

## Bugs found while building and testing (real, fixed)

* **In the harness**
  * `XC-RPC-10`: assumed one error object for a rejected batch; the servers answer with an *array* holding the error. The check now accepts both (both are valid JSON-RPC).
  * `XC-AUT-07` (HTTP): assumed HTTP 403 for a missing scope; the servers answer HTTP 200 + JSON-RPC `-32003`. Check corrected to the JSON-RPC contract.
  * `XC-HTP-03`: used `ping` to test "session id required", but `ping` is legitimately exempt; now uses `tools/list`.
  * `XC-HTP-05`: server rightly closes the socket after sending 413 while the client is still uploading; the client now reads the answer after a broken pipe (and `tests/test_wire.py::HttpWireTests::test_big_body_413_is_read_even_if_server_hangs_up_early` pins it).
  * `XC-CAP-03` (stdio): notifications are delivered before the sentinel answer, so they were read from the wrong buffer.
  * HTTP 401/403 bodies are OAuth-style (`{"error": "invalid_token"}`, a *string*), not JSON-RPC; `Reply.error` crashed on them. Added `Reply.reason`.
  * Cross-token **L1 did not isolate the signature**: with per-server audiences, an unchecked-signature mutant of `mcp-base` was still rejected for "wrong audience" (found by `tests/test_integration.py::BrokenServersAreDetected`). L1 now uses one shared audience and `--allow-kidless`, so only the signature can be the reason.
  * **Blind spot found by the mutation check:** mutant C6 (`mcp-auth-hardened` accepting kid-less tokens without `--allow-kidless`) first SURVIVED, because in L2 a foreign token is refused for its audience anyway. Added layer **L3s** (shared audience, auth strict), which must refuse exactly the foreign tokens, for the reason `kid`; C6 is now killed.
  * `StdioConn.close` leaked pipes (ResourceWarning); fixed and the suite runs with `-W error::ResourceWarning`.
* **In the servers** (the crosscheck found no behavioural defect in the four servers that the project's own suites had missed; the discrepancies above were all harness assumptions).
* **Flake observed once:** a cross-token run reported L1 FAIL while two heavy evidence builds were running in parallel on the same machine; it did not reproduce in 30+ repeats on an idle machine and I did not find the cause. Treat timing-related `error` results on loaded machines as harness flakiness, not as server verdicts. (Not proven to be load; stated as a hypothesis.)

## Disclosure

Produced by an AI assistant. "Originality" means provenance and absence of third-party code, not novelty of the underlying techniques.

## Mechanical evidence (live at generation time)

<!-- GENERATED:BEGIN -->
<!-- GENERATED:END -->
