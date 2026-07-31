#!/usr/bin/env python3
"""Build one zero-safe operational transport-input sidecar."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_engine.buyers import BuyerProfileV1
from opportunity_engine.logistics import build_operational_transport_export
from opportunity_engine.markets import MarketProfileV1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build Transport Estimate Input V1 for the selected operational opportunity"
    )
    parser.add_argument(
        "--landed-cost",
        default="data/operational_landed_cost_v1.json",
    )
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
        default="data/operational_transport_input_v1.json",
    )
    args = parser.parse_args()

    landed_cost_payload = json.loads(
        Path(args.landed_cost).read_text(encoding="utf-8")
    )
    buyer = BuyerProfileV1.from_path(Path(args.buyer))
    market = MarketProfileV1.from_path(Path(args.market))
    export_payload = build_operational_transport_export(
        landed_cost_payload,
        buyer,
        market,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(export_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)

    source = export_payload["source_opportunity"]
    snapshot = export_payload["transport_snapshot"]
    print(
        json.dumps(
            {
                "output": str(output),
                "selection_status": export_payload["selection_status"],
                "opportunity_id": (
                    source["opportunity_id"] if source is not None else None
                ),
                "transport_status": (
                    snapshot["transport_status"] if snapshot is not None else None
                ),
                "missing_inputs": (
                    snapshot["missing_inputs"] if snapshot is not None else []
                ),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
