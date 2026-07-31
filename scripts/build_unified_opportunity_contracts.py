#!/usr/bin/env python3
"""Build the Unified Opportunity Contract V1 sidecar from official decisions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_engine.discovery.unified_decision_export import (
    build_unified_decision_export,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export decision_intelligence through Unified Opportunity Contract V1"
    )
    parser.add_argument("--decisions", default="data/decision_intelligence.json")
    parser.add_argument("--output", default="data/unified_opportunities_v1.json")
    parser.add_argument("--market", default="NO")
    args = parser.parse_args()

    decision_payload = json.loads(
        Path(args.decisions).read_text(encoding="utf-8")
    )
    export_payload = build_unified_decision_export(
        decision_payload,
        market=args.market,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(export_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "opportunity_count": export_payload["opportunity_count"],
                "output": str(output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
