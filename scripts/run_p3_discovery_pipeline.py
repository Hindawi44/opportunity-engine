#!/usr/bin/env python3
"""Run the complete P2 pipeline, then persist P3 lifecycle and health snapshots."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run(command: list[str], root: Path) -> int:
    return subprocess.run(command, cwd=root, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run P3 discovery operations pipeline")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()

    p2_command = [sys.executable, "scripts/run_p2_pipeline.py"]
    if args.dry_run:
        p2_command.append("--dry-run")
    p2_exit = run(p2_command, root)

    if args.dry_run:
        return p2_exit

    if p2_exit == 0:
        registry_exit = run([
            sys.executable,
            "scripts/build_opportunity_registry.py",
            "--discovery", "data/discovery_leads.json",
            "--scored", "data/scored_opportunities.json",
            "--existing", "data/opportunity_registry.json",
            "--output", "data/opportunity_registry.json",
        ], root)
        if registry_exit != 0:
            return registry_exit

    health_exit = run([
        sys.executable,
        "scripts/build_discovery_health_report.py",
        "--pipeline-status", "data/pipeline_run_status.json",
        "--source-funnel", "data/source_funnel.json",
        "--registry", "data/opportunity_registry.json",
        "--output", "data/discovery_health.json",
    ], root)
    gap_exit = run([
        sys.executable,
        "scripts/build_source_gap_matrix.py",
        "--plan", "config/source_expansion_plan.json",
        "--source-funnel", "data/source_funnel.json",
        "--output", "data/source_gap_matrix.json",
    ], root)
    return p2_exit or health_exit or gap_exit


if __name__ == "__main__":
    raise SystemExit(main())
