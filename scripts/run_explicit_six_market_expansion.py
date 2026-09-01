#!/usr/bin/env python3
"""Run the visible FR/IT/NL Exact-Lot portion of the six-market checkpoint.

NO/SE/DE remain explicit source steps in the workflow.  This runner exposes the
previously hidden FR/IT/NL atexit work as one named production step without
adding a provider, market, query, request slot, or qualification rule.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

from opportunity_engine.discovery import unified_search_runtime_cli_hook as runtime


def main() -> int:
    runtime._run_expansion_clothing_exa()
    status_path = runtime._output_dir() / "unified-six-market-exa-runtime.json"
    if not status_path.exists():
        raise SystemExit("FR/IT/NL expansion did not write its runtime status")
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    markets = payload.get("markets") or {}
    if set(markets) != set(runtime.EXPANSION_EXA_MARKETS):
        raise SystemExit("FR/IT/NL expansion market coverage is incomplete")
    if payload.get("status") not in {"SUCCESS", "FAILURE", "SKIPPED_NO_EXA_API_KEY"}:
        raise SystemExit("FR/IT/NL expansion returned an invalid status")
    print(f"six_market_expansion_status: {payload.get('status')}")
    print(f"six_market_expansion_report: {status_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
