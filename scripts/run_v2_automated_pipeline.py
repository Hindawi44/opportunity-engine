#!/usr/bin/env python3
"""Run the complete opportunity pipeline and persist an auditable scheduler record."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def atomic_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    temp.replace(path)


def run_stage(name: str, command: list[str], root: Path) -> dict[str, Any]:
    started_at = utc_now()
    start = time.monotonic()
    result = subprocess.run(command, cwd=root, check=False)
    return {
        "name": name,
        "command": command,
        "started_at": started_at,
        "ended_at": utc_now(),
        "duration_seconds": round(time.monotonic() - start, 3),
        "exit_code": result.returncode,
        "status": "SUCCESS" if result.returncode == 0 else "FAILED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run V2.3 scheduled automated opportunity pipeline")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--trigger", default=os.environ.get("PIPELINE_TRIGGER", "manual"))
    parser.add_argument("--max-history", type=int, default=200)
    args = parser.parse_args()

    root = args.root.resolve()
    data = root / "data"
    status_path = data / "automated_pipeline_status.json"
    history_path = data / "automated_pipeline_history.json"

    run_id = str(uuid.uuid4())
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "trigger": args.trigger,
        "started_at": utc_now(),
        "ended_at": None,
        "duration_seconds": None,
        "status": "RUNNING",
        "failed_stage": None,
        "stages": [],
        "safety": {
            "automatic_purchase": False,
            "automatic_bid": False,
            "automatic_external_action": False,
        },
    }
    atomic_write(status_path, record)
    start = time.monotonic()

    stages = [
        (
            "complete_sources_decisions_actions_learning",
            [sys.executable, "scripts/run_p5_learning_pipeline.py"] + (["--dry-run"] if args.dry_run else []),
        ),
        (
            "smart_alert_engine",
            [sys.executable, "scripts/run_v2_smart_alert_pipeline.py"],
        ),
    ]

    exit_code = 0
    for name, command in stages:
        stage = run_stage(name, command, root)
        record["stages"].append(stage)
        atomic_write(status_path, record)
        if stage["exit_code"] != 0:
            exit_code = int(stage["exit_code"])
            record["failed_stage"] = name
            break
        if args.dry_run:
            break

    record["ended_at"] = utc_now()
    record["duration_seconds"] = round(time.monotonic() - start, 3)
    record["status"] = "SUCCESS" if exit_code == 0 else "FAILED"
    atomic_write(status_path, record)

    history = load_json(history_path, {"schema_version": SCHEMA_VERSION, "runs": []})
    runs = list(history.get("runs", []))
    runs.append(record)
    runs = runs[-max(1, args.max_history):]
    atomic_write(history_path, {
        "schema_version": SCHEMA_VERSION,
        "run_count": len(runs),
        "runs": runs,
    })

    print(f"V2.3 automated pipeline {record['status']} (run_id={run_id})")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
