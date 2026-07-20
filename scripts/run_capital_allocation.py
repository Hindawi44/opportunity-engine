#!/usr/bin/env python3
"""Generate a conservative capital allocation plan from today's snapshot."""

from __future__ import annotations

import argparse
import json

from opportunity_engine.ods.capital_allocation_snapshot import SnapshotCapitalAllocator


def main() -> int:
    parser = argparse.ArgumentParser(description="Allocate capital across verified buy opportunities")
    parser.add_argument("--snapshot", default="data/todays_opportunities.json")
    parser.add_argument("--capital", type=float, required=True, help="Total available capital in NOK")
    parser.add_argument("--reserve", type=float, default=0.20, help="Cash reserve fraction")
    parser.add_argument("--max-position", type=float, default=0.25, help="Maximum fraction per opportunity")
    parser.add_argument("--output", default="data/capital_allocation.json")
    args = parser.parse_args()

    plan = SnapshotCapitalAllocator().process(
        args.snapshot,
        total_capital_nok=args.capital,
        reserve_fraction=args.reserve,
        max_single_opportunity_fraction=args.max_position,
        output_path=args.output,
    )
    print(json.dumps(plan.__dict__, ensure_ascii=False, default=list, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
