#!/usr/bin/env python3
"""Does mcp-crosscheck actually notice broken servers?

For each mutant: copy the mutated family member (+ one healthy partner) into a temp family dir, inject ONE bug into the copy, run
`python3 -m mcpcross run` against that copy and require a FAIL (exit 1). A mutant that is not caught is reported as SURVIVED.
Only the temp copy is ever modified. Usage: python3 tools/mutation_sanity.py [--family-dir DIR] [--only M2,M3] [--list]
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_FAMILY = os.path.dirname(HERE)
PKG = {"mcp-base": "mcpforge", "mcp-memory-first": "mcpmem", "mcp-auth-hardened": "mcpauth", "mcp-resource-heavy": "mcpres"}
NAME = {"mcp-base": "base", "mcp-memory-first": "memory", "mcp-auth-hardened": "auth", "mcp-resource-heavy": "resources"}

# (id, project dir, partner dir, file, old text, new text, description, which crosscheck part should notice)
MUTANTS = [
    ("C1", "mcp-base", "mcp-memory-first", "jsonrpc.py", "METHOD_NOT_FOUND = -32601", "METHOD_NOT_FOUND = -32602",
     "unknown method answers -32602", "battery + differential"),
    ("C2", "mcp-memory-first", "mcp-base", "auth.py", "if self.audience not in auds:", "if False:",
     "audience is not checked", "cross-token L2 + battery"),
    ("C3", "mcp-resource-heavy", "mcp-base", "auth.py", "if not hmac.compare_digest(expected, signature):", "if False:",
     "signature is not checked", "cross-token L1 + battery"),
    ("C4", "mcp-base", "mcp-memory-first", "server.py", 'if req.in_batch and self.protocol_version == "2025-06-18":', "if False:",
     "batches accepted on 2025-06-18", "battery"),
    ("C5", "mcp-memory-first", "mcp-base", "auth.py", 'if claims.get("iss") != self.issuer:', "if False:",
     "issuer is not checked", "battery"),
    ("C6", "mcp-auth-hardened", "mcp-base", "auth.py", "if not (self.allow_kidless and alg == \"HS256\"):", "if False:",
     "kid-less tokens accepted without the flag", "battery"),
    ("C7", "mcp-auth-hardened", "mcp-base", "auth.py",
     "            if not self.keyring.check_signature(signing_input, signature, key):\n                raise AuthError(\"invalid_token\", \"signature verification failed\", reason=\"bad_signature\")\n        try:",
     "            if False:\n                raise AuthError(\"invalid_token\", \"signature verification failed\", reason=\"bad_signature\")\n        try:",
     "kid-path signature is not checked", "battery"),
    ("C8", "mcp-base", "mcp-memory-first", "server.py", '"resources": {"subscribe": False, "listChanged": False}', '"resources": {"subscribe": True, "listChanged": False}',
     "advertises resources.subscribe but does not implement it", "differential (capability table) + battery"),
    ("C9", "mcp-resource-heavy", "mcp-base", "jsonrpc.py", "INVALID_PARAMS = -32602", "INVALID_PARAMS = -32600",
     "invalid params answered with -32600", "battery + differential"),
    ("C10", "mcp-base", "mcp-memory-first", "auth.py", "        if not hmac.compare_digest(expected, signature):\n            raise AuthError(\"invalid_token\", \"signature verification failed\")",
     "        if False:\n            raise AuthError(\"invalid_token\", \"signature verification failed\")", "signature is not checked (base)", "cross-token L1 + battery"),
]


def make_family(proj, partner, tmp):
    for d in {proj, partner}:
        shutil.copytree(os.path.join(DEFAULT_FAMILY_DIR[0], d), os.path.join(tmp, d),
                        ignore=shutil.ignore_patterns(".git", "__pycache__", "evidence", ".mcp*", "tests"))


DEFAULT_FAMILY_DIR = [DEFAULT_FAMILY]


def run_one(m, timeout):
    mid, proj, partner, fname, old, new, desc, who = m
    tmp = tempfile.mkdtemp(prefix="xc-mut-")
    try:
        make_family(proj, partner, tmp)
        path = os.path.join(tmp, proj, PKG[proj], fname)
        src = open(path).read()
        if src.count(old) != 1:
            return "BAD-PATTERN", "pattern occurs %d times in %s" % (src.count(old), path)
        open(path, "w").write(src.replace(old, new))
        cmd = [sys.executable, "-m", "mcpcross", "run", "--family-dir", tmp, "--targets", "%s,%s" % (NAME[proj], NAME[partner]), "--no-write"]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE, timeout=timeout)
        tail = [l for l in r.stdout.splitlines() if l.strip()][-1:] or ["(no output) " + r.stderr[-200:]]
        if r.returncode == 1:
            return "KILLED", "crosscheck exit 1"
        return "SURVIVED", "exit %d: %s" % (r.returncode, tail[0])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--family-dir", default=DEFAULT_FAMILY)
    ap.add_argument("--only", default="")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    DEFAULT_FAMILY_DIR[0] = a.family_dir
    chosen = [m for m in MUTANTS if not a.only or m[0] in a.only.split(",")]
    if a.list:
        for m in chosen:
            print(m[0], m[1], m[3], m[6])
        return 0
    survived = 0
    t0 = time.time()
    for m in chosen:
        st, why = run_one(m, a.timeout)
        survived += st != "KILLED"
        print("%-4s %-18s %-9s %s [expected detector: %s] %s" % (m[0], m[1], st, m[6], m[7], "" if st == "KILLED" else "-> " + why), flush=True)
    print("\nmutants killed: %d/%d (%.0fs)" % (len(chosen) - survived, len(chosen), time.time() - t0))
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())
