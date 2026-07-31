#!/usr/bin/env python3
"""Validate and export Buyer Profile V1 against its home market profile."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_engine.buyers import BuyerProfileV1, build_buyer_profile_snapshot
from opportunity_engine.markets.profile import MarketProfileV1


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Mahmoud Namsos Buyer Profile V1 snapshot")
    parser.add_argument(
        "--buyer",
        default="config/buyers/mahmoud_namsos_v1.json",
    )
    parser.add_argument(
        "--market",
        default="config/markets/no_v1.json",
    )
    parser.add_argument(
        "--output",
        default="data/buyer_profile_mahmoud_namsos_v1.json",
    )
    args = parser.parse_args()

    buyer = BuyerProfileV1.from_path(Path(args.buyer))
    market = MarketProfileV1.from_path(Path(args.market))
    snapshot = build_buyer_profile_snapshot(buyer, market)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)

    readiness = snapshot["matching_readiness"]
    print(
        json.dumps(
            {
                "output": str(output),
                "profile_id": snapshot["profile_id"],
                "matching_status": readiness["status"],
                "missing_required_constraints": readiness[
                    "missing_required_constraints"
                ],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
