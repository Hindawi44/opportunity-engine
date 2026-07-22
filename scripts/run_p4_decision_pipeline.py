#!/usr/bin/env python3
"""Run the complete P3 pipeline, build P4 decisions, then synchronize consumers."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run(command: list[str], root: Path) -> int:
    return subprocess.run(command, cwd=root, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run P4.1 decision consistency pipeline")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()

    p3_command = [sys.executable, "scripts/run_p3_discovery_pipeline.py"]
    if args.dry_run:
        p3_command.append("--dry-run")
    p3_exit = run(p3_command, root)
    if p3_exit != 0 or args.dry_run:
        return p3_exit

    decision_exit = run([
        sys.executable,
        "scripts/build_decision_intelligence.py",
        "--scored", "data/scored_opportunities.json",
        "--output", "data/decision_intelligence.json",
    ], root)
    if decision_exit != 0:
        return decision_exit

    return run([
        sys.executable,
        "scripts/sync_final_decisions.py",
        "--decisions", "data/decision_intelligence.json",
        "--dashboard", "data/dashboard.json",
        "--alerts", "data/smart_alerts.json",
    ], root)


if __name__ == "__main__":
    raise SystemExit(main())
