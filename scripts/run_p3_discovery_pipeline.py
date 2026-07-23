#!/usr/bin/env python3
"""Run the complete P2 pipeline, then persist P3 lifecycle and health snapshots."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


OFFICIAL_GAP_STATUSES = {"ACTIVE", "CODE_READY", "BLOCKED_AUTH", "PLANNED", "DEPRECATED"}


def run(command: list[str], root: Path) -> int:
    return subprocess.run(command, cwd=root, check=False).returncode


def validate_gap_matrix(path: Path) -> bool:
    if not path.is_file():
        print(f"Missing required source gap matrix: {path}", file=sys.stderr)
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Invalid source gap matrix {path}: {exc}", file=sys.stderr)
        return False
    allowed = set(payload.get("allowed_statuses") or [])
    statuses = {
        str(item.get("status"))
        for item in payload.get("sources", [])
        if isinstance(item, dict) and item.get("status")
    }
    if allowed != OFFICIAL_GAP_STATUSES or not statuses <= OFFICIAL_GAP_STATUSES:
        print("Source gap matrix contains non-official statuses", file=sys.stderr)
        return False
    return True


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

    registry_exit = 0
    audit_exit = 0
    if p2_exit == 0:
        audit_exit = run([
            sys.executable,
            "scripts/build_cross_source_deduplication_audit.py",
            "--daily", "data/todays_opportunities.json",
            "--discovery", "data/discovery_leads.json",
            "--events", "data/public_auction_event_leads.json",
            "--output", "data/cross_source_deduplication_audit.json",
        ], root)
        if audit_exit != 0:
            return audit_exit
        registry_exit = run([
            sys.executable,
            "scripts/build_opportunity_registry.py",
            "--discovery", "data/discovery_leads.json",
            "--scored", "data/scored_opportunities.json",
            "--existing", "data/opportunity_registry.json",
            "--audit", "data/cross_source_deduplication_audit.json",
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
    gap_output = root / "data/source_gap_matrix.json"
    gap_exit = run([
        sys.executable,
        "scripts/build_source_gap_matrix.py",
        "--plan", "config/source_expansion_plan.json",
        "--source-funnel", "data/source_funnel.json",
        "--output", "data/source_gap_matrix.json",
    ], root)
    if gap_exit == 0 and not validate_gap_matrix(gap_output):
        gap_exit = 1
    return p2_exit or audit_exit or registry_exit or health_exit or gap_exit


if __name__ == "__main__":
    raise SystemExit(main())
