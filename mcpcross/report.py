"""Assemble the JSON + markdown crosscheck report."""
import datetime
import json
import os
import platform
import subprocess
import sys

from . import __version__, battery

TZ = datetime.timezone(datetime.timedelta(hours=-3))
MARK = {"pass": "✔", "fail": "✘", "skip": "–", "error": "!"}


def git_head(path):
    try:
        r = subprocess.run(["git", "-C", path, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def summarize_battery(results):
    """-> {target: {transport: {pass, fail, skip, error}}}"""
    out = {}
    for tname, checks in results.items():
        for cid, per_tr in checks.items():
            for tr, r in per_tr.items():
                c = out.setdefault(tname, {}).setdefault(tr, {"pass": 0, "fail": 0, "skip": 0, "error": 0})
                c[r["status"]] += 1
    return out


def differential_summary(diff):
    cases = diff["cases"]
    dis = [(c["case"], tr) for c in cases for tr, d in c["by_transport"].items() if not d["agree"]]
    par = [c["case"] for c in cases if c.get("transport_parity") is False]
    caps_bad = [(n, cap) for n, t in diff["capabilities"].items() for cap, r in t["rows"].items() if not r["consistent"]]
    return {"cases": len(cases), "disagreements": dis, "transport_parity_failures": par, "capability_inconsistencies": caps_bad,
            "ok": not dis and not par and not caps_bad}


def build(family_dir, targets, transports, results=None, diff=None, cross=None, started=None):
    rep = {"tool": "mcp-crosscheck", "version": __version__, "targets": [t.name for t in targets], "transports": list(transports),
           "meta": {"generated": datetime.datetime.now(TZ).isoformat(timespec="seconds"), "timezone": "UTC-3 (America/Buenos_Aires)",
                    "python": platform.python_version(), "platform": platform.platform(),
                    "commits": {t.name: git_head(t.root(family_dir)) for t in targets}}}
    if started:
        rep["meta"]["seconds"] = round(datetime.datetime.now().timestamp() - started, 1)
    ok = True
    if results is not None:
        s = summarize_battery(results)
        bad = sum(c["fail"] + c["error"] for t in s.values() for c in t.values())
        rep["battery"] = {"checks_registered": len(battery.CHECKS), "summary": s, "failures": bad, "results": results,
                          "titles": {c["id"]: c["title"] for c in battery.CHECKS}, "spec": {c["id"]: c["spec"] for c in battery.CHECKS}}
        ok &= bad == 0
    if diff is not None:
        rep["differential"] = dict(diff, summary=differential_summary(diff))
        ok &= rep["differential"]["summary"]["ok"]
    if cross is not None:
        rep["crosstoken"] = cross
        ok &= cross["ok"]
    rep["ok"] = bool(ok)
    return rep


def to_json(rep):
    return json.dumps(rep, indent=2, sort_keys=True, default=str) + "\n"


def _cell(c):
    if c["outcome"] == "accept":
        return "✔ accepted" if c["ok"] else "✘ accepted (expected reject)" if c["expected"] == "reject" else "✘ accepted but unusable"
    reason = c.get("reason", "")
    tag = "✔" if c["ok"] else "✘"
    where = ("HTTP %s" % c.get("http")) if c.get("http") else ("rpc %s" % c.get("code"))
    return "%s rejected (%s%s)" % (tag, where, (": " + reason[:40]) if reason else "")


def to_markdown(rep):
    L = []
    w = L.append
    w("# mcp-crosscheck report")
    w("")
    m = rep["meta"]
    w("- tool version: `%s`; generated: %s (%s); python %s" % (rep["version"], m["generated"], m["timezone"], m["python"]))
    w("- targets: %s; transports: %s" % (", ".join(rep["targets"]), ", ".join(rep["transports"])))
    w("- target commits: %s" % ", ".join("%s=%s" % kv for kv in sorted(m["commits"].items())))
    w("- **overall verdict: %s**" % ("PASS" if rep["ok"] else "FAIL"))
    w("")
    if "battery" in rep:
        b = rep["battery"]
        w("## 1. Shared black-box battery (%d checks registered)" % b["checks_registered"])
        w("")
        w("| target | transport | pass | fail | error | skip |")
        w("|---|---|---:|---:|---:|---:|")
        for t in rep["targets"]:
            for tr in rep["transports"]:
                c = b["summary"].get(t, {}).get(tr)
                if c:
                    w("| %s | %s | %d | %d | %d | %d |" % (t, tr, c["pass"], c["fail"], c["error"], c["skip"]))
        w("")
        w("Legend: ✔ pass, ✘ fail, ! harness error, – skipped (precondition absent, reason in the JSON).")
        w("")
        cols = [(t, tr) for t in rep["targets"] for tr in rep["transports"]]
        w("| check | title | " + " | ".join("%s/%s" % (t[:4], tr[0]) for t, tr in cols) + " |")
        w("|---|---|" + "---|" * len(cols))
        for cid in sorted(b["titles"]):
            cells = []
            for t, tr in cols:
                r = b["results"].get(t, {}).get(cid, {}).get(tr)
                cells.append(MARK[r["status"]] if r else " ")
            w("| %s | %s | %s |" % (cid, b["titles"][cid].replace("|", "/"), " | ".join(cells)))
        fails = [(t, cid, tr, r) for t, cs in b["results"].items() for cid, d in sorted(cs.items()) for tr, r in d.items() if r["status"] in ("fail", "error")]
        if fails:
            w("")
            w("### Failures")
            for t, cid, tr, r in fails:
                w("- `%s` %s/%s: %s" % (cid, t, tr, r["detail"]))
        skips = [(t, cid, tr, r) for t, cs in b["results"].items() for cid, d in sorted(cs.items()) for tr, r in d.items() if r["status"] == "skip"]
        if skips:
            w("")
            w("### Skips")
            for t, cid, tr, r in skips:
                w("- `%s` %s/%s: %s" % (cid, t, tr, r["detail"]))
        w("")
    if "differential" in rep:
        d = rep["differential"]
        s = d["summary"]
        w("## 2. Differential checks (identical input -> identical JSON-RPC error code)")
        w("")
        w("- %d malformed-input cases x %d transports x %d targets; disagreements: **%d**; stdio-vs-http semantic mismatches: **%d**; "
          "capability/behaviour inconsistencies: **%d**" % (s["cases"], len(d["transports"]), len(d["targets"]), len(s["disagreements"]),
                                                            len(s["transport_parity_failures"]), len(s["capability_inconsistencies"])))
        w("")
        w("| case | state | " + " | ".join(d["transports"]) + " | agree |")
        w("|---|---|" + "---|" * (len(d["transports"]) + 1))
        for c in d["cases"]:
            cells, agree = [], True
            for tr in d["transports"]:
                bt = c["by_transport"][tr]
                vals = sorted(set(bt["outcomes"].values()))
                cells.append("`%s`" % vals[0] if len(vals) == 1 else "**DIFFER** " + "; ".join("%s=%s" % kv for kv in bt["outcomes"].items()))
                agree &= bt["agree"]
            w("| %s | %s | %s | %s |" % (c["case"], c["state"], " | ".join(cells), "✔" if agree else "✘"))
        w("")
        w("### Capability advertisement vs behaviour")
        w("")
        w("| target | capability | advertised | method answered (not -32601) | consistent |")
        w("|---|---|:-:|:-:|:-:|")
        for tname in d["targets"]:
            for cap, r in d["capabilities"][tname]["rows"].items():
                w("| %s | %s | %s | %s | %s |" % (tname, cap, "yes" if r["advertised"] else "no", "yes" if r["answered"] else "no", "✔" if r["consistent"] else "✘"))
        w("")
    if "crosstoken" in rep:
        x = rep["crosstoken"]
        w("## 3. Cross-token matrix (row = token minted by, column = server presenting it to)")
        w("")
        for layer in x["layers"]:
            w("### %s - %s: %s" % (layer["layer"], layer["title"], "PASS" if layer["ok"] else "FAIL"))
            w("")
            w("Expectation: %s." % layer["expect"])
            for tr, v in layer["transports"].items():
                w("")
                w("**%s** (%s)" % (tr, "PASS" if v["ok"] else "FAIL"))
                w("")
                names = list(v["matrix"])
                w("| minted by \\ presented to | " + " | ".join(names) + " |")
                w("|---|" + "---|" * len(names))
                for s_ in names:
                    w("| %s | %s |" % (s_, " | ".join(_cell(v["matrix"][s_][d_]) for d_ in names)))
            w("")
    return "\n".join(L) + "\n"


def write(rep, outdir):
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "crosscheck.json"), "w") as f:
        f.write(to_json(rep))
    with open(os.path.join(outdir, "crosscheck.md"), "w") as f:
        f.write(to_markdown(rep))
