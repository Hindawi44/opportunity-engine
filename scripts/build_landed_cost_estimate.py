#!/usr/bin/env python3
"""Validate and export a Landed Cost Estimate V1 snapshot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_engine.costs import (
    LandedCostEstimateV1,
    build_landed_cost_snapshot,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build an auditable Landed Cost Estimate V1 snapshot"
    )
    parser.add_argument("--input", required=True)
    parser.add_argument(
        "--output",
        default="data/landed_cost_estimate_v1.json",
    )
    args = parser.parse_args()

    estimate = LandedCostEstimateV1.from_path(Path(args.input))
    snapshot = build_landed_cost_snapshot(estimate)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)

    print(
        json.dumps(
            {
                "output": str(output),
                "estimate_id": snapshot["estimate_id"],
                "estimate_status": snapshot["estimate_status"],
                "confidence": snapshot["confidence"],
                "missing_required_inputs": snapshot[
                    "missing_required_inputs"
                ],
                "qualification_status": snapshot[
                    "qualification_readiness"
                ]["status"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
