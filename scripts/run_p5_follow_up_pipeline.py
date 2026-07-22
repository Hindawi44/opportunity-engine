#!/usr/bin/env python3
"""Run P5.1 Action Center, then build P5.2 follow-up lifecycle snapshots."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run(command: list[str], root: Path) -> int:
    return subprocess.run(command, cwd=root, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run P5.2 follow-up pipeline")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()

    p51_command = [sys.executable, "scripts/run_p5_action_pipeline.py"]
    if args.dry_run:
        p51_command.append("--dry-run")
    p51_exit = run(p51_command, root)
    if p51_exit != 0 or args.dry_run:
        return p51_exit

    return run([
        sys.executable,
        "scripts/build_follow_up_engine.py",
        "--follow-ups", "data/follow_up_queue.json",
        "--actions", "data/action_queue.json",
        "--state", "data/follow_up_status.json",
        "--due-work", "data/follow_up_due.json",
        "--completed", "data/completed_follow_ups.json",
    ], root)


if __name__ == "__main__":
    raise SystemExit(main())
