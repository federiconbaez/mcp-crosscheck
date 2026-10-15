"""Differential checks: feed IDENTICAL inputs to all targets and demand identical JSON-RPC error codes.

Also builds the capability-vs-behaviour table: for every capability a server advertises (or does not), does the matching
method really work (or really answer -32601)?
"""
import concurrent.futures
import json

from . import launch, targets as tgt
from .client import Client

INIT = {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "xc", "version": "1"}}


def _m(method, params=None, mid=1):
    m = {"jsonrpc": "2.0", "id": mid, "method": method}
    if params is not None:
        m["params"] = params
    return m


# (name, frame, state) - frame is an object (serialised) or a raw str/bytes.   state: pre | post | post0618 | post1105
CASES = [
    # ---- before initialize
    ("pre/tools-list", _m("tools/list"), "pre"),
    ("pre/resources-list", _m("resources/list"), "pre"),
    ("pre/prompts-get", _m("prompts/get", {"name": "x"}), "pre"),
    ("pre/tools-call", _m("tools/call", {"name": "memory_store", "arguments": {"content": "x"}}), "pre"),
    ("pre/unknown-method", _m("crosscheck/nope"), "pre"),
    ("pre/ping", _m("ping"), "pre"),
    ("pre/notification", {"jsonrpc": "2.0", "method": "notifications/initialized"}, "pre"),
    # ---- malformed framing (state-independent, run initialized)
    ("frame/truncated-json", '{"jsonrpc":"2.0","method":', "post"),
    ("frame/not-json", "hello", "post"),
    ("frame/trailing-garbage", '{"jsonrpc":"2.0","id":1,"method":"ping"} x', "post"),
    ("frame/nan-constant", '{"jsonrpc":"2.0","id":1,"method":"ping","params":{"a":NaN}}', "post"),
    ("frame/bare-scalar", "5", "post"),
    ("frame/null", "null", "post"),
    ("frame/string", '"ping"', "post"),
    ("frame/invalid-utf8", b'{"jsonrpc":"2.0","id":1,"method":"ping","params":{"x":"\xff"}}', "post"),
    ("frame/deep-nesting", "[" * 3000 + "]" * 3000, "post"),
    ("frame/empty-object", "{}", "post"),
    ("frame/empty-batch", "[]", "post"),
    ("frame/batch-of-scalars", "[1,2]", "post"),
    ("frame/batch-mixed", [_m("ping", mid=1), {"jsonrpc": "2.0", "method": "notifications/x"}, 5], "post"),
    ("frame/batch-ping", [_m("ping", mid=1), _m("ping", mid=2)], "post"),
    ("frame/batch-notifications", [{"jsonrpc": "2.0", "method": "notifications/a"}], "post"),
    # ---- invalid request objects
    ("req/no-jsonrpc", {"id": 1, "method": "ping"}, "post"),
    ("req/jsonrpc-1.0", {"jsonrpc": "1.0", "id": 1, "method": "ping"}, "post"),
    ("req/jsonrpc-number", {"jsonrpc": 2.0, "id": 1, "method": "ping"}, "post"),
    ("req/method-number", {"jsonrpc": "2.0", "id": 1, "method": 5}, "post"),
    ("req/method-missing", {"jsonrpc": "2.0", "id": 1}, "post"),
    ("req/id-bool", {"jsonrpc": "2.0", "id": True, "method": "ping"}, "post"),
    ("req/id-float", {"jsonrpc": "2.0", "id": 1.5, "method": "ping"}, "post"),
    ("req/id-object", {"jsonrpc": "2.0", "id": {}, "method": "ping"}, "post"),
    ("req/id-null", {"jsonrpc": "2.0", "id": None, "method": "ping"}, "post"),
    ("req/params-string", {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": "x"}, "post"),
    ("req/params-number-tools-call", {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": 7}, "post"),
    # ---- methods
    ("method/unknown", _m("crosscheck/nope"), "post"),
    ("method/unknown-namespaced", _m("resources/nope"), "post"),
    ("method/notification-as-request", _m("notifications/initialized"), "post"),
    ("method/empty-name", _m(""), "post"),
    ("method/initialize-twice", _m("initialize", INIT), "post"),
    ("method/initialize-no-params", _m("initialize"), "pre"),
    ("method/initialize-bad-types", _m("initialize", {"protocolVersion": 1, "capabilities": [], "clientInfo": "x"}), "pre"),
    ("method/initialize-missing-clientinfo", _m("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}}), "pre"),
    ("method/initialize-unknown-version", _m("initialize", dict(INIT, protocolVersion="1999-01-01")), "pre"),
    # ---- tools
    ("tools/call-no-name", _m("tools/call", {"arguments": {}}), "post"),
    ("tools/call-name-number", _m("tools/call", {"name": 5}), "post"),
    ("tools/call-unknown-tool", _m("tools/call", {"name": "crosscheck_nope"}), "post"),
    ("tools/call-args-string", _m("tools/call", {"name": "memory_recall", "arguments": "x"}), "post"),
    ("tools/call-wrong-type-arg", _m("tools/call", {"name": "memory_store", "arguments": {"content": 5}}), "post"),
    ("tools/call-missing-required", _m("tools/call", {"name": "memory_store", "arguments": {}}), "post"),
    ("tools/call-extra-arg", _m("tools/call", {"name": "memory_store", "arguments": {"content": "x", "zzz": 1}}), "post"),
    ("tools/list-bad-cursor", _m("tools/list", {"cursor": "!!"}), "post"),
    ("tools/list-cursor-number", _m("tools/list", {"cursor": 5}), "post"),
    # ---- resources
    ("resources/read-no-uri", _m("resources/read", {}), "post"),
    ("resources/read-uri-number", _m("resources/read", {"uri": 5}), "post"),
    ("resources/read-unknown", _m("resources/read", {"uri": "crosscheck://missing"}), "post"),
    ("resources/read-empty-uri", _m("resources/read", {"uri": ""}), "post"),
    ("resources/list-bad-cursor", _m("resources/list", {"cursor": "!!"}), "post"),
    ("resources/templates-bad-cursor", _m("resources/templates/list", {"cursor": "!!"}), "post"),
    # ---- prompts
    ("prompts/get-no-name", _m("prompts/get", {}), "post"),
    ("prompts/get-unknown", _m("prompts/get", {"name": "crosscheck_nope"}), "post"),
    ("prompts/get-args-string", _m("prompts/get", {"name": "recall_and_summarize", "arguments": "x"}), "post"),
    ("prompts/list-bad-cursor", _m("prompts/list", {"cursor": "!!"}), "post"),
    # ---- version-dependent
    ("v2025-06-18/batch", [_m("ping", mid=1)], "post0618"),
    ("v2025-06-18/ping", _m("ping"), "post0618"),
    ("v2024-11-05/batch", [_m("ping", mid=1), _m("ping", mid=2)], "post1105"),
    ("v2024-11-05/ping", _m("ping"), "post1105"),
]

STATE_VERSION = {"post": "2025-03-26", "post0618": "2025-06-18", "post1105": "2024-11-05"}


def outcome(rep, transport):
    """Canonical, comparable description of what came back. HTTP statuses are kept (they are part of the contract)."""
    def one(msg):
        if msg is None:
            return "silence"
        if isinstance(msg, dict) and "error" in msg:
            e = msg["error"]
            return "err%s%s" % (e.get("code") if isinstance(e, dict) else "?", "(id:null)" if msg.get("id") is None else "")
        if isinstance(msg, dict) and "result" in msg:
            return "result"
        return "other"
    if isinstance(rep.msg, list):
        body = "array[%s]" % ",".join(sorted(one(m) for m in rep.msg))
    else:
        body = one(rep.msg)
    if rep.eof and rep.msg is None:
        body = "eof"
    return ("%s|%s" % (rep.status, body)) if transport == "http" else body


def code_only(text):
    """Strip the HTTP status so stdio and http outcomes can be compared on JSON-RPC semantics alone."""
    return text.split("|", 1)[1] if "|" in text else text


def run_case(dep, transport, name, frame, state):
    token = dep.mint(scope=tgt.UNION_SCOPES)
    conn = dep.conn(transport, token)
    try:
        cl = Client(conn)
        if state != "pre":
            rep = cl.initialize(STATE_VERSION.get(state, "2025-03-26"))
            if rep.result is None:
                return "init-failed:%r" % (rep.msg,)
        return outcome(conn.send(frame), transport)
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


def collect_target(target, family_dir, transports, tmp_root=None):
    out = {}
    for transport in transports:
        dep = launch.Deployment(target, family_dir, tmp_root=tmp_root, label="diff-" + transport)
        try:
            for name, frame, state in CASES:
                out[(name, transport)] = run_case(dep, transport, name, frame, state)
        finally:
            dep.close()
    return out


CAP_METHODS = (("tools", "tools/list", None), ("resources", "resources/list", None), ("prompts", "prompts/list", None),
               ("resources.subscribe", "resources/subscribe", {"uri": "crosscheck://missing"}),
               ("completions", "completion/complete", {"ref": {"type": "ref/prompt", "name": "x"}, "argument": {"name": "x", "value": ""}}),
               ("logging", "logging/setLevel", {"level": "info"}))


def capability_table(target, family_dir, tmp_root=None):
    """advertised? and answered? (anything but -32601) for each capability, using one stdio session."""
    dep = launch.Deployment(target, family_dir, tmp_root=tmp_root, label="cap")
    try:
        cl = Client(dep.stdio(dep.mint(scope=tgt.UNION_SCOPES)))
        cl.initialize()
        caps = cl.init_result["capabilities"]
        rows = {}
        for cap, method, params in CAP_METHODS:
            adv = (cap in caps) if "." not in cap else bool(caps.get(cap.split(".")[0], {}).get(cap.split(".")[1]))
            rep = cl.request(method, params)
            answered = rep.code != -32601
            rows[cap] = {"advertised": adv, "answered": answered, "consistent": adv == answered, "code": rep.code}
        flags = {"tools.listChanged": bool(caps.get("tools", {}).get("listChanged")),
                 "resources.listChanged": bool(caps.get("resources", {}).get("listChanged")),
                 "prompts.listChanged": bool(caps.get("prompts", {}).get("listChanged"))}
        cl.close()
        return {"capabilities": json.loads(json.dumps(caps, sort_keys=True)), "rows": rows, "flags": flags}
    finally:
        dep.close()


def run_differential(targets, family_dir, transports=("stdio", "http"), jobs=4, tmp_root=None):
    per_target, caps = {}, {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        futs = {ex.submit(collect_target, t, family_dir, transports, tmp_root): ("cases", t.name) for t in targets}
        futs.update({ex.submit(capability_table, t, family_dir, tmp_root): ("caps", t.name) for t in targets})
        for fut in concurrent.futures.as_completed(futs):
            kind, name = futs[fut]
            (per_target if kind == "cases" else caps)[name] = fut.result()
    names = [t.name for t in targets]
    cases = []
    for name, frame, state in CASES:
        row = {"case": name, "state": state, "by_transport": {}}
        for transport in transports:
            outs = {n: per_target[n][(name, transport)] for n in names}
            row["by_transport"][transport] = {"outcomes": outs, "agree": len(set(outs.values())) == 1}
        if len(transports) > 1:
            semantic = {code_only(per_target[n][(name, tr)]) for n in names for tr in transports}
            row["transport_parity"] = len({code_only(per_target[n][(name, "stdio")]) for n in names} | {code_only(per_target[n][(name, "http")]) for n in names}) == 1
        cases.append(row)
    return {"cases": cases, "capabilities": caps, "targets": names, "transports": list(transports)}
