#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from opportunity_engine.discovery.france_market_discovery import collect_france_market_signals


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run bounded France clothing/bridal liquidation discovery."
    )
    parser.add_argument(
        "--output",
        default="artifacts/france-market-discovery/france-market-discovery.json",
    )
    parser.add_argument("--query-budget", type=int, default=None)
    parser.add_argument("--results-per-query", type=int, default=10)
    args = parser.parse_args()

    kwargs = {
        "environment": os.environ,
        "results_per_query": args.results_per_query,
    }
    if args.query_budget is not None:
        kwargs["query_budget"] = args.query_budget

    report = collect_france_market_signals(**kwargs)
    output = Path(args.output)
    _write(output, report)
    print(
        json.dumps(
            {
                "status": report.get("status"),
                "queries_attempted": report.get("queries_attempted"),
                "queries_succeeded": report.get("queries_succeeded"),
                "accepted_signal_count": report.get("accepted_signal_count"),
                "rejected_result_count": report.get("rejected_result_count"),
                "duplicate_result_count": report.get("duplicate_result_count"),
                "independent_domain_count": report.get("independent_domain_count"),
                "output": output.as_posix(),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 2 if report.get("status") == "BLOCKED_RETRIEVAL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
