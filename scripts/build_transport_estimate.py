#!/usr/bin/env python3
"""Validate Transport Estimate Input V1 and write its conservative snapshot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_engine.logistics import (
    TransportEstimateInputV1,
    build_transport_estimate_snapshot,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Transport Estimate Input V1 and export readiness"
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    estimate = TransportEstimateInputV1.from_path(Path(args.input))
    snapshot = build_transport_estimate_snapshot(estimate)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "transport_status": snapshot["transport_status"],
                "confidence": snapshot["confidence"],
                "output": str(output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
