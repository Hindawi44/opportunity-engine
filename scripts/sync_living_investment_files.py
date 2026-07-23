#!/usr/bin/env python3
"""Create/update Living Investment Files from the daily pipeline snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_engine.investment_file_sync import InvestmentFileSynchronizer


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize daily opportunities into living investment files")
    parser.add_argument("--input", default="data/todays_opportunities.json")
    parser.add_argument("--output-dir", default="data/investment_files")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Daily opportunity snapshot not found: {input_path}")

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    result = InvestmentFileSynchronizer(args.output_dir).sync_payload(payload)
    print(json.dumps(result.__dict__, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
