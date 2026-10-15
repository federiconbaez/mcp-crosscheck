#!/usr/bin/env bash
# mcp-crosscheck demo: needs mcp-base, mcp-memory-first, mcp-auth-hardened, mcp-resource-heavy as sibling directories.
set -euo pipefail
cd "$(dirname "$0")"
exec python3 demo.py "$@"
