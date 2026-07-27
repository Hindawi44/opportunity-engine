"""Execute one Clothing Inventory case end to end.

The default mode reuses the preserved deterministic case. Live mode fetches the
existing public Auksjonen category and selects exactly one active clothing-related
listing. Confirmed-intake mode accepts one validated source-agnostic evidence
package and stops at retained Opportunity Dossier reporting. Missing evidence
remains explicit and no automatic commercial or financial action is performed.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from opportunity_engine.discovery.classifier import classify_candidate, to_canonical_opportunity
from opportunity_engine.discovery.confirmed_dossier_intake import (
    ConfirmedDossierIntakeError,
    build_confirmed_dossier_report,
    load_confirmed_dossier_intake,
)
from opportunity_engine.discovery.e2e_checkpoint import (
    CheckpointOutcome,
    build_opportunity_dossier,
    evaluate_analysis_eligibility,
)
from opportunity_engine.discovery.models import DiscoveryCandidate
from opportunity_engine.discovery.real_case import run_real_clothing_inventory_case
from opportunity_engine.discovery.single_case_cost_evidence import (
    apply_verified_acquisition_costs,
)
from opportunity_engine.discovery.single_case_decision_intelligence import (
    apply_existing_scoring_and_decision,
)
from opportunity_engine.discovery.single_case_market_evidence import (
    apply_verified_market_comparables,
)
from opportunity_engine.source_ingestion.auksjonen import (
    AUKSJONEN_CATEGORY_URL,
    RawListing,
    fetch_public_page,
    parse_public_listings,
)

DEFAULT_OUTPUT_DIR = Path("data/validation/clothing-inventory-single-case")
_CLOTHING_TERMS = (
    "klær",
    "klaer",
    "kles",
    "jakke",
    "bukse",
    "skjorte",
    "genser",
    "arbeidstøy",
    "arbeidstoy",
    "tekstil",
    "clothing",
    "apparel",
    "garment",
)


def is_clothing_listing(listing: RawListing) -> bool:
    """Return true only when the observed title contains a clothing signal."""
    normalized = listing.title.casefold()
    return any(term in normalized for term in _CLOTHING_TERMS)


def is_active_listing(listing: RawListing) -> bool:
    """Return true only for a listing explicitly preserved as active."""
    return listing.listing_status == "ACTIVE"


def select_one_clothing_listing(listings: list[RawListing]) -> RawListing:
    """Select exactly one deterministic active clothing listing from live results."""
    matches = sorted(
        (
            listing
            for listing in listings
            if is_clothing_listing(listing) and is_active_listing(listing)
        ),
        key=lambda listing: listing.listing_id,
    )
    if not matches:
        raise ValueError("No active clothing-related Auksjonen listing was found")
    return matches[0]


def candidate_from_live_listing(
    listing: RawListing,
    *,
    observed_at: str | None = None,
) -> DiscoveryCandidate:
    """Convert one active observed listing without inventing quantity or contact facts."""
    if not is_active_listing(listing):
        raise ValueError("Ended Auksjonen listings cannot enter the live candidate path")
    timestamp = observed_at or datetime.now(timezone.utc).isoformat()
    return DiscoveryCandidate(
        title=listing.title,
        url=listing.url,
        source="AUKSJONEN_NO_LIVE_LISTING",
        discovered_at=timestamp,
        text=f"Auksjonen.no public active auction clothing listing: {listing.title}",
        location=listing.location,
        quantity=None,
        price_nok=listing.asking_price_nok,
        contact=None,
    )


def run_candidate(candidate: DiscoveryCandidate) -> CheckpointOutcome:
    """Run one candidate through the existing approved product boundary."""
    result = classify_candidate(candidate)
    dossier = build_opportunity_dossier(result)
    eligibility = evaluate_analysis_eligibility(result, dossier)
    canonical = to_canonical_opportunity(result)

    return CheckpointOutcome(
        outcome_type="ANALYSIS_READY" if eligibility.eligible_for_analysis else "EVIDENCE_REQUIRED",
        discovery_result=result,
        dossier=dossier,
        eligibility=eligibility,
        canonical_opportunity=canonical,
        analysis_invoked=False,
        automatic_purchase_decision=False,
    )


def build_live_final_report(
    *,
    html: str,
    source_url: str = AUKSJONEN_CATEGORY_URL,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Parse a public page and execute exactly one active clothing candidate."""
    listings = parse_public_listings(html, category_url=source_url)
    selected = select_one_clothing_listing(listings)
    candidate = candidate_from_live_listing(selected, observed_at=observed_at)
    outcome = run_candidate(candidate)
    report = _finalize_report(outcome)
    report.update(
        {
            "execution_mode": "LIVE_SOURCE",
            "source_page": source_url,
            "live_listings_extracted": len(listings),
            "active_clothing_listings": sum(
                is_clothing_listing(listing) and is_active_listing(listing)
                for listing in listings
            ),
            "selected_listing_id": selected.listing_id,
            "selected_listing_status": selected.listing_status,
        }
    )
    return report


def _finalize_report(outcome: CheckpointOutcome) -> dict[str, Any]:
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


def build_final_report() -> dict[str, Any]:
    """Run the preserved case and return a deterministic final report."""
    report = _finalize_report(run_real_clothing_inventory_case())
    report["execution_mode"] = "PRESERVED_CASE"
    return report


def load_comparables_payload(path: Path) -> object:
    """Read a machine-readable comparable package without inferring verification."""
    return json.loads(path.read_text(encoding="utf-8"))


def load_costs_payload(path: Path) -> object:
    """Read a machine-readable acquisition-cost package without inferring verification."""
    return json.loads(path.read_text(encoding="utf-8"))


def enrich_with_comparables(
    report: dict[str, Any],
    comparables_payload: object,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Attach explicit verified comparisons using the existing V2.8/V2.10 contracts."""
    return apply_verified_market_comparables(report, comparables_payload, now=now)


def enrich_with_costs(
    report: dict[str, Any],
    costs_payload: object,
) -> dict[str, Any]:
    """Attach explicit verified acquisition costs using V2.9/V2.10 contracts."""
    return apply_verified_acquisition_costs(report, costs_payload)


def enrich_with_decision(report: dict[str, Any]) -> dict[str, Any]:
    """Apply the existing score and canonical BUY_REVIEW/WATCH/REJECT policy."""
    return apply_existing_scoring_and_decision(report)


def _intake_operator_summary(
    report: dict[str, Any],
    dossier: dict[str, Any],
    confirmed: dict[str, Any],
    seller_claims: dict[str, Any],
) -> str:
    quantity = seller_claims.get("quantity", confirmed.get("quantity", "unknown"))
    price = seller_claims.get(
        "asking_price_nok",
        confirmed.get("asking_price_nok", "unknown"),
    )
    missing = dossier.get("missing_evidence", [])
    lines = [
        "Clothing Inventory — Confirmed Dossier Intake Result",
        f"Mode: {report.get('execution_mode', 'unknown')}",
        f"Opportunity title: {confirmed['source_title']}",
        f"Stable opportunity ID: {dossier['opportunity_id']}",
        f"Source: {confirmed['source_name']}",
        f"URL: {confirmed['source_url']}",
        f"Scenario: {dossier['primary_scenario']}",
        f"Opportunity status: {report['opportunity_status']}",
        f"Dossier status: {report['dossier_status']}",
        f"Final decision: {report['final_decision']}",
        f"Quantity: {quantity}",
        f"Observed price NOK: {price}",
        "Missing required evidence: " + (
            ", ".join(missing) if missing else "none"
        ),
        "Retained in opportunity report: yes",
        "Automatic purchase/bid/contact/reservation/payment: false",
    ]
    return "\n".join(lines) + "\n"


def build_operator_summary(report: dict[str, Any]) -> str:
    """Create a concise operator-readable summary from the final report."""
    dossier = report["dossier"]
    eligibility = report["eligibility"]
    confirmed = dossier["confirmed_facts"]
    seller_claims = dossier["seller_claims"]

    if report.get("execution_mode") == "CONFIRMED_DOSSIER_INTAKE":
        return _intake_operator_summary(
            report,
            dossier,
            confirmed,
            seller_claims,
        )

    missing = eligibility.get("missing_requirements", [])
    lines = [
        "Clothing Inventory — Single Case End-to-End Result",
        f"Mode: {report.get('execution_mode', 'unknown')}",
        f"Outcome: {report['final_outcome']}",
        f"Source: {confirmed['source_name']}",
        f"Title: {confirmed['source_title']}",
        f"URL: {confirmed['source_url']}",
        f"Scenario: {dossier['primary_scenario']}",
        f"Quantity: {seller_claims.get('quantity', 'unknown')}",
        f"Observed price NOK: {seller_claims.get('asking_price_nok', 'unknown')}",
        f"Eligible for analysis: {eligibility['eligible_for_analysis']}",
        "Missing required evidence: " + (", ".join(missing) if missing else "none"),
    ]

    market = report.get("market_comparables")
    if isinstance(market, dict):
        lines.extend(
            [
                f"Verified comparables: {market.get('accepted_count', 0)}",
                f"Market-comparable status: {market.get('status', 'unknown')}",
                f"Conservative market value NOK: {market.get('conservative_market_value_nok', 'unknown')}",
            ]
        )

    costs = report.get("acquisition_cost_evidence")
    if isinstance(costs, dict):
        lines.extend(
            [
                f"Verified cost components: {costs.get('accepted_count', 0)}",
                f"Acquisition-cost status: {costs.get('status', 'unknown')}",
                f"True acquisition cost NOK: {costs.get('true_acquisition_cost_nok', 'unknown')}",
            ]
        )

    financial = report.get("financial_integration")
    if isinstance(financial, dict):
        lines.append(f"Financial decision gate: {financial.get('decision_gate', 'unknown')}")
        if financial.get("conservative_resale_value_nok") is not None:
            lines.append(
                f"Conservative resale value NOK: {financial.get('conservative_resale_value_nok')}"
            )
        if financial.get("expected_profit_nok") is not None:
            lines.append(f"Expected profit NOK: {financial.get('expected_profit_nok')}")
        if financial.get("roi_percent") is not None:
            lines.append(f"ROI percent: {financial.get('roi_percent')}")

    decision = report.get("decision_intelligence")
    if isinstance(decision, dict):
        lines.extend(
            [
                f"Opportunity score: {decision.get('opportunity_score', 'unknown')}",
                f"Score grade: {decision.get('score_grade', 'unknown')}",
                f"Final decision: {decision.get('final_decision', 'unknown')}",
                f"Final decision Arabic: {decision.get('final_decision_ar', 'unknown')}",
                f"Maximum safe bid NOK: {decision.get('maximum_safe_bid_nok', 'unknown')}",
                f"Human approval required: {decision.get('requires_human_approval', False)}",
            ]
        )

    lines.append("Automatic purchase/bid/contact/payment: false")
    return "\n".join(lines) + "\n"


def write_report_outputs(report: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    """Write one supplied report as dossier, final report, and operator summary."""
    output_dir.mkdir(parents=True, exist_ok=True)
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

    return {"dossier": dossier_path, "report": report_path, "summary": summary_path}


def write_outputs(output_dir: Path) -> dict[str, Path]:
    """Write outputs for the preserved deterministic case."""
    return write_report_outputs(build_final_report(), output_dir)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one Clothing Inventory case end to end."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for the dossier, final report, and operator summary.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Fetch the public Auksjonen category and select one active clothing listing.",
    )
    parser.add_argument("--source-url", default=AUKSJONEN_CATEGORY_URL)
    parser.add_argument(
        "--html-file",
        type=Path,
        help="Use a preserved HTML page instead of network access; implies live parsing.",
    )
    parser.add_argument(
        "--confirmed-intake-file",
        type=Path,
        help=(
            "Use one validated confirmed active Clothing Inventory JSON intake. "
            "This mode writes a retained evidence-required dossier and does not "
            "invoke financial analysis or decision intelligence."
        ),
    )
    parser.add_argument(
        "--comparables-file",
        type=Path,
        help=(
            "Optional JSON package of explicit verified market comparisons. "
            "Only records with verified=true are eligible."
        ),
    )
    parser.add_argument(
        "--costs-file",
        type=Path,
        help=(
            "Optional JSON package of explicit verified acquisition-cost components. "
            "All six V2.9 components are required for a complete acquisition cost."
        ),
    )
    args = parser.parse_args()

    if args.confirmed_intake_file and (args.live or args.html_file):
        parser.error(
            "--confirmed-intake-file is mutually exclusive with --live and --html-file"
        )
    if args.confirmed_intake_file and (
        args.comparables_file or args.costs_file
    ):
        parser.error(
            "--confirmed-intake-file does not accept --comparables-file or --costs-file"
        )

    if args.confirmed_intake_file:
        try:
            intake = load_confirmed_dossier_intake(args.confirmed_intake_file)
            report = build_confirmed_dossier_report(intake)
        except ConfirmedDossierIntakeError as exc:
            print(json.dumps(exc.to_dict(), ensure_ascii=False), file=sys.stderr)
            return 2

        paths = write_report_outputs(report, args.output_dir)
        for label, path in paths.items():
            print(f"{label}: {path}")
        return 0

    if args.live or args.html_file:
        html = (
            args.html_file.read_text(encoding="utf-8")
            if args.html_file
            else fetch_public_page(args.source_url)
        )
        report = build_live_final_report(html=html, source_url=args.source_url)
    else:
        report = build_final_report()

    if args.comparables_file:
        report = enrich_with_comparables(
            report,
            load_comparables_payload(args.comparables_file),
        )
    if args.costs_file:
        report = enrich_with_costs(
            report,
            load_costs_payload(args.costs_file),
        )

    report = enrich_with_decision(report)
    paths = write_report_outputs(report, args.output_dir)
    for label, path in paths.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
