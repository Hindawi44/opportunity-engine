#!/usr/bin/env python3
"""Ingest today's Italy signals into restored checkpoint memory and run follow-up."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from opportunity_engine.discovery.italy_case_memory_adapter import run_italy_case_memory_cycle


def _read_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Italy case memory + follow-up V1")
    parser.add_argument("--discovery", type=Path, required=True)
    parser.add_argument(
        "--state-root",
        type=Path,
        default=Path("artifacts/multi-market-inputs"),
        help="Checkpoint input root; prior SQLite state must be restored here first.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/multi-market-daily-operator-checkpoint/italy-case-memory-v1.json"),
    )
    parser.add_argument(
        "--follow-up-output",
        type=Path,
        default=Path("artifacts/multi-market-daily-operator-checkpoint/italy-signal-follow-up-v1.json"),
    )
    args = parser.parse_args()

    discovery = _read_json(args.discovery)
    signals = [item for item in discovery.get("signals") or [] if isinstance(item, dict)]
    args.state_root.mkdir(parents=True, exist_ok=True)

    cycle = run_italy_case_memory_cycle(
        signals,
        input_root=args.state_root,
        environment=os.environ,
    )
    cycle["state_restore_owner"] = "MULTI_MARKET_DAILY_OPERATOR_CHECKPOINT"
    cycle["discovery_status"] = discovery.get("status")
    cycle["discovery_accepted_signal_count"] = discovery.get("accepted_signal_count")
    _write_json(args.output, cycle)
    _write_json(args.follow_up_output, dict(cycle.get("follow_up") or {}))

    summary = {
        "status": "SUCCESS",
        "state_restore_owner": cycle["state_restore_owner"],
        "discovery_status": discovery.get("status"),
        "discovery_signal_count": len(signals),
        "adapted_entity_signal_count": (cycle.get("adapter") or {}).get("adapted_entity_signal_count"),
        "persistent_case_count": cycle.get("persistent_case_count"),
        "follow_up_status": (cycle.get("follow_up") or {}).get("status"),
        "follow_up_search_request_count": (cycle.get("follow_up") or {}).get("search_request_count"),
        "commercial_lead_count": (cycle.get("follow_up") or {}).get("commercial_lead_count"),
        "output": args.output.as_posix(),
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
