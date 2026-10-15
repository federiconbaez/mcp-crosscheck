# mcp-crosscheck report

- tool version: `1.0.0`; generated: 2026-10-15T01:16:29-03:00 (UTC-3 (America/Buenos_Aires)); python 3.13.5
- targets: base, memory, auth, resources; transports: stdio, http
- target commits: auth=611a678, base=85d510f, memory=e443446, resources=9c5781c
- **overall verdict: PASS**

## 1. Shared black-box battery (57 checks registered)

| target | transport | pass | fail | error | skip |
|---|---|---:|---:|---:|---:|
| base | stdio | 47 | 0 | 0 | 1 |
| base | http | 53 | 0 | 0 | 1 |
| memory | stdio | 47 | 0 | 0 | 1 |
| memory | http | 53 | 0 | 0 | 1 |
| auth | stdio | 47 | 0 | 0 | 1 |
| auth | http | 53 | 0 | 0 | 1 |
| resources | stdio | 48 | 0 | 0 | 0 |
| resources | http | 54 | 0 | 0 | 0 |

Legend: ✔ pass, ✘ fail, ! harness error, – skipped (precondition absent, reason in the JSON).

| check | title | base/s | base/h | memo/s | memo/h | auth/s | auth/h | reso/s | reso/h |
|---|---|---|---|---|---|---|---|---|---|
| XC-AUT-01 | no token -> rejected (stdio -32001 / http 401 + WWW-Authenticate: Bearer) | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-AUT-02 | expired token (1 h ago, beyond any leeway) -> rejected | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-AUT-03 | signature with one flipped bit -> rejected | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-AUT-04 | alg=none and garbage tokens -> rejected | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-AUT-05 | valid signature but wrong audience -> rejected | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-AUT-06 | valid signature but wrong issuer -> rejected | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-AUT-07 | token with only the base scope cannot call tools (-32003 / HTTP 403) | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-AUT-08 | a token's scopes do not leak between sessions (read-only vs full side by side) | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-CAP-01 | advertised capability <=> its methods work; unadvertised -> -32601 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-CAP-02 | resources.subscribe true => subscribe/unsubscribe work and validate; false => -32601 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-CAP-03 | resources.listChanged true => a real list_changed push follows a change (stdio) / GET stream exists (http) | – | – | – | – | – | – | ✔ | ✔ |
| XC-CAP-04 | completions advertised => completion/complete works on a listed prompt; unadvertised => -32601 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-CAP-05 | list_changed flags for tools/prompts are honest (false => the lists do not change) | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-CON-01 | 8 concurrent clients x 4 store/recall rounds: no errors, nothing lost | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-HTP-01 | foreign Origin header -> 403 |   | ✔ |   | ✔ |   | ✔ |   | ✔ |
| XC-HTP-02 | non-JSON Content-Type -> 415 |   | ✔ |   | ✔ |   | ✔ |   | ✔ |
| XC-HTP-03 | Mcp-Session-Id: issued, required later, unknown -> 404, DELETE ends the session |   | ✔ |   | ✔ |   | ✔ |   | ✔ |
| XC-HTP-04 | session is bound to the token subject: another subject cannot reuse the session id |   | ✔ |   | ✔ |   | ✔ |   | ✔ |
| XC-HTP-05 | oversized body (> 1 MiB) -> 413 |   | ✔ |   | ✔ |   | ✔ |   | ✔ |
| XC-HTP-06 | unsupported MCP-Protocol-Version header -> 400 |   | ✔ |   | ✔ |   | ✔ |   | ✔ |
| XC-HTP-07 | parse error over HTTP -> 400 with a JSON-RPC error body |   | ✔ |   | ✔ |   | ✔ |   | ✔ |
| XC-HTP-08 | GET /mcp without an event-stream Accept is refused (405/406); unknown paths -> 404 |   | ✔ |   | ✔ |   | ✔ |   | ✔ |
| XC-HTP-09 | batch over HTTP returns a JSON array with application/json |   | ✔ |   | ✔ |   | ✔ |   | ✔ |
| XC-LIF-01 | initialize result has protocolVersion, capabilities and serverInfo{name,version} | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-LIF-02 | each of 2024-11-05, 2025-03-26, 2025-06-18 is negotiated as requested | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-LIF-03 | unknown protocolVersion -> success with a version the server supports | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-LIF-04 | request before initialize is refused with -32600 (no result) | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-LIF-05 | ping answers {} both before and after initialize | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-LIF-06 | notifications/initialized and unknown notifications produce no response | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-LIF-07 | initialize with missing/invalid params -> -32602 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-PER-01 | a stored memory survives a server restart | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-PRM-01 | prompts/list shape; prompts/get unknown -> -32602 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-PRM-02 | a prompt with required arguments rejects a call without them (-32602) | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-RES-01 | resources/list and resources/templates/list have the specified shape (all pages) | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-RES-02 | resources/read of listed resources returns contents with exactly one of text/blob | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-RES-03 | unknown resource -> -32002; missing uri -> -32602 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-RPC-01 | malformed JSON -> -32700 with id null | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-RPC-02 | structurally invalid request -> -32600 with id null | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-RPC-03 | unknown method after initialize -> -32601 with the id echoed | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-RPC-04 | ids are echoed verbatim: string, 0, and a large integer | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-RPC-05 | invalid id types (bool, float, object) -> -32600 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-RPC-06 | params of the wrong JSON type -> -32602 or -32600, never a result | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-RPC-07 | empty batch -> one -32600 object | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-RPC-08 | batch [ping, ping] on 2025-03-26 -> array of two results with ids | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-RPC-09 | batch of notifications only -> no response | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-RPC-10 | batches are rejected (-32600) once 2025-06-18 is negotiated | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-RPC-11 | invalid UTF-8 bytes -> -32700 and the server keeps serving | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-STD-01 | CRLF frames and blank lines are tolerated; stdout carries only JSON | ✔ |   | ✔ |   | ✔ |   | ✔ |   |
| XC-STD-02 | line over 1 MiB -> -32600 and the server keeps serving | ✔ |   | ✔ |   | ✔ |   | ✔ |   |
| XC-STD-03 | stdin EOF -> clean exit code 0 | ✔ |   | ✔ |   | ✔ |   | ✔ |   |
| XC-TLS-01 | tools/list: unique names, description string, inputSchema type=object | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-TLS-02 | every tool schema is strict (additionalProperties:false at the top level) | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-TLS-03 | unknown tool -> -32602; missing tool name -> -32602 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-TLS-04 | memory_store -> memory_recall round trip finds exactly the stored note | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-TLS-05 | argument violations are tool errors (isError:true), not protocol errors | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-TLS-06 | structuredContent appears only on a negotiated 2025-06-18 session | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| XC-TLS-07 | tools/list cursor: bogus cursor -> -32602, missing cursor fine | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |

### Skips
- `XC-CAP-03` base/stdio: listChanged not advertised (nothing to verify)
- `XC-CAP-03` base/http: listChanged not advertised (nothing to verify)
- `XC-CAP-03` memory/stdio: listChanged not advertised (nothing to verify)
- `XC-CAP-03` memory/http: listChanged not advertised (nothing to verify)
- `XC-CAP-03` auth/stdio: listChanged not advertised (nothing to verify)
- `XC-CAP-03` auth/http: listChanged not advertised (nothing to verify)

## 2. Differential checks (identical input -> identical JSON-RPC error code)

- 65 malformed-input cases x 2 transports x 4 targets; disagreements: **0**; stdio-vs-http semantic mismatches: **0**; capability/behaviour inconsistencies: **0**

| case | state | stdio | http | agree |
|---|---|---|---|---|
| pre/tools-list | pre | `err-32600` | `400|err-32600` | ✔ |
| pre/resources-list | pre | `err-32600` | `400|err-32600` | ✔ |
| pre/prompts-get | pre | `err-32600` | `400|err-32600` | ✔ |
| pre/tools-call | pre | `err-32600` | `400|err-32600` | ✔ |
| pre/unknown-method | pre | `err-32600` | `400|err-32600` | ✔ |
| pre/ping | pre | `result` | `200|result` | ✔ |
| pre/notification | pre | `silence` | `202|silence` | ✔ |
| frame/truncated-json | post | `err-32700(id:null)` | `400|err-32700(id:null)` | ✔ |
| frame/not-json | post | `err-32700(id:null)` | `400|err-32700(id:null)` | ✔ |
| frame/trailing-garbage | post | `err-32700(id:null)` | `400|err-32700(id:null)` | ✔ |
| frame/nan-constant | post | `err-32700(id:null)` | `400|err-32700(id:null)` | ✔ |
| frame/bare-scalar | post | `err-32600(id:null)` | `400|err-32600(id:null)` | ✔ |
| frame/null | post | `err-32600(id:null)` | `400|err-32600(id:null)` | ✔ |
| frame/string | post | `err-32600(id:null)` | `400|err-32600(id:null)` | ✔ |
| frame/invalid-utf8 | post | `err-32700(id:null)` | `400|err-32700(id:null)` | ✔ |
| frame/deep-nesting | post | `array[err-32600(id:null)]` | `200|array[err-32600(id:null)]` | ✔ |
| frame/empty-object | post | `err-32600(id:null)` | `400|err-32600(id:null)` | ✔ |
| frame/empty-batch | post | `err-32600(id:null)` | `400|err-32600(id:null)` | ✔ |
| frame/batch-of-scalars | post | `array[err-32600(id:null),err-32600(id:null)]` | `200|array[err-32600(id:null),err-32600(id:null)]` | ✔ |
| frame/batch-mixed | post | `array[err-32600(id:null),result]` | `200|array[err-32600(id:null),result]` | ✔ |
| frame/batch-ping | post | `array[result,result]` | `200|array[result,result]` | ✔ |
| frame/batch-notifications | post | `silence` | `202|silence` | ✔ |
| req/no-jsonrpc | post | `err-32600` | `400|err-32600` | ✔ |
| req/jsonrpc-1.0 | post | `err-32600` | `400|err-32600` | ✔ |
| req/jsonrpc-number | post | `err-32600` | `400|err-32600` | ✔ |
| req/method-number | post | `err-32600` | `400|err-32600` | ✔ |
| req/method-missing | post | `err-32600` | `400|err-32600` | ✔ |
| req/id-bool | post | `err-32600(id:null)` | `400|err-32600(id:null)` | ✔ |
| req/id-float | post | `err-32600(id:null)` | `400|err-32600(id:null)` | ✔ |
| req/id-object | post | `err-32600(id:null)` | `400|err-32600(id:null)` | ✔ |
| req/id-null | post | `err-32600(id:null)` | `400|err-32600(id:null)` | ✔ |
| req/params-string | post | `err-32600` | `400|err-32600` | ✔ |
| req/params-number-tools-call | post | `err-32600` | `400|err-32600` | ✔ |
| method/unknown | post | `err-32601` | `200|err-32601` | ✔ |
| method/unknown-namespaced | post | `err-32601` | `200|err-32601` | ✔ |
| method/notification-as-request | post | `err-32601` | `200|err-32601` | ✔ |
| method/empty-name | post | `err-32600` | `400|err-32600` | ✔ |
| method/initialize-twice | post | `err-32600` | `400|err-32600` | ✔ |
| method/initialize-no-params | pre | `err-32602` | `200|err-32602` | ✔ |
| method/initialize-bad-types | pre | `err-32602` | `200|err-32602` | ✔ |
| method/initialize-missing-clientinfo | pre | `err-32602` | `200|err-32602` | ✔ |
| method/initialize-unknown-version | pre | `result` | `200|result` | ✔ |
| tools/call-no-name | post | `err-32602` | `200|err-32602` | ✔ |
| tools/call-name-number | post | `err-32602` | `200|err-32602` | ✔ |
| tools/call-unknown-tool | post | `err-32602` | `200|err-32602` | ✔ |
| tools/call-args-string | post | `err-32602` | `200|err-32602` | ✔ |
| tools/call-wrong-type-arg | post | `result` | `200|result` | ✔ |
| tools/call-missing-required | post | `result` | `200|result` | ✔ |
| tools/call-extra-arg | post | `result` | `200|result` | ✔ |
| tools/list-bad-cursor | post | `err-32602` | `200|err-32602` | ✔ |
| tools/list-cursor-number | post | `err-32602` | `200|err-32602` | ✔ |
| resources/read-no-uri | post | `err-32602` | `200|err-32602` | ✔ |
| resources/read-uri-number | post | `err-32602` | `200|err-32602` | ✔ |
| resources/read-unknown | post | `err-32002` | `200|err-32002` | ✔ |
| resources/read-empty-uri | post | `err-32602` | `200|err-32602` | ✔ |
| resources/list-bad-cursor | post | `err-32602` | `200|err-32602` | ✔ |
| resources/templates-bad-cursor | post | `err-32602` | `200|err-32602` | ✔ |
| prompts/get-no-name | post | `err-32602` | `200|err-32602` | ✔ |
| prompts/get-unknown | post | `err-32602` | `200|err-32602` | ✔ |
| prompts/get-args-string | post | `err-32602` | `200|err-32602` | ✔ |
| prompts/list-bad-cursor | post | `err-32602` | `200|err-32602` | ✔ |
| v2025-06-18/batch | post0618 | `array[err-32600]` | `200|array[err-32600]` | ✔ |
| v2025-06-18/ping | post0618 | `result` | `200|result` | ✔ |
| v2024-11-05/batch | post1105 | `array[result,result]` | `200|array[result,result]` | ✔ |
| v2024-11-05/ping | post1105 | `result` | `200|result` | ✔ |

### Capability advertisement vs behaviour

| target | capability | advertised | method answered (not -32601) | consistent |
|---|---|:-:|:-:|:-:|
| base | tools | yes | yes | ✔ |
| base | resources | yes | yes | ✔ |
| base | prompts | yes | yes | ✔ |
| base | resources.subscribe | no | no | ✔ |
| base | completions | no | no | ✔ |
| base | logging | no | no | ✔ |
| memory | tools | yes | yes | ✔ |
| memory | resources | yes | yes | ✔ |
| memory | prompts | yes | yes | ✔ |
| memory | resources.subscribe | no | no | ✔ |
| memory | completions | no | no | ✔ |
| memory | logging | no | no | ✔ |
| auth | tools | yes | yes | ✔ |
| auth | resources | yes | yes | ✔ |
| auth | prompts | yes | yes | ✔ |
| auth | resources.subscribe | no | no | ✔ |
| auth | completions | no | no | ✔ |
| auth | logging | no | no | ✔ |
| resources | tools | yes | yes | ✔ |
| resources | resources | yes | yes | ✔ |
| resources | prompts | yes | yes | ✔ |
| resources | resources.subscribe | yes | yes | ✔ |
| resources | completions | yes | yes | ✔ |
| resources | logging | no | no | ✔ |

## 3. Cross-token matrix (row = token minted by, column = server presenting it to)

### L1 - separate secrets, shared audience, auth --allow-kidless: PASS

Expectation: accept only when source == destination (rejection reason: signature).

**stdio** (PASS)

| minted by \ presented to | base | memory | auth | resources |
|---|---|---|---|---|
| base | ✔ accepted | ✔ rejected (rpc -32001: Unauthorized: signature verification fai) | ✔ rejected (rpc -32001: Unauthorized: signature verification fai) | ✔ rejected (rpc -32001: Unauthorized: signature verification fai) |
| memory | ✔ rejected (rpc -32001: Unauthorized: signature verification fai) | ✔ accepted | ✔ rejected (rpc -32001: Unauthorized: signature verification fai) | ✔ rejected (rpc -32001: Unauthorized: signature verification fai) |
| auth | ✔ rejected (rpc -32001: Unauthorized: signature verification fai) | ✔ rejected (rpc -32001: Unauthorized: signature verification fai) | ✔ accepted | ✔ rejected (rpc -32001: Unauthorized: signature verification fai) |
| resources | ✔ rejected (rpc -32001: Unauthorized: signature verification fai) | ✔ rejected (rpc -32001: Unauthorized: signature verification fai) | ✔ rejected (rpc -32001: Unauthorized: signature verification fai) | ✔ accepted |

**http** (PASS)

| minted by \ presented to | base | memory | auth | resources |
|---|---|---|---|---|
| base | ✔ accepted | ✔ rejected (HTTP 401: invalid_token: signature verification fa) | ✔ rejected (HTTP 401: invalid_token: signature verification fa) | ✔ rejected (HTTP 401: invalid_token: signature verification fa) |
| memory | ✔ rejected (HTTP 401: invalid_token: signature verification fa) | ✔ accepted | ✔ rejected (HTTP 401: invalid_token: signature verification fa) | ✔ rejected (HTTP 401: invalid_token: signature verification fa) |
| auth | ✔ rejected (HTTP 401: invalid_token: signature verification fa) | ✔ rejected (HTTP 401: invalid_token: signature verification fa) | ✔ accepted | ✔ rejected (HTTP 401: invalid_token: signature verification fa) |
| resources | ✔ rejected (HTTP 401: invalid_token: signature verification fa) | ✔ rejected (HTTP 401: invalid_token: signature verification fa) | ✔ rejected (HTTP 401: invalid_token: signature verification fa) | ✔ accepted |

### L2 - shared secret, per-member audience (strict kid): PASS

Expectation: accept only when source == destination.

**stdio** (PASS)

| minted by \ presented to | base | memory | auth | resources |
|---|---|---|---|---|
| base | ✔ accepted | ✔ rejected (rpc -32001: Unauthorized: wrong audience) | ✔ rejected (rpc -32001: Unauthorized: missing kid) | ✔ rejected (rpc -32001: Unauthorized: wrong audience) |
| memory | ✔ rejected (rpc -32001: Unauthorized: wrong audience) | ✔ accepted | ✔ rejected (rpc -32001: Unauthorized: missing kid) | ✔ rejected (rpc -32001: Unauthorized: wrong audience) |
| auth | ✔ rejected (rpc -32001: Unauthorized: wrong audience) | ✔ rejected (rpc -32001: Unauthorized: wrong audience) | ✔ accepted | ✔ rejected (rpc -32001: Unauthorized: wrong audience) |
| resources | ✔ rejected (rpc -32001: Unauthorized: wrong audience) | ✔ rejected (rpc -32001: Unauthorized: wrong audience) | ✔ rejected (rpc -32001: Unauthorized: missing kid) | ✔ accepted |

**http** (PASS)

| minted by \ presented to | base | memory | auth | resources |
|---|---|---|---|---|
| base | ✔ accepted | ✔ rejected (HTTP 401: invalid_token: wrong audience) | ✔ rejected (HTTP 401: invalid_token: missing kid) | ✔ rejected (HTTP 401: invalid_token: wrong audience) |
| memory | ✔ rejected (HTTP 401: invalid_token: wrong audience) | ✔ accepted | ✔ rejected (HTTP 401: invalid_token: missing kid) | ✔ rejected (HTTP 401: invalid_token: wrong audience) |
| auth | ✔ rejected (HTTP 401: invalid_token: wrong audience) | ✔ rejected (HTTP 401: invalid_token: wrong audience) | ✔ accepted | ✔ rejected (HTTP 401: invalid_token: wrong audience) |
| resources | ✔ rejected (HTTP 401: invalid_token: wrong audience) | ✔ rejected (HTTP 401: invalid_token: wrong audience) | ✔ rejected (HTTP 401: invalid_token: missing kid) | ✔ accepted |

### L2b - shared secret, per-member audience, auth --allow-kidless: PASS

Expectation: accept only when source == destination.

**stdio** (PASS)

| minted by \ presented to | base | memory | auth | resources |
|---|---|---|---|---|
| base | ✔ accepted | ✔ rejected (rpc -32001: Unauthorized: wrong audience) | ✔ rejected (rpc -32001: Unauthorized: wrong audience) | ✔ rejected (rpc -32001: Unauthorized: wrong audience) |
| memory | ✔ rejected (rpc -32001: Unauthorized: wrong audience) | ✔ accepted | ✔ rejected (rpc -32001: Unauthorized: wrong audience) | ✔ rejected (rpc -32001: Unauthorized: wrong audience) |
| auth | ✔ rejected (rpc -32001: Unauthorized: wrong audience) | ✔ rejected (rpc -32001: Unauthorized: wrong audience) | ✔ accepted | ✔ rejected (rpc -32001: Unauthorized: wrong audience) |
| resources | ✔ rejected (rpc -32001: Unauthorized: wrong audience) | ✔ rejected (rpc -32001: Unauthorized: wrong audience) | ✔ rejected (rpc -32001: Unauthorized: wrong audience) | ✔ accepted |

**http** (PASS)

| minted by \ presented to | base | memory | auth | resources |
|---|---|---|---|---|
| base | ✔ accepted | ✔ rejected (HTTP 401: invalid_token: wrong audience) | ✔ rejected (HTTP 401: invalid_token: wrong audience) | ✔ rejected (HTTP 401: invalid_token: wrong audience) |
| memory | ✔ rejected (HTTP 401: invalid_token: wrong audience) | ✔ accepted | ✔ rejected (HTTP 401: invalid_token: wrong audience) | ✔ rejected (HTTP 401: invalid_token: wrong audience) |
| auth | ✔ rejected (HTTP 401: invalid_token: wrong audience) | ✔ rejected (HTTP 401: invalid_token: wrong audience) | ✔ accepted | ✔ rejected (HTTP 401: invalid_token: wrong audience) |
| resources | ✔ rejected (HTTP 401: invalid_token: wrong audience) | ✔ rejected (HTTP 401: invalid_token: wrong audience) | ✔ rejected (HTTP 401: invalid_token: wrong audience) | ✔ accepted |

### L3 - shared secret + shared audience, auth --allow-kidless: PASS

Expectation: accept every pair; token must be usable.

**stdio** (PASS)

| minted by \ presented to | base | memory | auth | resources |
|---|---|---|---|---|
| base | ✔ accepted | ✔ accepted | ✔ accepted | ✔ accepted |
| memory | ✔ accepted | ✔ accepted | ✔ accepted | ✔ accepted |
| auth | ✔ accepted | ✔ accepted | ✔ accepted | ✔ accepted |
| resources | ✔ accepted | ✔ accepted | ✔ accepted | ✔ accepted |

**http** (PASS)

| minted by \ presented to | base | memory | auth | resources |
|---|---|---|---|---|
| base | ✔ accepted | ✔ accepted | ✔ accepted | ✔ accepted |
| memory | ✔ accepted | ✔ accepted | ✔ accepted | ✔ accepted |
| auth | ✔ accepted | ✔ accepted | ✔ accepted | ✔ accepted |
| resources | ✔ accepted | ✔ accepted | ✔ accepted | ✔ accepted |

### L3s - shared secret + shared audience, auth strict (kid required): PASS

Expectation: accept every pair except foreign (kid-less) tokens presented to auth, which are refused for the missing kid.

**stdio** (PASS)

| minted by \ presented to | base | memory | auth | resources |
|---|---|---|---|---|
| base | ✔ accepted | ✔ accepted | ✔ rejected (rpc -32001: Unauthorized: missing kid) | ✔ accepted |
| memory | ✔ accepted | ✔ accepted | ✔ rejected (rpc -32001: Unauthorized: missing kid) | ✔ accepted |
| auth | ✔ accepted | ✔ accepted | ✔ accepted | ✔ accepted |
| resources | ✔ accepted | ✔ accepted | ✔ rejected (rpc -32001: Unauthorized: missing kid) | ✔ accepted |

**http** (PASS)

| minted by \ presented to | base | memory | auth | resources |
|---|---|---|---|---|
| base | ✔ accepted | ✔ accepted | ✔ rejected (HTTP 401: invalid_token: missing kid) | ✔ accepted |
| memory | ✔ accepted | ✔ accepted | ✔ rejected (HTTP 401: invalid_token: missing kid) | ✔ accepted |
| auth | ✔ accepted | ✔ accepted | ✔ accepted | ✔ accepted |
| resources | ✔ accepted | ✔ accepted | ✔ rejected (HTTP 401: invalid_token: missing kid) | ✔ accepted |

