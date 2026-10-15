"""The shared black-box conformance battery. Every check runs unchanged against every target and transport.

A check is ``@check(id, title, spec, transports=...)``; it raises ``Fail`` (a violated expectation) or ``Skip`` (not applicable,
with the reason recorded in the matrix). Expectations that are the *family consensus* (e.g. unknown tool -> -32602) are marked as
such in ``spec``; the differential module separately proves all four servers agree on every malformed input.
"""
import json
import threading
import time

from . import jwtkit, targets, wire
from .client import Client

CHECKS = []
SUPPORTED_VERSIONS = ("2025-03-26", "2024-11-05", "2025-06-18")


class Fail(AssertionError):
    pass


class Skip(Exception):
    pass


def expect(cond, msg="expectation failed"):
    if not cond:
        raise Fail(msg)


def check(cid, title, spec, transports=("stdio", "http")):
    def deco(fn):
        CHECKS.append({"id": cid, "title": title, "spec": spec, "transports": transports, "fn": fn})
        return fn
    return deco


class Ctx:
    """Per (deployment, transport) context handed to every check."""

    def __init__(self, dep, transport):
        self.dep, self.transport = dep, transport
        self.opened = []
        self._caps = None

    @property
    def http(self):
        return self.transport == "http"

    def token(self, scope=targets.UNION_SCOPES, **kw):
        return self.dep.mint(scope=scope, **kw)

    def conn(self, token="full"):
        tok = self.token() if token == "full" else token
        c = self.dep.conn(self.transport, tok)
        self.opened.append(c)
        return c

    def client(self, init=True, version="2025-03-26", token="full"):
        cl = Client(self.conn(token))
        if init:
            rep = cl.initialize(version)
            expect(rep.result is not None, "initialize failed: %r" % (rep.msg,))
        return cl

    def caps(self):
        if self._caps is None:
            cl = self.client()
            self._caps = cl.init_result.get("capabilities", {})
        return self._caps

    def close_all(self):
        for c in self.opened:
            try:
                c.close()
            except Exception:  # noqa: BLE001
                pass
        self.opened = []


def uniq(prefix):
    return "%s-%d" % (prefix, time.time_ns())


def tools_of(cl):
    rep = cl.request("tools/list")
    expect(rep.result is not None and isinstance(rep.result.get("tools"), list), "tools/list failed: %r" % (rep.msg,))
    return rep.result["tools"]


def all_pages(cl, method, key):
    items, cursor, guard = [], None, 0
    while True:
        rep = cl.request(method, {"cursor": cursor} if cursor else None)
        expect(rep.result is not None, "%s failed: %r" % (method, rep.msg))
        items += rep.result[key]
        cursor = rep.result.get("nextCursor")
        guard += 1
        if not cursor or guard > 50:
            return items


# ------------------------------------------------------------------------------------------------- lifecycle
@check("XC-LIF-01", "initialize result has protocolVersion, capabilities and serverInfo{name,version}", "MCP lifecycle: initialization")
def _(c):
    cl = c.client(init=False)
    rep = cl.initialize()
    r = rep.result
    expect(r is not None, rep.msg)
    expect(isinstance(r.get("protocolVersion"), str) and isinstance(r.get("capabilities"), dict), r)
    si = r.get("serverInfo")
    expect(isinstance(si, dict) and isinstance(si.get("name"), str) and isinstance(si.get("version"), str), r)
    expect("instructions" not in r or isinstance(r["instructions"], str), r)


@check("XC-LIF-02", "each of 2024-11-05, 2025-03-26, 2025-06-18 is negotiated as requested", "MCP lifecycle: version negotiation")
def _(c):
    for v in SUPPORTED_VERSIONS:
        cl = c.client(init=False)
        rep = cl.initialize(v)
        expect(rep.result and rep.result["protocolVersion"] == v, (v, rep.msg))


@check("XC-LIF-03", "unknown protocolVersion -> success with a version the server supports", "MCP lifecycle: version negotiation")
def _(c):
    rep = c.client(init=False).initialize("1999-01-01")
    expect(rep.result and rep.result["protocolVersion"] in SUPPORTED_VERSIONS, rep.msg)


@check("XC-LIF-04", "request before initialize is refused with -32600 (no result)", "family consensus + JSON-RPC 2.0 s5.1")
def _(c):
    cl = c.client(init=False)
    rep = cl.request("tools/list")
    expect(rep.code == -32600 and rep.result is None, rep.msg)


@check("XC-LIF-05", "ping answers {} both before and after initialize", "MCP utilities: ping")
def _(c):
    cl = c.client(init=False)
    expect(cl.request("ping").result == {}, "ping before initialize")
    cl.initialize()
    expect(cl.request("ping").result == {}, "ping after initialize")


@check("XC-LIF-06", "notifications/initialized and unknown notifications produce no response", "JSON-RPC 2.0 s4.1")
def _(c):
    cl = c.client(init=False)
    rep = cl.initialize()
    expect(rep.result is not None, rep.msg)
    r1 = cl.notify("notifications/initialized")
    r2 = cl.notify("notifications/x-crosscheck-unknown")
    for r in (r1, r2):
        expect(r.msg is None, "notification produced %r" % (r.msg,))
        if c.http:
            expect(r.status == 202, "HTTP notification status %r" % r.status)


@check("XC-LIF-07", "initialize with missing/invalid params -> -32602", "JSON-RPC 2.0 s5.1")
def _(c):
    cl = c.client(init=False)
    for params in (None, {}, {"protocolVersion": 5, "capabilities": {}, "clientInfo": {"name": "x", "version": "1"}}):
        rep = cl.request("initialize", params)
        expect(rep.code == -32602, (params, rep.msg))


# ------------------------------------------------------------------------------------------------- JSON-RPC
@check("XC-RPC-01", "malformed JSON -> -32700 with id null", "JSON-RPC 2.0 s5.1")
def _(c):
    rep = c.client().conn.send('{"jsonrpc":"2.0","method":')
    expect(isinstance(rep.msg, dict) and rep.code == -32700 and rep.msg.get("id") is None, rep.msg)


@check("XC-RPC-02", "structurally invalid request -> -32600 with id null", "JSON-RPC 2.0 s5.1")
def _(c):
    rep = c.client().conn.send('{"jsonrpc":"2.0","method":1,"params":"x"}')
    expect(rep.code == -32600 and rep.msg.get("id") is None, rep.msg)


@check("XC-RPC-03", "unknown method after initialize -> -32601 with the id echoed", "JSON-RPC 2.0 s5.1")
def _(c):
    rep = c.client().request("crosscheck/nope", mid=77)
    expect(rep.code == -32601 and rep.msg["id"] == 77, rep.msg)


@check("XC-RPC-04", "ids are echoed verbatim: string, 0, and a large integer", "JSON-RPC 2.0 s5")
def _(c):
    cl = c.client()
    for mid in ("abc-\u00e9", 0, 9007199254740993):
        rep = cl.request("ping", mid=mid)
        expect(rep.msg and rep.msg.get("id") == mid, (mid, rep.msg))


@check("XC-RPC-05", "invalid id types (bool, float, object) -> -32600", "JSON-RPC 2.0 s4 (strict ids; family consensus)")
def _(c):
    cl = c.client()
    for bad in (True, 1.5, {"a": 1}):
        rep = cl.conn.send({"jsonrpc": "2.0", "id": bad, "method": "ping"})
        expect(rep.code == -32600, (bad, rep.msg))


@check("XC-RPC-06", "params of the wrong JSON type -> -32602 or -32600, never a result", "JSON-RPC 2.0 s5.1")
def _(c):
    cl = c.client()
    rep = cl.conn.send({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": "nope"})
    expect(rep.code in (-32602, -32600), rep.msg)


@check("XC-RPC-07", "empty batch -> one -32600 object", "JSON-RPC 2.0 s6")
def _(c):
    rep = c.client().conn.send("[]")
    expect(isinstance(rep.msg, dict) and rep.code == -32600, rep.msg)


@check("XC-RPC-08", "batch [ping, ping] on 2025-03-26 -> array of two results with ids", "JSON-RPC 2.0 s6 / MCP 2025-03-26")
def _(c):
    cl = c.client(version="2025-03-26")
    rep = cl.conn.send([{"jsonrpc": "2.0", "id": 1, "method": "ping"}, {"jsonrpc": "2.0", "id": 2, "method": "ping"}])
    expect(isinstance(rep.msg, list) and sorted(m["id"] for m in rep.msg) == [1, 2] and all(m.get("result") == {} for m in rep.msg), rep.msg)


@check("XC-RPC-09", "batch of notifications only -> no response", "JSON-RPC 2.0 s6")
def _(c):
    cl = c.client()
    rep = cl.conn.send([{"jsonrpc": "2.0", "method": "notifications/x-a"}, {"jsonrpc": "2.0", "method": "notifications/x-b"}])
    expect(rep.msg is None, rep.msg)


@check("XC-RPC-10", "batches are rejected (-32600) once 2025-06-18 is negotiated", "MCP 2025-06-18 changelog: batching removed")
def _(c):
    cl = c.client(version="2025-06-18")
    rep = cl.conn.send([{"jsonrpc": "2.0", "id": 1, "method": "ping"}])
    errs = rep.msg if isinstance(rep.msg, list) else [rep.msg]   # a JSON-RPC server may answer with one error or an array of errors
    expect(errs and all(isinstance(m, dict) and (m.get("error") or {}).get("code") == -32600 for m in errs), rep.msg)


@check("XC-RPC-11", "invalid UTF-8 bytes -> -32700 and the server keeps serving", "JSON-RPC 2.0 s5.1 + robustness")
def _(c):
    cl = c.client()
    rep = cl.conn.send(b'{"jsonrpc":"2.0","id":1,"method":"ping","params":{"x":"\xff\xfe"}}')
    expect(rep.code == -32700, rep.msg)
    expect(cl.request("ping").result == {}, "server stopped serving")


# ------------------------------------------------------------------------------------------------- tools
@check("XC-TLS-01", "tools/list: unique names, description string, inputSchema type=object", "MCP server/tools: listing")
def _(c):
    tools = tools_of(c.client())
    expect(tools, "no tools")
    names = [t.get("name") for t in tools]
    expect(len(set(names)) == len(names) and all(isinstance(n, str) and n for n in names), names)
    for t in tools:
        expect(isinstance(t.get("description"), str), t["name"])
        expect(isinstance(t.get("inputSchema"), dict) and t["inputSchema"].get("type") == "object", t["name"])


@check("XC-TLS-02", "every tool schema is strict (additionalProperties:false at the top level)", "family design: strict schemas")
def _(c):
    bad = [t["name"] for t in tools_of(c.client()) if t["inputSchema"].get("additionalProperties") is not False]
    expect(not bad, "not strict: %s" % bad)


@check("XC-TLS-03", "unknown tool -> -32602; missing tool name -> -32602", "MCP server/tools: error handling (family consensus)")
def _(c):
    cl = c.client()
    expect(cl.tool("crosscheck_no_such_tool").code == -32602, "unknown tool")
    expect(cl.request("tools/call", {"arguments": {}}).code == -32602, "missing name")


@check("XC-TLS-04", "memory_store -> memory_recall round trip finds exactly the stored note", "MCP server/tools: calling")
def _(c):
    cl = c.client()
    marker = uniq("xcrt")
    cl.tool_json("memory_store", {"content": "round trip " + marker, "tags": ["xc"]})
    found = cl.tool_json("memory_recall", {"query": marker})
    expect(found["count"] == 1 and marker in found["results"][0]["content"], found)


@check("XC-TLS-05", "argument violations are tool errors (isError:true), not protocol errors", "MCP server/tools: tool execution errors")
def _(c):
    cl = c.client()
    rep = cl.tool("memory_store", {"content": 123})
    expect(rep.result is not None and rep.result.get("isError") is True, rep.msg)
    rep = cl.tool("memory_store", {"content": "x", "crosscheck_extra": 1})
    expect(rep.result is not None and rep.result.get("isError") is True, "extra property accepted: %r" % (rep.msg,))
    rep = cl.tool("memory_store", {})
    expect(rep.result is not None and rep.result.get("isError") is True, "missing required accepted: %r" % (rep.msg,))


@check("XC-TLS-06", "structuredContent appears only on a negotiated 2025-06-18 session", "MCP 2025-06-18 server/tools: structured content")
def _(c):
    for v, want in (("2025-03-26", False), ("2025-06-18", True)):
        cl = c.client(version=v)
        rep = cl.tool("memory_list", {}) if any(t["name"] == "memory_list" for t in tools_of(cl)) else cl.tool("memory_recall", {"query": "zzzxc"})
        expect(rep.result is not None, rep.msg)
        has = "structuredContent" in rep.result
        if v == "2025-03-26":
            expect(not has, "structuredContent on %s" % v)
        elif not has:
            raise Skip("target does not emit structuredContent for this tool on 2025-06-18")


@check("XC-TLS-07", "tools/list cursor: bogus cursor -> -32602, missing cursor fine", "MCP utilities: pagination")
def _(c):
    cl = c.client()
    rep = cl.request("tools/list", {"cursor": "!!!not-a-cursor"})
    expect(rep.code == -32602, rep.msg)
    expect(cl.request("tools/list", {}).result is not None)


# ------------------------------------------------------------------------------------------------- resources / prompts
@check("XC-RES-01", "resources/list and resources/templates/list have the specified shape (all pages)", "MCP server/resources: listing")
def _(c):
    cl = c.client()
    res = all_pages(cl, "resources/list", "resources")
    expect(res and all(isinstance(r.get("uri"), str) and isinstance(r.get("name"), str) for r in res), "bad resource entry")
    uris = [r["uri"] for r in res]
    expect(len(set(uris)) == len(uris), "duplicate URIs across pages")
    for t in all_pages(cl, "resources/templates/list", "resourceTemplates"):
        expect(isinstance(t.get("uriTemplate"), str) and isinstance(t.get("name"), str), t)


@check("XC-RES-02", "resources/read of listed resources returns contents with exactly one of text/blob", "MCP server/resources: reading")
def _(c):
    cl = c.client()
    res = all_pages(cl, "resources/list", "resources")
    for r in res[:8]:
        rep = cl.request("resources/read", {"uri": r["uri"]})
        expect(rep.result is not None, (r["uri"], rep.msg))
        for item in rep.result["contents"]:
            expect(item["uri"] and ("text" in item) != ("blob" in item), (r["uri"], item.keys()))


@check("XC-RES-03", "unknown resource -> -32002; missing uri -> -32602", "MCP server/resources: error handling (family consensus)")
def _(c):
    cl = c.client()
    expect(cl.request("resources/read", {"uri": "crosscheck://missing"}).code == -32002, "unknown uri")
    expect(cl.request("resources/read", {}).code == -32602, "missing uri")


@check("XC-PRM-01", "prompts/list shape; prompts/get unknown -> -32602", "MCP server/prompts")
def _(c):
    cl = c.client()
    prompts = all_pages(cl, "prompts/list", "prompts")
    expect(prompts and all(isinstance(p.get("name"), str) for p in prompts), prompts)
    for p in prompts:
        for a in p.get("arguments", []):
            expect(isinstance(a.get("name"), str), p)
    expect(cl.request("prompts/get", {"name": "crosscheck_no_such_prompt"}).code == -32602, "unknown prompt")


@check("XC-PRM-02", "a prompt with required arguments rejects a call without them (-32602)", "MCP server/prompts: argument validation")
def _(c):
    cl = c.client()
    for p in all_pages(cl, "prompts/list", "prompts"):
        if any(a.get("required") for a in p.get("arguments", [])):
            rep = cl.request("prompts/get", {"name": p["name"], "arguments": {}})
            expect(rep.code == -32602, (p["name"], rep.msg))
            return
    raise Skip("no prompt with required arguments")


# ------------------------------------------------------------------------------------------------- capabilities vs behaviour
@check("XC-CAP-01", "advertised capability <=> its methods work; unadvertised -> -32601", "MCP lifecycle: capability negotiation")
def _(c):
    cl = c.client()
    caps = cl.init_result["capabilities"]
    probes = {"tools": ("tools/list", None), "resources": ("resources/list", None), "prompts": ("prompts/list", None)}
    for cap, (method, params) in probes.items():
        rep = cl.request(method, params)
        if cap in caps:
            expect(rep.result is not None, "%s advertised but %s failed: %r" % (cap, method, rep.msg))
        else:
            expect(rep.code == -32601, "%s not advertised but %s answered %r" % (cap, method, rep.msg))
    rep = cl.request("logging/setLevel", {"level": "info"})
    if "logging" in caps:
        expect(rep.result is not None, "logging advertised but setLevel failed")
    else:
        expect(rep.code == -32601, "logging not advertised but setLevel answered %r" % (rep.msg,))


@check("XC-CAP-02", "resources.subscribe true => subscribe/unsubscribe work and validate; false => -32601", "MCP server/resources: subscriptions")
def _(c):
    cl = c.client()
    rcap = cl.init_result["capabilities"].get("resources", {})
    uri = all_pages(cl, "resources/list", "resources")[0]["uri"]
    rep = cl.request("resources/subscribe", {"uri": uri})
    if rcap.get("subscribe"):
        expect(rep.result == {}, "subscribe failed: %r" % (rep.msg,))
        expect(cl.request("resources/subscribe", {"uri": "crosscheck://missing"}).code in (-32002, -32602), "subscribing to unknown uri")
        expect(cl.request("resources/unsubscribe", {"uri": uri}).result == {}, "unsubscribe failed")
    else:
        expect(rep.code == -32601, "subscribe not advertised but answered %r" % (rep.msg,))
        expect(cl.request("resources/unsubscribe", {"uri": uri}).code == -32601, "unsubscribe answered although not advertised")


@check("XC-CAP-03", "resources.listChanged true => a real list_changed push follows a change (stdio) / GET stream exists (http)", "MCP server/resources: list changed")
def _(c):
    cl = c.client()
    caps = cl.init_result["capabilities"].get("resources", {})
    if not caps.get("listChanged"):
        raise Skip("listChanged not advertised (nothing to verify)")
    if c.http:
        conn = cl.conn
        import http.client
        h = http.client.HTTPConnection("127.0.0.1", conn.port, timeout=5)
        h.request("GET", "/mcp", headers={"Authorization": "Bearer " + conn.token, "Accept": "text/event-stream", "Mcp-Session-Id": conn.session})
        r = h.getresponse()
        ctype = r.getheader("Content-Type", "")
        h.close()
        expect(r.status == 200 and ctype.startswith("text/event-stream"), "listChanged advertised but GET stream gave %s %s" % (r.status, ctype))
        return
    rep = cl.tool("memory_store", {"content": uniq("xclc")})
    notes = rep.notes + cl.conn.drain_notes(1.0)
    expect(any(n.get("method") == "notifications/resources/list_changed" for n in notes), "no list_changed after a new memory: %r" % (notes,))


@check("XC-CAP-04", "completions advertised => completion/complete works on a listed prompt; unadvertised => -32601", "MCP utilities: completion")
def _(c):
    cl = c.client()
    caps = cl.init_result["capabilities"]
    prompt = next((p for p in all_pages(cl, "prompts/list", "prompts") if p.get("arguments")), None)
    params = {"ref": {"type": "ref/prompt", "name": prompt["name"] if prompt else "x"},
              "argument": {"name": prompt["arguments"][0]["name"] if prompt else "x", "value": ""}}
    rep = cl.request("completion/complete", params)
    if "completions" in caps:
        expect(rep.result and isinstance(rep.result["completion"]["values"], list) and len(rep.result["completion"]["values"]) <= 100, rep.msg)
    else:
        expect(rep.code == -32601, "completions not advertised but answered %r" % (rep.msg,))


@check("XC-CAP-05", "list_changed flags for tools/prompts are honest (false => the lists do not change)", "MCP server/tools+prompts: list changed")
def _(c):
    cl = c.client()
    caps = cl.init_result["capabilities"]
    before = ([t["name"] for t in tools_of(cl)], [p["name"] for p in all_pages(cl, "prompts/list", "prompts")])
    cl.tool("memory_store", {"content": uniq("xcl")})
    after = ([t["name"] for t in tools_of(cl)], [p["name"] for p in all_pages(cl, "prompts/list", "prompts")])
    if not caps.get("tools", {}).get("listChanged"):
        expect(before[0] == after[0], "tool list changed although listChanged is false")
    if not caps.get("prompts", {}).get("listChanged"):
        expect(before[1] == after[1], "prompt list changed although listChanged is false")


# ------------------------------------------------------------------------------------------------- authentication
def attempt_initialize(c, token, version="2025-03-26"):
    """-> Reply of an initialize attempt with ``token`` (None means no token at all)."""
    conn = c.dep.conn(c.transport, token)
    c.opened.append(conn)
    cl = Client(conn)
    rep = cl.request("initialize", {"protocolVersion": version, "capabilities": {}, "clientInfo": {"name": "xc", "version": "1"}})
    return rep


def rejected(rep):
    if rep.status is not None:
        return rep.status in (401, 403)
    return rep.code in (-32001, -32003)


@check("XC-AUT-01", "no token -> rejected (stdio -32001 / http 401 + WWW-Authenticate: Bearer)", "RFC 6750 s3 (simplified)")
def _(c):
    rep = attempt_initialize(c, None)
    expect(rejected(rep), rep)
    if c.http:
        expect(rep.status == 401 and rep.headers.get("www-authenticate", "").lower().startswith("bearer"), (rep.status, rep.headers))
    else:
        expect(rep.code == -32001, rep.msg)


@check("XC-AUT-02", "expired token (1 h ago, beyond any leeway) -> rejected", "RFC 7519 s4.1.4")
def _(c):
    expect(rejected(attempt_initialize(c, c.token(ttl=-3600))))


@check("XC-AUT-03", "signature with one flipped bit -> rejected", "RFC 7515 s5.2")
def _(c):
    expect(rejected(attempt_initialize(c, jwtkit.flip_signature_bit(c.token()))))


@check("XC-AUT-04", "alg=none and garbage tokens -> rejected", "RFC 8725 s3.1")
def _(c):
    for tok in (jwtkit.alg_none(c.token()), "garbage", "a.b.c", "x" * 9000):
        expect(rejected(attempt_initialize(c, tok)), tok[:20])


@check("XC-AUT-05", "valid signature but wrong audience -> rejected", "RFC 7519 s4.1.3")
def _(c):
    expect(rejected(attempt_initialize(c, c.token(aud="someone-else"))))


@check("XC-AUT-06", "valid signature but wrong issuer -> rejected", "RFC 7519 s4.1.1")
def _(c):
    expect(rejected(attempt_initialize(c, c.token(issuer="https://evil.example"))))


@check("XC-AUT-07", "token with only the base scope cannot call tools (-32003 / HTTP 403)", "scope enforcement")
def _(c):
    cl = c.client(token=c.token(scope=targets.READ_ONLY_BASE, sub="xc-noscope"))
    rep = cl.tool("memory_store", {"content": "denied"})
    expect(rep.code == -32003, rep.msg)


@check("XC-AUT-08", "a token's scopes do not leak between sessions (read-only vs full side by side)", "scope enforcement")
def _(c):
    ro = c.client(token=c.token(scope="mcp tools:read memory:read resources:read prompts:read", sub="xc-ro"))
    full = c.client(token=c.token(sub="xc-full"))
    expect(ro.tool("memory_store", {"content": "x"}).code == -32003, "read-only token stored a memory")
    expect(full.tool("memory_store", {"content": uniq("xcf")}).result is not None, "full token was denied")


# ------------------------------------------------------------------------------------------------- HTTP specifics
@check("XC-HTP-01", "foreign Origin header -> 403", "MCP transports: DNS-rebinding warning", ("http",))
def _(c):
    conn = c.conn()
    rep = conn.send({"jsonrpc": "2.0", "id": 1, "method": "ping"}, headers={"Origin": "http://evil.example"})
    expect(rep.status == 403, rep)


@check("XC-HTP-02", "non-JSON Content-Type -> 415", "HTTP semantics", ("http",))
def _(c):
    conn = c.conn()
    rep = conn.send('{"jsonrpc":"2.0","id":1,"method":"ping"}', headers={"Content-Type": "text/plain"})
    expect(rep.status == 415, rep)


@check("XC-HTP-03", "Mcp-Session-Id: issued, required later, unknown -> 404, DELETE ends the session", "MCP transports: session management", ("http",))
def _(c):
    cl = c.client()
    sid = cl.conn.session
    expect(sid and len(sid) >= 16, "no/short session id")
    rep = cl.conn.send({"jsonrpc": "2.0", "id": 5, "method": "tools/list"}, session=False)
    expect(rep.status in (400, 404), "tools/list without a session id -> %r" % rep.status)
    rep = cl.conn.send({"jsonrpc": "2.0", "id": 6, "method": "ping"}, headers={"Mcp-Session-Id": "0" * 32})
    expect(rep.status == 404, "unknown session -> %r" % rep.status)
    rep = cl.conn.request("DELETE", "/mcp", None, {"Mcp-Session-Id": sid})
    expect(rep.status in (200, 204), "DELETE -> %r" % rep.status)
    rep = cl.conn.send({"jsonrpc": "2.0", "id": 7, "method": "ping"})
    expect(rep.status == 404, "after DELETE -> %r" % rep.status)


@check("XC-HTP-04", "session is bound to the token subject: another subject cannot reuse the session id", "security design", ("http",))
def _(c):
    a = c.client(token=c.token(sub="xc-alice"))
    other = c.conn(c.token(sub="xc-mallory"))
    rep = other.send({"jsonrpc": "2.0", "id": 9, "method": "tools/list"}, headers={"Mcp-Session-Id": a.conn.session})
    expect(rep.status in (403, 404) and rep.result is None, rep)


@check("XC-HTP-05", "oversized body (> 1 MiB) -> 413", "robustness", ("http",))
def _(c):
    conn = c.conn()
    body = b'{"jsonrpc":"2.0","id":1,"method":"ping","params":{"pad":"' + b"x" * ((1 << 20) + 4096) + b'"}}'
    rep = conn.send(body)
    expect(rep.status == 413, rep)


@check("XC-HTP-06", "unsupported MCP-Protocol-Version header -> 400", "MCP 2025-06-18 transports: protocol version header", ("http",))
def _(c):
    cl = c.client(version="2025-06-18")
    rep = cl.conn.send({"jsonrpc": "2.0", "id": 3, "method": "ping"}, headers={"MCP-Protocol-Version": "1999-01-01"})
    expect(rep.status == 400, rep)


@check("XC-HTP-07", "parse error over HTTP -> 400 with a JSON-RPC error body", "JSON-RPC over HTTP", ("http",))
def _(c):
    rep = c.conn().send("{not json")
    expect(rep.status == 400 and rep.code == -32700, rep)


@check("XC-HTP-08", "GET /mcp without an event-stream Accept is refused (405/406); unknown paths -> 404", "MCP transports: Streamable HTTP", ("http",))
def _(c):
    cl = c.client()
    rep = cl.conn.request("GET", "/mcp", None, {"Mcp-Session-Id": cl.conn.session})
    expect(rep.status in (405, 406), rep.status)
    expect(cl.conn.request("GET", "/definitely-not-here").status == 404, "unknown path")


@check("XC-HTP-09", "batch over HTTP returns a JSON array with application/json", "JSON-RPC 2.0 s6", ("http",))
def _(c):
    cl = c.client()
    rep = cl.conn.send([{"jsonrpc": "2.0", "id": 1, "method": "ping"}])
    expect(rep.status == 200 and isinstance(rep.msg, list) and rep.headers.get("content-type", "").startswith("application/json"), rep)


# ------------------------------------------------------------------------------------------------- stdio specifics
@check("XC-STD-01", "CRLF frames and blank lines are tolerated; stdout carries only JSON", "MCP transports: stdio", ("stdio",))
def _(c):
    cl = c.client()
    rep = cl.conn.send(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}) + "\r")
    expect(rep.result == {}, rep)
    cl.conn.write_raw(b"\n\n   \n")
    expect(cl.request("ping").result == {})


@check("XC-STD-02", "line over 1 MiB -> -32600 and the server keeps serving", "robustness", ("stdio",))
def _(c):
    cl = c.client()
    rep = cl.conn.send(b'{"jsonrpc":"2.0","id":1,"method":"ping","params":{"a":"' + b"x" * (1 << 21) + b'"}}')
    expect(rep.code == -32600, rep)
    expect(cl.request("ping").result == {})


@check("XC-STD-03", "stdin EOF -> clean exit code 0", "MCP transports: stdio shutdown", ("stdio",))
def _(c):
    cl = c.client()
    expect(cl.conn.close() == 0, "exit code != 0")


# ------------------------------------------------------------------------------------------------- state, concurrency
@check("XC-PER-01", "a stored memory survives a server restart", "persistence")
def _(c):
    marker = uniq("xcper")
    a = c.client()
    a.tool_json("memory_store", {"content": "persist " + marker})
    a.close()
    if c.http:
        c.dep.stop_http()
    b = c.client()
    expect(b.tool_json("memory_recall", {"query": marker})["count"] == 1, "note lost across restart")


@check("XC-CON-01", "8 concurrent clients x 4 store/recall rounds: no errors, nothing lost", "robustness")
def _(c):
    marker = uniq("xccon")
    errors, done = [], []
    token = c.token()
    conns = []

    def work(n):
        try:
            conn = c.dep.conn(c.transport, token)
            conns.append(conn)
            cl = Client(conn)
            expect(cl.initialize().result is not None, "init")
            for i in range(4):
                cl.tool_json("memory_store", {"content": "%s w%d i%d" % (marker, n, i)})
            done.append(n)
        except Exception as exc:  # noqa: BLE001
            errors.append("%s: %s" % (type(exc).__name__, str(exc)[:200]))
    if c.http:
        c.dep.start_http()
    threads = [threading.Thread(target=work, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(120)
    c.opened += conns
    expect(not errors, errors[:3])
    cl = c.client()
    got = cl.tool_json("memory_recall", {"query": marker, "limit": 50})
    expect(got["count"] == 32, "stored 32, recalled %d" % got["count"])
