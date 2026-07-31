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

    unified_export_exit = run([
        sys.executable,
        "scripts/build_unified_opportunity_contracts.py",
        "--decisions", "data/decision_intelligence.json",
        "--output", "data/unified_opportunities_v1.json",
        "--market", "NO",
    ], root)
    if unified_export_exit != 0:
        return unified_export_exit

    landed_cost_exit = run([
        sys.executable,
        "scripts/build_operational_landed_cost.py",
        "--decisions", "data/decision_intelligence.json",
        "--buyer", "config/buyers/mahmoud_namsos_v1.json",
        "--output", "data/operational_landed_cost_v1.json",
    ], root)
    if landed_cost_exit != 0:
        return landed_cost_exit

    transport_input_exit = run([
        sys.executable,
        "scripts/build_operational_transport_input.py",
        "--landed-cost", "data/operational_landed_cost_v1.json",
        "--buyer", "config/buyers/mahmoud_namsos_v1.json",
        "--market", "config/markets/no_v1.json",
        "--output", "data/operational_transport_input_v1.json",
    ], root)
    if transport_input_exit != 0:
        return transport_input_exit

    shipment_evidence_exit = run([
        sys.executable,
        "scripts/build_shipment_evidence_queue.py",
        "--transport-input", "data/operational_transport_input_v1.json",
        "--output", "data/shipment_evidence_queue_v1.json",
    ], root)
    if shipment_evidence_exit != 0:
        return shipment_evidence_exit

    return run([
        sys.executable,
        "scripts/sync_final_decisions.py",
        "--decisions", "data/decision_intelligence.json",
        "--dashboard", "data/dashboard.json",
        "--alerts", "data/smart_alerts.json",
    ], root)


if __name__ == "__main__":
    raise SystemExit(main())
