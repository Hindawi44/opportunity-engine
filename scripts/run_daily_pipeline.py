#!/usr/bin/env python3
"""Run the automated daily opportunity pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_engine.ods.daily_pipeline import AutomatedDailyPipeline, DailyPipelineConfig
from opportunity_engine.ods.market_pricing import MarketComparable
from opportunity_engine.ods.real_cost import RealCostInputs


def _load_verified_inputs(path: str | None):
    if not path:
        return {}, {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    comparables = {
        opportunity_id: tuple(MarketComparable(**item) for item in items)
        for opportunity_id, items in payload.get("comparables_by_id", {}).items()
    }
    costs = {
        opportunity_id: RealCostInputs(**item)
        for opportunity_id, item in payload.get("costs_by_id", {}).items()
    }
    return comparables, costs


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate today's opportunity dashboard snapshot")
    parser.add_argument("--keyword", default=None, help="Optional Auksjonen search keyword")
    parser.add_argument("--limit", type=int, default=25, help="Maximum rows in the report")
    parser.add_argument("--output", default="data/todays_opportunities.json")
    parser.add_argument(
        "--verified-inputs",
        default=None,
        help="Optional JSON file containing verified comparables and explicit costs",
    )
    args = parser.parse_args()

    comparables, costs = _load_verified_inputs(args.verified_inputs)
    result = AutomatedDailyPipeline().run(
        DailyPipelineConfig(keyword=args.keyword, limit=args.limit, output_path=args.output),
        comparables_by_id=comparables,
        costs_by_id=costs,
    )
    print(json.dumps(result.__dict__, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
