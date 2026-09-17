#!/usr/bin/env python3
"""Explicit review actions and durable read-only STUDY memory export."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import uuid4

from opportunity_engine.operator_study_memory import export_memory, record_decision


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    decide = commands.add_parser("decide")
    decide.add_argument("--database", type=Path, required=True)
    decide.add_argument("--opportunity-id", required=True)
    decide.add_argument("--action", required=True, choices=["STUDY", "DELETE", "LATER"])
    decide.add_argument("--reason", default="")
    decide.add_argument("--request-id", default="")
    export = commands.add_parser("export")
    export.add_argument("--input-root", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "decide":
        result = record_decision(
            args.database, opportunity_id=args.opportunity_id,
            action=args.action, reason=args.reason,
            request_id=args.request_id or str(uuid4()),
        )
        print(json.dumps({"persisted": True, "decision": result}, ensure_ascii=False))
        return 0
    result = export_memory(args.input_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"study": len(result["study"]), "later": len(result["later"]),
                      "explicit_decision_count": result["explicit_decision_count"],
                      "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
