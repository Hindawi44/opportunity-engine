#!/usr/bin/env python3
"""Validate and export the resolved Norway Market Profile V1 snapshot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_engine.markets.norway import build_norway_market_profile_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Norway Market Profile V1 against official source registries"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/norway_market_profile_v1.json"),
    )
    args = parser.parse_args()

    root = args.root.resolve()
    snapshot = build_norway_market_profile_snapshot(root)
    output = args.output if args.output.is_absolute() else root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    source_snapshot = snapshot["source_registry_snapshot"]
    print(
        json.dumps(
            {
                "profile_id": snapshot["profile_id"],
                "market_code": snapshot["market_code"],
                "source_count": source_snapshot["source_count"],
                "status_counts": source_snapshot["status_counts"],
                "output": str(output),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
