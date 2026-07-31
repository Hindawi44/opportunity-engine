#!/usr/bin/env python3
"""Build shipment-evidence tasks from the operational transport sidecar."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_engine.logistics import build_shipment_evidence_queue


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build Shipment Evidence Workflow V1"
    )
    parser.add_argument(
        "--transport-input",
        default="data/operational_transport_input_v1.json",
    )
    parser.add_argument(
        "--output",
        default="data/shipment_evidence_queue_v1.json",
    )
    args = parser.parse_args()

    payload = json.loads(
        Path(args.transport_input).read_text(encoding="utf-8")
    )
    queue = build_shipment_evidence_queue(payload)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)

    source = queue["source_opportunity"]
    print(
        json.dumps(
            {
                "output": str(output),
                "selection_status": queue["selection_status"],
                "workflow_status": queue["workflow_status"],
                "opportunity_id": (
                    source["opportunity_id"] if source is not None else None
                ),
                "task_count": queue["task_count"],
                "blocking_task_count": queue["blocking_task_count"],
                "next_action": queue["next_action"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
