#!/usr/bin/env python3
"""Run one existing source command and record its outcome without hiding failure."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise SystemExit("A source command is required after --")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc).isoformat()
    completed = subprocess.run(command, check=False)  # noqa: S603
    finished_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "command": command,
        "exit_code": completed.returncode,
        "started_at": started_at,
        "finished_at": finished_at,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    status_path = output_dir / "execution-status.json"
    status_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"source_execution_status: {status_path}")
    print(f"source_exit_code: {completed.returncode}")
    # A source failure is data for the checkpoint. The consolidator decides the
    # single human action and keeps failure separate from a valid zero result.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
