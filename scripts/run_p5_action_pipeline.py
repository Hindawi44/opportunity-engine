#!/usr/bin/env python3
"""Run the complete P4.1 pipeline, then build P5.1 Action Center snapshots."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run(command: list[str], root: Path) -> int:
    return subprocess.run(command, cwd=root, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run P5.1 action center pipeline")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()

    p4_command = [sys.executable, "scripts/run_p4_decision_pipeline.py"]
    if args.dry_run:
        p4_command.append("--dry-run")
    p4_exit = run(p4_command, root)
    if p4_exit != 0 or args.dry_run:
        return p4_exit

    return run([
        sys.executable,
        "scripts/build_action_center.py",
        "--decisions", "data/decision_intelligence.json",
        "--actions", "data/action_queue.json",
        "--follow-ups", "data/follow_up_queue.json",
        "--closed", "data/closed_opportunities.json",
        "--history", "data/decision_history.json",
    ], root)


if __name__ == "__main__":
    raise SystemExit(main())
