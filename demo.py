#!/usr/bin/env python3
"""End-to-end demo of mcp-crosscheck. Every step asserts something; the exit code is 0 only if all steps hold.

Needs the four sibling projects next to this repo (the family layout). Takes roughly 30-60 s.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
FAMILY = os.environ.get("MCP_FAMILY_DIR", os.path.dirname(HERE))
STEPS = []


def step(title):
    def deco(fn):
        STEPS.append((title, fn))
        return fn
    return deco


def xc(*args, **kw):
    return subprocess.run([sys.executable, "-m", "mcpcross"] + list(args), capture_output=True, text=True, cwd=HERE, **kw)


@step("the battery registry is listed")
def s1(ctx):
    r = xc("list")
    assert r.returncode == 0 and "XC-LIF-01" in r.stdout
    n = int(r.stdout.strip().splitlines()[-1].split()[0])
    assert n >= 50
    return "%d checks registered" % n


@step("full run: battery + differential + cross-token over 4 servers x stdio+http")
def s2(ctx):
    out = tempfile.mkdtemp(prefix="xc-demo-out-")
    ctx["out"] = out
    t0 = time.time()
    r = xc("run", "--family-dir", FAMILY, "--out", out)
    print(r.stdout.rstrip())
    assert r.returncode == 0, r.stderr[-500:]
    assert "CROSSCHECK PASS" in r.stdout
    rep = json.load(open(os.path.join(out, "crosscheck.json")))
    ctx["rep"] = rep
    assert rep["ok"] is True
    return "verdict PASS in %.0fs" % (time.time() - t0)


@step("battery: every (server, transport) pair ran the checks with zero failures")
def s3(ctx):
    s = ctx["rep"]["battery"]["summary"]
    assert set(s) == {"base", "memory", "auth", "resources"}
    total = 0
    for t, per in s.items():
        for tr, c in per.items():
            assert c["fail"] == 0 and c["error"] == 0, (t, tr, c)
            assert c["pass"] >= 45, (t, tr, c)
            total += c["pass"]
    return "%d passing check executions" % total


@step("differential: identical malformed inputs -> identical error codes on every server")
def s4(ctx):
    d = ctx["rep"]["differential"]
    assert d["summary"]["cases"] >= 60 and d["summary"]["ok"]
    kinds = set()
    for c in d["cases"]:
        for tr, v in c["by_transport"].items():
            assert v["agree"], c["case"]
            kinds.update(v["outcomes"].values())
    return "%d cases, %d distinct outcomes seen, 0 disagreements" % (d["summary"]["cases"], len(kinds))


@step("capabilities advertised == behaviour (resources.subscribe only on mcp-resource-heavy)")
def s5(ctx):
    caps = ctx["rep"]["differential"]["capabilities"]
    for name, t in caps.items():
        assert all(r["consistent"] for r in t["rows"].values()), name
    assert caps["resources"]["rows"]["resources.subscribe"]["advertised"] is True
    assert caps["base"]["rows"]["resources.subscribe"]["advertised"] is False
    return "4/4 servers consistent"


@step("cross-token L1/L2/L2b: different secret, different audience -> rejected; same server -> accepted")
def s6(ctx):
    reasons = set()
    for layer in ctx["rep"]["crosstoken"]["layers"]:
        if layer["layer"] == "L3":
            continue
        for tr, v in layer["transports"].items():
            for s, row in v["matrix"].items():
                for d, cell in row.items():
                    if s == d:
                        assert cell["outcome"] == "accept"
                    else:
                        assert cell["outcome"] == "reject", (layer["layer"], tr, s, d)
                        reasons.add(cell["reason"].split(":")[-1].strip())
    return "rejection reasons seen: %s" % ", ".join(sorted(reasons))


@step("cross-token L3: same secret + audience (+ auth --allow-kidless) -> all 16 pairs accepted and usable")
def s7(ctx):
    l3 = [l for l in ctx["rep"]["crosstoken"]["layers"] if l["layer"] == "L3"][0]
    n = 0
    for tr, v in l3["transports"].items():
        for s, row in v["matrix"].items():
            for d, cell in row.items():
                assert cell["outcome"] == "accept" and cell["usable"], (tr, s, d, cell)
                n += 1
    assert n == 32
    return "%d/32 accepted (16 pairs x 2 transports)" % n


def broken_family(proj, fname, old, new, partner="mcp-memory-first"):
    tmp = tempfile.mkdtemp(prefix="xc-demo-fam-")
    for d in (proj, partner):
        shutil.copytree(os.path.join(FAMILY, d), os.path.join(tmp, d), ignore=shutil.ignore_patterns(".git", "__pycache__", "evidence", "tests", ".mcp*"))
    pkg = {"mcp-base": "mcpforge", "mcp-memory-first": "mcpmem"}[proj]
    path = os.path.join(tmp, proj, pkg, fname)
    src = open(path).read()
    assert src.count(old) == 1
    open(path, "w").write(src.replace(old, new))
    return tmp


@step("negative control 1: a copy of mcp-base whose signature check is disabled -> crosscheck FAILS (cross-token L1)")
def s8(ctx):
    tmp = broken_family("mcp-base", "auth.py", "        if not hmac.compare_digest(expected, signature):\n            raise AuthError(\"invalid_token\", \"signature verification failed\")",
                        "        if False:\n            raise AuthError(\"invalid_token\", \"signature verification failed\")")
    try:
        out = tempfile.mkdtemp(prefix="xc-demo-neg-")
        r = xc("run", "--family-dir", tmp, "--targets", "base,memory", "--out", out, "--skip", "differential")
        assert r.returncode == 1, r.stdout[-400:]
        rep = json.load(open(os.path.join(out, "crosscheck.json")))
        cell = [l for l in rep["crosstoken"]["layers"] if l["layer"] == "L1"][0]["transports"]["stdio"]["matrix"]["memory"]["base"]
        assert cell["outcome"] == "accept" and not cell["ok"]
        fails = [cid for cid, d in rep["battery"]["results"]["base"].items() for r_ in d.values() if r_["status"] == "fail"]
        return "exit 1; L1 memory->base accepted a foreign-secret token; battery failures: %s" % ", ".join(sorted(set(fails)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@step("negative control 2: a copy of mcp-base answering -32602 for unknown methods -> battery + differential FAIL")
def s9(ctx):
    tmp = broken_family("mcp-base", "jsonrpc.py", "METHOD_NOT_FOUND = -32601", "METHOD_NOT_FOUND = -32602")
    try:
        out = tempfile.mkdtemp(prefix="xc-demo-neg-")
        r = xc("run", "--family-dir", tmp, "--targets", "base,memory", "--transports", "stdio", "--out", out, "--skip", "crosstoken")
        assert r.returncode == 1
        rep = json.load(open(os.path.join(out, "crosscheck.json")))
        dis = rep["differential"]["summary"]["disagreements"]
        assert dis
        fails = sorted({cid for cid, d in rep["battery"]["results"]["base"].items() for r_ in d.values() if r_["status"] == "fail"})
        assert fails
        return "exit 1; battery failed %s; %d differential disagreements" % (", ".join(fails), len(dis))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@step("the markdown report was written and contains the matrix")
def s10(ctx):
    md = open(os.path.join(ctx["out"], "crosscheck.md")).read()
    assert "overall verdict: PASS" in md and "Cross-token matrix" in md and "minted by" in md
    return "%d lines of markdown" % len(md.splitlines())


def main():
    if not all(os.path.isdir(os.path.join(FAMILY, d)) for d in ("mcp-base", "mcp-memory-first", "mcp-auth-hardened", "mcp-resource-heavy")):
        print("demo needs the sibling family directories under %s (set MCP_FAMILY_DIR)" % FAMILY, file=sys.stderr)
        return 2
    ctx, ok = {}, 0
    for i, (title, fn) in enumerate(STEPS, 1):
        print("\n[%d/%d] %s" % (i, len(STEPS), title), flush=True)
        try:
            msg = fn(ctx)
            print("    OK  %s" % (msg or ""), flush=True)
            ok += 1
        except AssertionError as exc:
            print("    FAIL assertion: %s" % exc, flush=True)
        except Exception as exc:  # noqa: BLE001
            print("    FAIL %s: %s" % (type(exc).__name__, exc), flush=True)
    print("\n" + "=" * 78)
    print("== %s - %d/%d steps passed" % ("DEMO OK" if ok == len(STEPS) else "DEMO FAILED", ok, len(STEPS)))
    print("=" * 78)
    return 0 if ok == len(STEPS) else 1


if __name__ == "__main__":
    sys.exit(main())
