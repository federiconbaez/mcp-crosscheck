"""Command line: python3 -m mcpcross run|list [options]"""
import argparse
import os
import sys
import time

from . import __version__, battery, crosstoken, differential, report, runner, targets as tgt

DEFAULT_FAMILY = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "evidence")


def _csv(s):
    return [x for x in (s or "").split(",") if x]


def build_parser():
    p = argparse.ArgumentParser(prog="mcpcross", description="Cross-validate the four MCP family servers (stdio + HTTP).")
    p.add_argument("--version", action="version", version="mcp-crosscheck " + __version__)
    sub = p.add_subparsers(dest="cmd")
    r = sub.add_parser("run", help="run battery + differential + cross-token and write the report")
    r.add_argument("--family-dir", default=DEFAULT_FAMILY, help="directory holding mcp-base/, mcp-memory-first/, mcp-auth-hardened/, mcp-resource-heavy/ (default: parent of this repo)")
    r.add_argument("--targets", default="", help="comma list of: " + ", ".join(tgt.BY_NAME) + " (default all)")
    r.add_argument("--transports", default="stdio,http")
    r.add_argument("--out", default=DEFAULT_OUT, help="evidence directory for crosscheck.json / crosscheck.md")
    r.add_argument("--only", default="", help="comma list of battery check ids (e.g. XC-RPC-01)")
    r.add_argument("--skip", default="", help="comma list of: battery,differential,crosstoken")
    r.add_argument("--jobs", type=int, default=4)
    r.add_argument("--no-write", action="store_true", help="do not write evidence files")
    l = sub.add_parser("list", help="list registered battery checks")
    l.add_argument("--json", action="store_true")
    return p


def cmd_list(a):
    import json
    rows = [{"id": c["id"], "title": c["title"], "spec": c["spec"], "transports": list(c["transports"])} for c in battery.CHECKS]
    if a.json:
        print(json.dumps(rows, indent=2))
    else:
        for c in rows:
            print("%-10s %-5s %s" % (c["id"], "+".join(t[0] for t in c["transports"]), c["title"]))
        print("%d checks" % len(rows))
    return 0


def cmd_run(a):
    started = time.time()
    try:
        tlist = tgt.select(_csv(a.targets), a.family_dir)
    except (ValueError, FileNotFoundError) as exc:
        print("mcpcross: %s" % exc, file=sys.stderr)
        return 2
    transports = tuple(_csv(a.transports))
    bad_tr = [t for t in transports if t not in ("stdio", "http")]
    if bad_tr or not transports:
        print("mcpcross: --transports must be a subset of stdio,http", file=sys.stderr)
        return 2
    skip = set(_csv(a.skip))
    results = diff = cross = None
    if "battery" not in skip:
        print("[1/3] battery: %d checks x %d targets x %s ..." % (len(battery.CHECKS), len(tlist), "+".join(transports)), flush=True)
        results = runner.run_battery(tlist, a.family_dir, transports, only=set(_csv(a.only)) or None, jobs=a.jobs)
    if "differential" not in skip:
        print("[2/3] differential ...", flush=True)
        diff = differential.run_differential(tlist, a.family_dir, transports, jobs=a.jobs)
    if "crosstoken" not in skip:
        print("[3/3] cross-token matrix ...", flush=True)
        cross = crosstoken.run_crosstoken(tlist, a.family_dir, transports)
    rep = report.build(a.family_dir, tlist, transports, results, diff, cross, started)
    if not a.no_write:
        report.write(rep, a.out)
        print("wrote %s/crosscheck.json and crosscheck.md" % a.out)
    if results is not None:
        for t in rep["targets"]:
            for tr in transports:
                c = rep["battery"]["summary"].get(t, {}).get(tr, {})
                print("  battery %-9s %-5s pass=%s fail=%s error=%s skip=%s" % (t, tr, c.get("pass"), c.get("fail"), c.get("error"), c.get("skip")))
    if diff is not None:
        s = rep["differential"]["summary"]
        print("  differential: %d cases, %d disagreements, %d transport mismatches, %d capability inconsistencies" %
              (s["cases"], len(s["disagreements"]), len(s["transport_parity_failures"]), len(s["capability_inconsistencies"])))
    if cross is not None:
        for l in cross["layers"]:
            print("  cross-token %-4s %s" % (l["layer"], "PASS" if l["ok"] else "FAIL"))
    print("CROSSCHECK %s" % ("PASS" if rep["ok"] else "FAIL"))
    return 0 if rep["ok"] else 1


def main(argv=None):
    p = build_parser()
    a = p.parse_args(argv)
    if a.cmd == "list":
        return cmd_list(a)
    if a.cmd is None:
        a = p.parse_args(["run"] + list(argv or sys.argv[1:]))
    return cmd_run(a)
