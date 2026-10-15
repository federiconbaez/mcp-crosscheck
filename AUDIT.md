# AUDIT.md - how a third party verifies mcp-crosscheck, step by step

Needs only `python3` (>= 3.10; built and tested on 3.13.5) and, optionally, `git`, `sha256sum`, `openssl`. Everything runs offline.
`mcp-crosscheck` verifies *other* projects, so it needs the four sibling projects (`mcp-base`, `mcp-memory-first`,
`mcp-auth-hardened`, `mcp-resource-heavy`) in the same parent directory - e.g. extract the master bundle and work inside it.

**What this kit can and cannot show.** It shows that, on your machine, four independently launched server processes give the same
answers to the same inputs, that each server passes a shared black-box battery, and that tokens are accepted or rejected across
servers exactly as the configuration says. It is **not** independent certification: the battery was written by the same author as
the servers, and the servers share an ancestor (`mcp-forge`). The strongest independent check you can add is a third-party MCP client
or your own raw JSON-RPC client; the author has not done that.

## Step 0 - integrity

```bash
sha256sum -c mcp-crosscheck.tar.gz.sha256     # or: sha256sum -c MANIFEST.sha256 at the family level of the master bundle
tar xzf mcp-crosscheck.tar.gz && cd mcp-crosscheck
python3 tools/make_manifest.py --check
python3 tools/check_doc_refs.py               # every file/test/check named in the docs exists
```

## Step 1 - stdlib only

```bash
python3 tools/check_stdlib_only.py            # AST only; fails on third-party imports, exec/eval/__import__/importlib, dependency manifests
```

## Step 2 - unit and integration tests ({TESTS})

```bash
python3 -m unittest discover -v
```

`tests/test_wire.py` tests the framing layer against a fake stdio server and a fake HTTP server (so the harness is itself tested
without any family member). `tests/test_integration.py` runs the whole battery / differential / matrix against the real family and
two *broken copies* (an unchecked signature, a wrong error code) that must be caught.

## Step 3 - the cross-validation run itself

```bash
python3 -m mcpcross run --out /tmp/xc-evidence ; echo "exit=$?"     # 0 = PASS
less /tmp/xc-evidence/crosscheck.md
python3 - <<'PY'
import json; r = json.load(open("/tmp/xc-evidence/crosscheck.json"))
print("ok:", r["ok"], "| battery summary:", json.dumps(r["battery"]["summary"]))
print("differential:", r["differential"]["summary"]["cases"], "cases, disagreements:", len(r["differential"]["summary"]["disagreements"]))
print("cross-token:", {l["layer"]: l["ok"] for l in r["crosstoken"]["layers"]})
PY
```

Expected: `battery` has `fail: 0, error: 0` for each of 8 (server, transport) pairs (a few `skip`s are listed with reasons -
`XC-CAP-03` is skipped where `listChanged` is not advertised); `differential` 0 disagreements; all four layers PASS.

## Step 4 - read the oracle, not the verdict

The expected values live in plain sight. Do not trust "PASS"; read these and decide whether you agree with them:

* `mcpcross/battery.py` - every `@check("XC-...", title, spec-clause)` states the clause it relies on (JSON-RPC 2.0, MCP 2024-11-05 /
  2025-03-26 / 2025-06-18, RFC 6750/7519 for tokens). List them with `python3 -m mcpcross list`.
* `mcpcross/differential.py` - the table `CASES` (65 inputs). The comparison key is exact: HTTP status + JSON-RPC outcome, including
  whether the error `id` is `null`, whether a batch answered with an array, and whether the server stayed silent.
* `mcpcross/crosstoken.py` - `expected_accept()` and the docstring define what each layer must produce.

## Step 5 - is the crosscheck itself vacuous? (negative controls)

```bash
./demo.sh                                  # steps 8-9: deliberately broken COPIES of mcp-base must make `mcpcross run` exit 1
python3 tools/mutation_sanity.py           # 10 injected bugs in temp copies of the servers; every one must be KILLED (exit 1)
```

Only temp copies are modified. If a mutant ever shows `SURVIVED`, the crosscheck has a blind spot there (see "Limits").

## Step 6 - by hand, without our harness (spot checks)

```bash
cd ../mcp-base
export MCP_FORGE_SECRET=0123456789abcdef0123456789abcdef MCP_FORGE_HOME=$(mktemp -d)
export MCP_TOKEN=$(python3 -m mcpforge mint-token --issuer https://crosscheck.test)
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"x","version":"1"}}}' \
  | python3 -m mcpforge serve --issuer https://crosscheck.test | head -c 300; echo
# a token minted by another family member with the same secret but ITS audience must be rejected:
cd ../mcp-memory-first && OTHER=$(python3 -m mcpmem mint-token --issuer https://crosscheck.test) && cd ../mcp-base
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"x","version":"1"}}}' \
  | MCP_TOKEN=$OTHER python3 -m mcpforge serve --issuer https://crosscheck.test | head -c 300; echo   # expect -32001 "wrong audience"
```

(Both servers read the same `MCP_FORGE_SECRET`, which is exactly the L2 configuration.)

## Requirement -> evidence map

| Requirement | Implemented in | Verified by |
|---|---|---|
| Launch all four servers over stdio and HTTP | `mcpcross/launch.py`, `mcpcross/wire.py` | `tests/test_wire.py::StdioWireTests`, `tests/test_wire.py::HttpWireTests`, `tests/test_integration.py::FullFamily` |
| Freshly written shared black-box battery | `mcpcross/battery.py` (57 checks) | `tests/test_registry.py::RegistryTests`, `tests/test_integration.py::FullFamily::test_battery_has_no_failures_on_any_target_or_transport` |
| Same malformed input -> same JSON-RPC error code | `mcpcross/differential.py` (`CASES`, `outcome`) | `tests/test_logic.py::OutcomeTests`, `tests/test_integration.py::FullFamily::test_differential_all_servers_agree_and_capabilities_match_behaviour` |
| Differential is not vacuous | `mcpcross/differential.py` | `tests/test_integration.py::FullFamily::test_differential_is_not_vacuous_it_sees_many_distinct_outcomes`, demo step 4 |
| Capability advertisement vs behaviour | `mcpcross/differential.py` (`capability_table`), `check:XC-CAP-01`, `check:XC-CAP-02`, `check:XC-CAP-04`, `check:XC-CAP-05` | `tests/test_integration.py::FullFamily`, demo step 5 |
| Different secret -> rejected (L1) | `mcpcross/crosstoken.py` | `tests/test_integration.py::FullFamily::test_cross_token_matrix`, `tests/test_integration.py::BrokenServersAreDetected::test_unchecked_signature_is_caught_by_cross_token_l1` |
| Same secret / different audience -> rejected (L2, L2b) | `mcpcross/crosstoken.py`, `check:XC-AUT-05` | `tests/test_integration.py::FullFamily::test_cross_token_matrix`, demo step 6 |
| Configured same secret + audience (+ `--allow-kidless`) -> accepted and usable (L3) | `mcpcross/crosstoken.py` | `tests/test_logic.py::CrossTokenLogic`, demo step 7 |
| JSON + markdown matrix report | `mcpcross/report.py` | `tests/test_logic.py::ReportTests`, `tests/test_cli.py::CliTests::test_quick_run_writes_reports` |
| Broken servers are detected | `tools/mutation_sanity.py`, `demo.py` | `tests/test_integration.py::BrokenServersAreDetected`, `evidence/mutation_report.txt` |
| Stdlib only, no dynamic imports | whole repo | `tools/check_stdlib_only.py`, `evidence/stdlib_check.txt` |
| Docs do not rot | `tools/check_doc_refs.py` | `evidence/doc_refs.txt` |
| Auth: expired / flipped signature / alg=none / wrong audience / wrong issuer / scope | `check:XC-AUT-01`, `check:XC-AUT-02`, `check:XC-AUT-03`, `check:XC-AUT-04`, `check:XC-AUT-05`, `check:XC-AUT-06`, `check:XC-AUT-07` | `evidence/crosscheck.md` section 1 |
| HTTP: Origin, Content-Type, session, size, protocol header | `check:XC-HTP-01`, `check:XC-HTP-02`, `check:XC-HTP-03`, `check:XC-HTP-05`, `check:XC-HTP-06` | `evidence/crosscheck.md` section 1 |

## Formal-verification hooks

* **Runtime contracts:** the servers keep their own contract registry (checked in their own repos). The crosscheck adds *external* contracts: `XC-CAP-*`
  (capability honesty) and the differential equality.
* **Bounded model check:** the cross-token matrix is an exhaustive enumeration of the 4 x 4 pair space per layer and transport (not a sample).
* **Hash-chained evidence:** `MANIFEST.sha256` (file hashes) and the source manifest embedded in `ORIGINALITY.md`; `evidence/crosscheck.json`
  records the git commit of each server under test.
* **Evidence generators:** `tools/build_evidence.sh` regenerates every file in `evidence/` from scratch.

## Limits (read before trusting)

* Same author for servers, battery and expectations; the four servers share code lineage (see each project's `evidence/adaptation_report.txt`).
  Agreement among them is expected and proves they did not diverge, not that they are right.
* No third-party MCP client or server was involved.
* Differential cases are mostly state-independent edge inputs; stateful divergences (e.g. long sessions, crash recovery) are covered by
  each project's own suite, not here.
* `XC-CAP-03` is skipped where `listChanged` is not advertised (3 of 4 servers); the push path is only exercised on `mcp-resource-heavy`.
* Timing-sensitive checks (concurrency, notification arrival) use fixed timeouts; on a heavily loaded machine a harness timeout may
  surface as `error`. During development one cross-token run failed once while two heavy evidence builds ran in parallel; it
  did not reproduce in 40+ idle repeats (see ORIGINALITY.md "bugs found").
* Tokens are minted with each server's own CLI; the crosscheck does not independently implement HS256 signing (it only mutates tokens: bit flip, `alg=none`).
