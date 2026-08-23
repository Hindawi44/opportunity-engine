#!/usr/bin/env python3
"""Run the six-market Exa exact-lot shadow hunt and write a JSON artifact."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from opportunity_engine.discovery.exa_exact_lot_shadow_hunt import (
    run_exa_exact_lot_shadow_hunt,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--results-per-market", type=int, default=5)
    parser.add_argument("--max-page-fetches", type=int, default=30)
    args = parser.parse_args()

    api_key = " ".join(str(os.environ.get("EXA_API_KEY") or "").split()).strip()
    if not api_key:
        raise SystemExit("EXA_API_KEY is required")

    report = run_exa_exact_lot_shadow_hunt(
        exa_api_key=api_key,
        results_per_market=args.results_per_market,
        max_page_fetches=args.max_page_fetches,
    )
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(Path(args.output), report)

    v = report["verification"]
    print("status=", report["status"])
    print("exa_requests=", report["exa_request_count"])
    print("exa_unique_urls=", v["exa_unique_url_count"])
    print("pages=", v["page_fetches_succeeded"], "/", v["page_fetches_attempted"])
    print("exact_lot_candidates=", v["exact_lot_candidate_count"])
    print("active_stock_signals=", v["active_stock_signal_count"])
    print("source_only=", v["source_intelligence_only_count"])
    print("info_legal=", v["info_or_legal_only_count"])
    print("unproven=", v["unproven_page_count"])
    print("fetch_failed=", v["fetch_failed_count"])
    return 0 if report["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
