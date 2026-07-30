#!/usr/bin/env python3
"""Update the persistent pre-market case registry from sale-channel reports."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.discovery.pre_market_case_tracker import (
    load_case_registry,
    observation_from_sale_channel_report,
    update_case_registry,
    write_case_tracker_artifacts,
)


def _read_report(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"sale-channel report must be a JSON object: {path}")
    expected = "pre-market-sale-channel-search-1.0"
    if payload.get("schema_version") != expected:
        raise ValueError(f"unsupported sale-channel report schema in {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sale-channel-report",
        action="append",
        required=True,
        help="Path to sale-channel-search.json; repeat for multiple cases",
    )
    parser.add_argument(
        "--previous-registry",
        help="Existing pre-market-cases.json; omitted on the first run",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/pre-market-case-tracker",
        help="Artifact directory",
    )
    args = parser.parse_args()

    report_paths = [Path(value) for value in args.sale_channel_report]
    previous = load_case_registry(args.previous_registry)
    observations = [
        observation_from_sale_channel_report(
            _read_report(path),
            source_report=str(path),
        )
        for path in report_paths
    ]
    result = update_case_registry(previous, observations)
    paths = write_case_tracker_artifacts(result, Path(args.output_dir))

    print(f"Previous cases: {result.previous_case_count}")
    print(f"Cases observed: {result.observed_case_count}")
    print(f"Cases retained: {len(result.cases)}")
    print(f"Changes: {len(result.changes)}")
    print(f"Alerts: {len(result.alerts)}")
    print(f"Operator actions: {len(result.operator_actions)}")
    print(f"Verified inventory sales: {len(result.verified_cases)}")
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
