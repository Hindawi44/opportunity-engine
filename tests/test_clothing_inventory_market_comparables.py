import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.run_clothing_inventory_single_case import (
    build_final_report,
    enrich_with_comparables,
    write_report_outputs,
)


def _verified_comparables() -> dict[str, object]:
    return {
        "comparables": [
            {
                "title": "Univern Hi-Vis arbeidsjakke comparable A",
                "url": "https://www.finn.no/bap/forsale/ad.html?finnkode=100001",
                "price_nok": 1800,
                "source_name": "FINN.no",
                "observed_at": "2026-07-26T12:00:00Z",
                "similarity_score": 0.86,
                "verified": True,
            },
            {
                "title": "Univern flammehemmende arbeidsjakke comparable B",
                "url": "https://www.auksjonen.no/auksjoner/arbeidsjakke/100002",
                "price_nok": 2000,
                "source_name": "Auksjonen.no",
                "observed_at": "2026-07-26T12:05:00Z",
                "similarity_score": 0.82,
                "verified": True,
            },
            {
                "title": "Hi-Vis antistatisk arbeidsjakke comparable C",
                "url": "https://arbeidsklaer.no/produkter/jakke-100003",
                "price_nok": 2200,
                "source_name": "Arbeidsklaer.no",
                "observed_at": "2026-07-26T12:10:00Z",
                "similarity_score": 0.78,
                "verified": True,
            },
        ]
    }


def test_three_verified_comparables_complete_market_gate_without_inventing_costs() -> None:
    report = enrich_with_comparables(
        build_final_report(),
        _verified_comparables(),
        now=datetime(2026, 7, 27, tzinfo=timezone.utc),
    )

    market = report["market_comparables"]
    assert market["status"] == "COMPLETE"
    assert market["accepted_count"] == 3
    assert market["conservative_market_value_nok"] == 1900.0
    assert "market comparable evidence" not in report["dossier"]["missing_evidence"]
    assert report["eligibility"]["eligible_for_analysis"] is True

    financial = report["financial_integration"]
    assert report["analysis_invoked"] is True
    assert financial["verified_comparable_count"] == 3
    assert financial["market_evidence_status"] == "COMPLETE"
    assert financial["cost_evidence_status"] == "INCOMPLETE"
    assert financial["expected_profit_nok"] is None
    assert report["final_outcome"] == "EVIDENCE_REQUIRED"

    assert report["automatic_purchase_decision"] is False
    assert report["automatic_bid"] is False
    assert report["automatic_contact"] is False
    assert report["automatic_payment"] is False


def test_unverified_search_candidates_do_not_cross_market_gate() -> None:
    payload = _verified_comparables()
    for comparable in payload["comparables"]:  # type: ignore[index]
        comparable["verified"] = False

    report = enrich_with_comparables(
        build_final_report(),
        payload,
        now=datetime(2026, 7, 27, tzinfo=timezone.utc),
    )

    assert report["market_comparables"]["status"] == "INCOMPLETE"
    assert report["market_comparables"]["accepted_count"] == 0
    assert report["eligibility"]["eligible_for_analysis"] is False
    assert report["analysis_invoked"] is False
    assert report["financial_integration"]["reason"] == "eligibility_gate_blocked"
    assert report["final_outcome"] == "EVIDENCE_REQUIRED"


def test_comparable_enriched_outputs_remain_machine_and_operator_readable(
    tmp_path: Path,
) -> None:
    report = enrich_with_comparables(
        build_final_report(),
        _verified_comparables(),
        now=datetime(2026, 7, 27, tzinfo=timezone.utc),
    )
    paths = write_report_outputs(report, tmp_path)

    stored = json.loads(paths["report"].read_text(encoding="utf-8"))
    summary = paths["summary"].read_text(encoding="utf-8")

    assert stored["market_comparables"]["accepted_count"] == 3
    assert stored["financial_integration"]["decision_gate"] == "EVIDENCE_REQUIRED"
    assert "Verified comparables: 3" in summary
    assert "Market-comparable status: COMPLETE" in summary
    assert "Financial decision gate: EVIDENCE_REQUIRED" in summary
    assert "Automatic purchase/bid/contact/payment: false" in summary
