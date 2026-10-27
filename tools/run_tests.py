#!/usr/bin/env python3
"""Run all VX Ace Developer tooling test suites."""
from __future__ import annotations
import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SUITES = ["tests/tooling", "tests/project_reader", "tests/codex", "tests/patch_planner", "tests/mutation", "tests/project_validator", "tests/impact", "tests/marshal_codec", "tests/master", "tests/structure", "tests/index_queries", "tests/mcp", "tests/balance", "tests/notetags", "tests/text_export"]

def main():
    failures=[]
    for suite in SUITES:
        print(f"\n=== {suite} ===", flush=True)
        p=subprocess.run([sys.executable,"-m","unittest","discover","-s",suite,"-p","test_*.py","-v"],cwd=str(ROOT))
        if p.returncode: failures.append(suite)
    if failures:
        print("Failed suites: "+", ".join(failures),file=sys.stderr); return 1
    print("\nAll tooling suites passed."); return 0
if __name__=="__main__": raise SystemExit(main())
