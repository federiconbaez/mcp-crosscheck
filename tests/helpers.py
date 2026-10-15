import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAMILY = os.path.dirname(HERE)

# A tiny line-based JSON-RPC echo server used to test the stdio wire layer without any family member.
FAKE_STDIO = r'''
import json, sys
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        m = json.loads(line)
    except ValueError:
        print(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse"}}), flush=True)
        continue
    if isinstance(m, dict) and m.get("method") == "ping":
        print(json.dumps({"jsonrpc": "2.0", "id": m.get("id"), "result": {}}), flush=True)
    elif isinstance(m, dict) and m.get("method") == "notify-me":
        print(json.dumps({"jsonrpc": "2.0", "method": "notifications/x", "params": {}}), flush=True)
        print(json.dumps({"jsonrpc": "2.0", "id": m.get("id"), "result": {"n": 1}}), flush=True)
    elif isinstance(m, dict) and "id" not in m:
        pass
    elif isinstance(m, dict):
        print(json.dumps({"jsonrpc": "2.0", "id": m.get("id"), "error": {"code": -32601, "message": "nope"}}), flush=True)
'''


def siblings_present():
    return all(os.path.isdir(os.path.join(FAMILY, d)) for d in ("mcp-base", "mcp-memory-first", "mcp-auth-hardened", "mcp-resource-heavy"))
