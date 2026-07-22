#!/usr/bin/env python3
"""Run the complete P5.2 pipeline, then build P5.3 observational learning snapshots."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run(command: list[str], root: Path) -> int:
    return subprocess.run(command, cwd=root, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run P5.3 learning pipeline")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()

    command = [sys.executable, "scripts/run_p5_follow_up_pipeline.py"]
    if args.dry_run:
        command.append("--dry-run")
    exit_code = run(command, root)
    if exit_code != 0 or args.dry_run:
        return exit_code

    return run([
        sys.executable,
        "scripts/build_learning_engine.py",
        "--decisions", "data/decision_intelligence.json",
        "--follow-status", "data/follow_up_status.json",
        "--completed", "data/completed_follow_ups.json",
        "--history", "data/learning_history.json",
        "--metrics", "data/learning_metrics.json",
    ], root)


if __name__ == "__main__":
    raise SystemExit(main())
