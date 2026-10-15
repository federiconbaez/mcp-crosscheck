"""Cross-token tests: a token minted by family member S is presented to member D, for every ordered pair (S, D).

Layers (each isolates one reason a token may be refused):
  L1  every member has its OWN secret                      -> only S == D accepted (different secret must be rejected)
  L2  all members share ONE secret + issuer, own audience  -> only S == D accepted (audience binding must reject;
                                                              mcp-auth-hardened additionally refuses kid-less tokens)
  L2b same as L2 but mcp-auth-hardened runs with --allow-kidless -> only S == D accepted (isolates the audience reason)
  L3  all members share ONE secret + issuer + audience, mcp-auth-hardened runs with --allow-kidless
                                                           -> every pair accepted and the token is USABLE (tools/list works)
"""
import concurrent.futures
import secrets

from . import launch, targets as tgt
from .client import Client

LAYERS = [
    ("L1", "separate secrets", "accept only when source == destination"),
    ("L2", "shared secret, per-member audience (strict kid)", "accept only when source == destination"),
    ("L2b", "shared secret, per-member audience, auth --allow-kidless", "accept only when source == destination"),
    ("L3", "shared secret + shared audience, auth --allow-kidless", "accept every pair; token must be usable"),
]
SHARED_AUD = "crosscheck-shared"


def expected_accept(layer, s, d):
    return True if layer == "L3" else s == d


def _configs(layer, tlist):
    shared = secrets.token_hex(24)
    cfg = {}
    for t in tlist:
        cfg[t.name] = {
            "secret": secrets.token_hex(24) if layer == "L1" else shared,
            "audience": SHARED_AUD if layer == "L3" else t.audience,
            "kidless": layer in ("L2b", "L3"),
        }
    return cfg


def _trial(src, dst, transport):
    token = src.mint(scope=tgt.UNION_SCOPES)
    conn = dst.conn(transport, token)
    try:
        cl = Client(conn)
        rep = cl.initialize()
        if rep.result is not None:
            lst = cl.request("tools/list")
            tools = (lst.result or {}).get("tools") or []
            return {"outcome": "accept", "usable": bool(tools), "tools": len(tools), "code": None, "reason": ""}
        return {"outcome": "reject", "usable": False, "code": rep.code, "http": rep.status, "reason": rep.reason[:120]}
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


def run_layer(layer, tlist, family_dir, transports, jobs=6, tmp_root=None):
    cfg = _configs(layer, tlist)
    srcs = {t.name: launch.Deployment(t, family_dir, tmp_root=tmp_root, label=layer + "s", **cfg[t.name]) for t in tlist}
    dsts = {t.name: launch.Deployment(t, family_dir, tmp_root=tmp_root, label=layer + "d", **cfg[t.name]) for t in tlist}
    out = {"layer": layer, "transports": {}}
    try:
        for transport in transports:
            if transport == "http":
                for d in dsts.values():
                    d.start_http()
            jobs_list = [(s.name, d.name) for s in tlist for d in tlist]
            matrix = {s.name: {} for s in tlist}
            with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
                futs = {ex.submit(_trial, srcs[s], dsts[d], transport): (s, d) for s, d in jobs_list}
                for fut in concurrent.futures.as_completed(futs):
                    s, d = futs[fut]
                    try:
                        cell = fut.result()
                    except Exception as exc:  # noqa: BLE001
                        cell = {"outcome": "error", "usable": False, "code": None, "reason": "%s: %s" % (type(exc).__name__, exc)}
                    exp = expected_accept(layer, s, d)
                    cell["expected"] = "accept" if exp else "reject"
                    ok = (cell["outcome"] == "accept" and cell["usable"]) if exp else cell["outcome"] == "reject"
                    cell["ok"] = bool(ok)
                    matrix[s][d] = cell
            out["transports"][transport] = {"matrix": matrix, "ok": all(c["ok"] for r in matrix.values() for c in r.values())}
    finally:
        for dep in list(srcs.values()) + list(dsts.values()):
            dep.close()
    out["ok"] = all(v["ok"] for v in out["transports"].values())
    return out


def run_crosstoken(tlist, family_dir, transports=("stdio", "http"), tmp_root=None):
    layers = [dict(run_layer(l, tlist, family_dir, transports, tmp_root=tmp_root), title=title, expect=exp) for l, title, exp in LAYERS]
    return {"layers": layers, "ok": all(l["ok"] for l in layers), "targets": [t.name for t in tlist], "transports": list(transports)}
