#!/usr/bin/env bash
# Regenerate everything under evidence/ from a clean run. Aborts on the first failure (set -e).
# Needs the four sibling family projects. Usage: tools/build_evidence.sh [--skip-mutation]
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p evidence
ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }
SKIP_MUT=0
for a in "$@"; do case "$a" in --skip-mutation) SKIP_MUT=1;; esac; done
{ echo "# generated $(ts) | $(python3 --version) | $(uname -sr)"; echo "# git HEAD: $(git rev-parse --short HEAD 2>/dev/null || echo none)"; } > evidence/run_info.txt
echo "[1/8] unit tests";            python3 -m unittest discover -v > evidence/test_output.txt 2>&1
echo "[2/8] crosscheck run";        python3 -m mcpcross run --out evidence > evidence/crosscheck_output.txt 2>&1
echo "[3/8] stdlib-only check";     python3 tools/check_stdlib_only.py > evidence/stdlib_check.txt 2>&1
echo "[4/8] demo";                  ./demo.sh > evidence/demo_output.txt 2>&1
if [ "$SKIP_MUT" = 0 ]; then
  echo "[5/8] mutation sanity";     python3 tools/mutation_sanity.py > evidence/mutation_report.txt 2>&1
fi
echo "[6/8] ORIGINALITY block";     python3 tools/gen_originality.py
echo "[7/8] doc references";        python3 tools/check_doc_refs.py > evidence/doc_refs.txt 2>&1
echo "[8/8] manifest";              python3 tools/make_manifest.py
echo "evidence written:"; ls -l evidence
