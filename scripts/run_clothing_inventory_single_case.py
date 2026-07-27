"""Execute one Clothing Inventory case end to end.

The default mode reuses the preserved deterministic case. Live mode fetches the
existing public Auksjonen category, selects exactly one clothing-related listing,
and passes only observed source facts through the approved Discovery, Opportunity
Dossier, eligibility, verified market-comparables, and financial-integration
contracts. Missing evidence remains explicit and no automatic commercial or
financial action is performed.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from opportunity_engine.discovery.classifier import classify_candidate, to_canonical_opportunity
from opportunity_engine.discovery.e2e_checkpoint import (
    CheckpointOutcome,
    build_opportunity_dossier,
    evaluate_analysis_eligibility,
)
from opportunity_engine.discovery.models import DiscoveryCandidate
from opportunity_engine.discovery.real_case import run_real_clothing_inventory_case
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


def select_one_clothing_listing(listings: list[RawListing]) -> RawListing:
    """Select exactly one deterministic clothing listing from parsed live results."""
    matches = sorted(
        (listing for listing in listings if is_clothing_listing(listing)),
        key=lambda listing: listing.listing_id,
    )
    if not matches:
        raise ValueError("No clothing-related Auksjonen listing was found")
    return matches[0]


def candidate_from_live_listing(
    listing: RawListing,
    *,
    observed_at: str | None = None,
) -> DiscoveryCandidate:
    """Convert one observed listing without inventing quantity or contact facts."""
    timestamp = observed_at or datetime.now(timezone.utc).isoformat()
    return DiscoveryCandidate(
        title=listing.title,
        url=listing.url,
        source="AUKSJONEN_NO_LIVE_LISTING",
        discovered_at=timestamp,
        text=f"Auksjonen.no public auction clothing listing: {listing.title}",
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
    """Parse a public page and execute exactly one observed clothing candidate."""
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
            "selected_listing_id": selected.listing_id,
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


def enrich_with_comparables(
    report: dict[str, Any],
    comparables_payload: object,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Attach explicit verified comparisons using the existing V2.8/V2.10 contracts."""
    return apply_verified_market_comparables(report, comparables_payload, now=now)


def build_operator_summary(report: dict[str, Any]) -> str:
    """Create a concise operator-readable summary from the final report."""
    dossier = report["dossier"]
    eligibility = report["eligibility"]
    confirmed = dossier["confirmed_facts"]
    seller_claims = dossier["seller_claims"]
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

    financial = report.get("financial_integration")
    if isinstance(financial, dict):
        lines.append(f"Financial decision gate: {financial.get('decision_gate', 'unknown')}")

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
        help="Fetch the existing public Auksjonen category and select one clothing listing.",
    )
    parser.add_argument("--source-url", default=AUKSJONEN_CATEGORY_URL)
    parser.add_argument(
        "--html-file",
        type=Path,
        help="Use a preserved HTML page instead of network access; implies live parsing.",
    )
    parser.add_argument(
        "--comparables-file",
        type=Path,
        help=(
            "Optional JSON package of explicit verified market comparisons. "
            "Only records with verified=true are eligible."
        ),
    )
    args = parser.parse_args()

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

    paths = write_report_outputs(report, args.output_dir)
    for label, path in paths.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
