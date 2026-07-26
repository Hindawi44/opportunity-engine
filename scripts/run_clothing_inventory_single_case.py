"""Execute one deterministic Clothing Inventory case end to end.

This runner reuses the approved Discovery, Opportunity Dossier, and eligibility
contracts. It writes one machine-readable dossier, one final report, and one
operator-readable summary. Missing evidence remains explicit and no automatic
commercial or financial action is performed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from opportunity_engine.discovery.real_case import run_real_clothing_inventory_case

DEFAULT_OUTPUT_DIR = Path("data/validation/clothing-inventory-single-case")


def build_final_report() -> dict[str, Any]:
    """Run the preserved case and return a deterministic final report."""
    outcome = run_real_clothing_inventory_case()
    payload = outcome.to_dict()
    payload.update(
        {
            "domain": "CLOTHING_INVENTORY",
            "final_outcome": outcome.outcome_type,
            "automatic_purchase_decision": False,
            "automatic_bid": False,
            "automatic_contact": False,
            "automatic_payment": False,
        }
    )
    return payload


def build_operator_summary(report: dict[str, Any]) -> str:
    """Create a concise operator-readable summary from the final report."""
    dossier = report["dossier"]
    eligibility = report["eligibility"]
    confirmed = dossier["confirmed_facts"]
    seller_claims = dossier["seller_claims"]
    missing = eligibility.get("missing_requirements", [])

    lines = [
        "Clothing Inventory — Single Case End-to-End Result",
        f"Outcome: {report['final_outcome']}",
        f"Source: {confirmed['source_name']}",
        f"Title: {confirmed['source_title']}",
        f"URL: {confirmed['source_url']}",
        f"Scenario: {dossier['primary_scenario']}",
        f"Quantity: {seller_claims.get('quantity', 'unknown')}",
        f"Observed price NOK: {seller_claims.get('asking_price_nok', 'unknown')}",
        f"Eligible for analysis: {eligibility['eligible_for_analysis']}",
        "Missing required evidence: " + (", ".join(missing) if missing else "none"),
        "Automatic purchase/bid/contact/payment: false",
    ]
    return "\n".join(lines) + "\n"


def write_outputs(output_dir: Path) -> dict[str, Path]:
    """Write the dossier, final report, and operator summary."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report = build_final_report()

    dossier_path = output_dir / "opportunity-dossier.json"
    report_path = output_dir / "final-report.json"
    summary_path = output_dir / "operator-summary.txt"

    dossier_path.write_text(
        json.dumps(report["dossier"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(build_operator_summary(report), encoding="utf-8")

    return {
        "dossier": dossier_path,
        "report": report_path,
        "summary": summary_path,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one deterministic Clothing Inventory case end to end."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for the dossier, final report, and operator summary.",
    )
    args = parser.parse_args()

    paths = write_outputs(args.output_dir)
    for label, path in paths.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
