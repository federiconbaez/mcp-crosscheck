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
  shared package to diff; compare `mcpcross/battery.py` with the conformance module inside the sibling project mcp-base yourself if this matters to you.
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
### AST stdlib-only check (live run, exit code 0)

```
STDLIB-ONLY CHECK (ast-based; nothing was imported or executed)
python 3.13.5, 290 stdlib modules known to this interpreter

file                                 code  total  imports (stdlib/local)
demo.py                               175    210  json,os,shutil,subprocess,sys,tempfile,time
mcpcross/__init__.py                    6      8  
mcpcross/__main__.py                    4      6  sys  | local: .cli
mcpcross/battery.py                   497    651  http,json,threading,time  | local: .,.client
mcpcross/cli.py                        85     97  argparse,json,os,sys,time  | local: .
mcpcross/client.py                     40     49  json  | local: .
mcpcross/crosstoken.py                 96    111  concurrent,secrets  | local: .,.client
mcpcross/differential.py              172    203  concurrent,json  | local: .,.client
mcpcross/jwtkit.py                     33     49  base64,json
mcpcross/launch.py                    107    125  os,secrets,shutil,socket,subprocess,tempfile,time  | local: .
mcpcross/report.py                    163    181  datetime,json,os,platform,subprocess,sys  | local: .
mcpcross/runner.py                     39     44  concurrent,time  | local: .
mcpcross/targets.py                    35     45  os
mcpcross/wire.py                      202    236  http,json,os,queue,signal,subprocess,sys,threading
tests/__init__.py                       0      0  
tests/helpers.py                       27     32  os,sys
tests/test_cli.py                      49     60  contextlib,io,json,os,tempfile,unittest  | local: mcpcross,tests.helpers
tests/test_integration.py              91    107  os,shutil,tempfile,unittest  | local: mcpcross,tests.helpers
tests/test_jwtkit.py                   31     42  json,unittest  | local: mcpcross
tests/test_logic.py                   105    132  json,unittest  | local: mcpcross
tests/test_registry.py                 45     58  re,unittest  | local: mcpcross
tests/test_wire.py                     99    122  http,json,threading,unittest  | local: mcpcross,tests.helpers
tools/check_doc_refs.py                51     59  glob,os,re,sys
tools/check_stdlib_only.py            142    161  argparse,ast,json,os,subprocess,sys
tools/gen_originality.py               72     88  hashlib,os,re,subprocess,sys
tools/make_manifest.py                 60     73  argparse,hashlib,os,sys
tools/mutation_sanity.py               86    101  argparse,os,shutil,subprocess,sys,tempfile,time

files: 27   lines: total=3050 code=2512 comment=30 blank=508
stdlib modules used (25): argparse, ast, base64, concurrent, contextlib, datetime, glob, hashlib, http, io, json, os, platform, queue, re, secrets, shutil, signal, socket, subprocess, sys, tempfile, threading, time, unittest

GIT HISTORY (oldest first):
655be23|Grok Bot (mcp-family build)|2026-10-15T04:00:59Z|mcp-crosscheck: wire/launch/client layers, 57-check black-box battery, differential and cross-token engines, report, CLI, tooling

 19 files changed, 2262 insertions(+)
992d795|Grok Bot (mcp-family build)|2026-10-15T04:06:13Z|crosscheck: tests (wire with fake servers, registry, logic, CLI, integration incl. broken-copy detection), demo, mutation_sanity, evidence builder, README/AUDIT; L1 isolates the signature (found while testing: audience masked an unchecked-signature mutant)

 15 files changed, 986 insertions(+), 6 deletions(-)
118a8c9|Grok Bot (mcp-family build)|2026-10-15T04:09:54Z|crosscheck: layer L3s (strict kid) closes mutant C6 blind spot; reason hints per layer; ORIGINALITY/SECURITY docs

 9 files changed, 139 insertions(+), 11 deletions(-)
a3a47a9|Grok Bot (mcp-family build)|2026-10-15T04:15:35Z|crosscheck: fix reason assertion test for the L3s layer

 3 files changed, 67 insertions(+), 1 deletion(-)

RESULT: PASS - zero third-party imports, no dynamic imports/exec/eval, no dependency manifests
```

### Git history (4 commits at generation time; later commits only touch docs/evidence)

```
655be23  Grok Bot (mcp-family build)  2026-10-15T04:00:59Z  mcp-crosscheck: wire/launch/client layers, 57-check black-box battery, differential and cross-token engines, report, CLI, tooling
992d795  Grok Bot (mcp-family build)  2026-10-15T04:06:13Z  crosscheck: tests (wire with fake servers, registry, logic, CLI, integration incl. broken-copy detection), demo, mutation_sanity, evidence builder, README/AUDIT; L1 isolates the signature (found while testing: audience masked an unchecked-signature mutant)
118a8c9  Grok Bot (mcp-family build)  2026-10-15T04:09:54Z  crosscheck: layer L3s (strict kid) closes mutant C6 blind spot; reason hints per layer; ORIGINALITY/SECURITY docs
a3a47a9  Grok Bot (mcp-family build)  2026-10-15T04:15:35Z  crosscheck: fix reason assertion test for the L3s layer
```

### SDK-identifier scan of source files (`modelcontextprotocol|fastmcp|from mcp|import mcp`)

```
tools/gen_originality.py:51: parts.append("### Lines inherited from mcp-base / mcp-forge, per file (`evidence/adaptation_report.t
tools/gen_originality.py:55: pat = re.compile(r"modelcontextprotocol|fastmcp|from mcp\b|import mcp\b", re.I)
tools/gen_originality.py:61: parts.append("### SDK-identifier scan of source files (`modelcontextprotocol|fastmcp|from mcp|import
```

### Source sha256 manifest (29 files, 3076 lines incl. blanks/comments/tests)

```
85ecf887b6dc4c4a649f88f6c963b7c115a8e2c7bfcf4ae07ab9f0570cbba317  demo.py
447c7b78db09b144881a389d8e0b2ec5fac5686af1384825bc95089606f6c980  demo.sh
d899bfa9fc2810e3ad65fe3e979ab98defd89d130dd64924d5b29044499d8e2f  mcpcross/__init__.py
e0930aeba5a3e2e2d94ca6c5fac4f72c0c4eb2be9bba283becf98e909091471c  mcpcross/__main__.py
f8be35049f4ee66d187ff7d174a45385c745b66b6d26a49958b58cebd89a6910  mcpcross/battery.py
7199b9e57f45652739efe778e54ec2fb4ce9232c61c6078df20aed37efca993c  mcpcross/cli.py
d904867bd6b46e800fec7888125854914725dd80a275e3e26efbc7f2f1892056  mcpcross/client.py
8898c8b58349f7323c05f73b89ed292242c46aacace4e1f1f31fc8e308c5d858  mcpcross/crosstoken.py
d6b29f815ef01899a035c5d0a12e450cdd0d8e63f92ab2b44d7d00bf3d04c43d  mcpcross/differential.py
7224b6e9a11abf3889360e6720a383e44df16af70999cbd36f65f13c4b9cb992  mcpcross/jwtkit.py
1b35337d79bb7917c8dafda78a583462800ee0a74ba2645e277f63ace91f3d48  mcpcross/launch.py
de641656841bdf6b560e6787207df6950c34255d42e23e37957398ffcf11d1e9  mcpcross/report.py
ec25199d663995ae833902513bbc54c274c44e660d9076a136273ceede4a7059  mcpcross/runner.py
3daf6cf11a9527e8a4ecddd92314ac3b331da69ba4af8a5f7c5e7bde8ae5b922  mcpcross/targets.py
84f482b2fcc8e94f32feb0da2fc1d906e8f765f1ff7f0aa855d08986cac79bbc  mcpcross/wire.py
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  tests/__init__.py
9f5dd2725f1c4cc56e08e7c3e23b8a72132560888a78d1b292196f9ddf47959e  tests/helpers.py
cbc47b10ae9f7580e002b09356ac06cf4c205f4ff95edd2a6ffe14d03984c782  tests/test_cli.py
92b709b9207e51280a6b99a7a97f8c45e8e99e9f53a09ef7deccdd5aa863a49b  tests/test_integration.py
5ebd13c85311de3de2cccf92b43f3bb2c083ffdd871d13cc6a6cae5f468e22bb  tests/test_jwtkit.py
01153644a4de86e0583b0b86c4e9752289e36e5510709f5c1542f926250d6275  tests/test_logic.py
464e910922dfd4bebe244c1b130c091a001dfb3ea2668c6981a37cd4b54171d5  tests/test_registry.py
10a3b886885f18af09dba1c0948a3ba5c5e2eb11c5fd857dff5d4f66fc11332f  tests/test_wire.py
acb8c3f00c86a57796220aab4378e613d6279cbf1474e33e2f5f3061c7b8e2a6  tools/build_evidence.sh
c00b7a38dc696ad205f7562a7060b18be6223fde2c3244bdfaa53a9032a92a02  tools/check_doc_refs.py
d6024858f0d46fcadd6b03c025b38b616b9fa42c26073327b264e237139a6bb5  tools/check_stdlib_only.py
65074c2678b2e041b9cc1e426dcb0549c95b4e42cca1c43b198b40f8efd2fc7d  tools/gen_originality.py
a9b50367b658589ba3106e65ebac584a13600d89b299464bc9d8d7dc99fc9f21  tools/make_manifest.py
1f77645bf865d8cb9b2ae677396af0c6c50a6f2d329423781a5b89f759b34ecc  tools/mutation_sanity.py
```

<!-- GENERATED:END -->
