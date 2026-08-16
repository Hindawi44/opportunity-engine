#!/usr/bin/env python3
"""Restore Italy memory, ingest today's clean signals, and run existing follow-up."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from opportunity_engine.discovery.italy_case_memory_adapter import run_italy_case_memory_cycle
from opportunity_engine.discovery.italy_case_memory_restore import restore_previous_italy_memory


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
        default=Path("artifacts/italy-case-memory"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/italy-case-memory/italy-case-memory-v1.json"),
    )
    parser.add_argument(
        "--follow-up-output",
        type=Path,
        default=Path("artifacts/italy-case-memory/italy-signal-follow-up-v1.json"),
    )
    parser.add_argument("--skip-restore", action="store_true")
    args = parser.parse_args()

    discovery = _read_json(args.discovery)
    signals = [item for item in discovery.get("signals") or [] if isinstance(item, dict)]
    args.state_root.mkdir(parents=True, exist_ok=True)

    if args.skip_restore:
        restore = {
            "status": "SKIPPED",
            "reason": "--skip-restore",
            "restored_database": None,
        }
        _write_json(args.state_root / "italy-memory-restore.json", restore)
    else:
        repository = str(os.environ.get("GITHUB_REPOSITORY") or "").strip()
        token = str(os.environ.get("GITHUB_TOKEN") or "").strip()
        run_id = int(str(os.environ.get("GITHUB_RUN_ID") or "0") or 0)
        if repository:
            restore = restore_previous_italy_memory(
                repository=repository,
                token=token,
                current_run_id=run_id,
                state_root=args.state_root,
                status_path=args.state_root / "italy-memory-restore.json",
            )
        else:
            restore = {
                "status": "SKIPPED_LOCAL_RUN",
                "reason": "GITHUB_REPOSITORY_MISSING",
                "restored_database": None,
            }
            _write_json(args.state_root / "italy-memory-restore.json", restore)

    cycle = run_italy_case_memory_cycle(
        signals,
        input_root=args.state_root,
        environment=os.environ,
    )
    cycle["live_restore"] = restore
    cycle["discovery_status"] = discovery.get("status")
    cycle["discovery_accepted_signal_count"] = discovery.get("accepted_signal_count")
    _write_json(args.output, cycle)
    _write_json(args.follow_up_output, dict(cycle.get("follow_up") or {}))

    summary = {
        "status": "SUCCESS",
        "restore_status": restore.get("status"),
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
