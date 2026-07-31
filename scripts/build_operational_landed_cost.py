#!/usr/bin/env python3
"""Build one zero-safe landed-cost sidecar from operational decisions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_engine.buyers import BuyerProfileV1
from opportunity_engine.costs import build_operational_landed_cost_export


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply Landed Cost Estimate V1 to one operational decision"
    )
    parser.add_argument("--decisions", default="data/decision_intelligence.json")
    parser.add_argument(
        "--buyer",
        default="config/buyers/mahmoud_namsos_v1.json",
    )
    parser.add_argument(
        "--output",
        default="data/operational_landed_cost_v1.json",
    )
    parser.add_argument("--opportunity-id", default=None)
    args = parser.parse_args()

    decision_payload = json.loads(
        Path(args.decisions).read_text(encoding="utf-8")
    )
    buyer = BuyerProfileV1.from_path(Path(args.buyer))
    export_payload = build_operational_landed_cost_export(
        decision_payload,
        buyer,
        opportunity_id=args.opportunity_id,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(export_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)

    selected = export_payload["source_opportunity"]
    estimate = export_payload["landed_cost_estimate"]
    print(
        json.dumps(
            {
                "output": str(output),
                "selection_status": export_payload["selection_status"],
                "opportunity_id": (
                    selected["opportunity_id"] if selected is not None else None
                ),
                "estimate_status": (
                    estimate["estimate_status"] if estimate is not None else None
                ),
                "missing_required_inputs": (
                    estimate["missing_required_inputs"]
                    if estimate is not None
                    else []
                ),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
