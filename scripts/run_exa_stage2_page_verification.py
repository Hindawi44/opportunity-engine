#!/usr/bin/env python3
"""Run bounded Exa-vs-Brave discovery then verify Exa-only original pages."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from opportunity_engine.discovery.exa_shadow_page_verification import verify_exa_unique_pages
from scripts.run_exa_brave_shadow_benchmark import run_benchmark


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def run_live_stage2(
    *,
    exa_api_key: str,
    brave_api_key: str,
    markets: list[str],
    results_per_query: int = 3,
    max_page_fetches: int = 18,
) -> dict:
    benchmark = run_benchmark(
        exa_api_key=exa_api_key,
        brave_api_key=brave_api_key,
        markets=markets,
        results_per_query=results_per_query,
        provider_mode="both",
    )
    verification = verify_exa_unique_pages(
        benchmark,
        max_page_fetches=max_page_fetches,
    )
    return {
        "schema_version": "exa-stage2-live-proof-1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": verification.get("status"),
        "shadow_only": True,
        "benchmark": benchmark,
        "verification": verification,
        "production_provider_activation": False,
        "promotion_to_live_engine_enabled": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--markets", default="NO,SE,DE,FR,IT,NL")
    parser.add_argument("--results-per-query", type=int, default=3)
    parser.add_argument("--max-page-fetches", type=int, default=18)
    args = parser.parse_args()

    exa_api_key = _compact(os.environ.get("EXA_API_KEY"))
    brave_api_key = _compact(os.environ.get("BRAVE_SEARCH_API_KEY"))
    if not exa_api_key:
        raise SystemExit("EXA_API_KEY is required")
    if not brave_api_key:
        raise SystemExit("BRAVE_SEARCH_API_KEY is required")

    payload = run_live_stage2(
        exa_api_key=exa_api_key,
        brave_api_key=brave_api_key,
        markets=[item for item in args.markets.split(",") if item.strip()],
        results_per_query=args.results_per_query,
        max_page_fetches=args.max_page_fetches,
    )
    _write_json(Path(args.output), payload)
    verification = payload["verification"]
    print("status=", payload["status"])
    print("exa_unique_urls=", verification.get("exa_unique_url_count"))
    print("page_fetches=", verification.get("page_fetches_succeeded"), "/", verification.get("page_fetches_attempted"))
    print("exact_lot_candidates=", verification.get("exact_lot_candidate_count"))
    print("active_stock_signals=", verification.get("active_stock_signal_count"))
    print("source_intelligence_only=", verification.get("source_intelligence_only_count"))
    print("info_or_legal_only=", verification.get("info_or_legal_only_count"))
    print("unproven=", verification.get("unproven_page_count"))
    print("fetch_failed=", verification.get("fetch_failed_count"))
    return 0 if payload["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
