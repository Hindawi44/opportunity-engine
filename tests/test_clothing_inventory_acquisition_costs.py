import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.run_clothing_inventory_single_case import (
    build_final_report,
    enrich_with_comparables,
    enrich_with_costs,
    write_report_outputs,
)


def _verified_comparables() -> dict[str, object]:
    return {
        "comparables": [
            {
                "title": "Univern Hi-Vis arbeidsjakke comparable A",
                "url": "https://www.finn.no/bap/forsale/ad.html?finnkode=200001",
                "price_nok": 1800,
                "source_name": "FINN.no",
                "observed_at": "2026-07-26T12:00:00Z",
                "similarity_score": 0.86,
                "verified": True,
            },
            {
                "title": "Univern flammehemmende arbeidsjakke comparable B",
                "url": "https://www.auksjonen.no/auksjoner/arbeidsjakke/200002",
                "price_nok": 2000,
                "source_name": "Auksjonen.no",
                "observed_at": "2026-07-26T12:05:00Z",
                "similarity_score": 0.82,
                "verified": True,
            },
            {
                "title": "Hi-Vis antistatisk arbeidsjakke comparable C",
                "url": "https://arbeidsklaer.no/produkter/jakke-200003",
                "price_nok": 2200,
                "source_name": "Arbeidsklaer.no",
                "observed_at": "2026-07-26T12:10:00Z",
                "similarity_score": 0.78,
                "verified": True,
            },
        ]
    }


def _verified_costs() -> dict[str, object]:
    return {
        "costs": [
            {
                "component": "auction_price",
                "amount_nok": 200,
                "currency": "NOK",
                "source_url": "https://www.auksjonen.no/auksjoner/arbeidsjakke/200002",
                "source_name": "Auksjonen.no",
                "observed_at": "2026-07-26T12:15:00Z",
                "basis": "Published final auction price",
                "zero_cost_confirmed": False,
                "verified": True,
            },
            {
                "component": "auction_fee",
                "amount_nok": 40,
                "currency": "NOK",
                "source_url": "https://www.auksjonen.no/kundeservice/vilkar",
                "source_name": "Auksjonen.no terms",
                "observed_at": "2026-07-26T12:16:00Z",
                "basis": "Published buyer fee for the selected lot",
                "zero_cost_confirmed": False,
                "verified": True,
            },
            {
                "component": "vat",
                "amount_nok": 60,
                "currency": "NOK",
                "source_url": "https://www.auksjonen.no/kundeservice/vilkar",
                "source_name": "Auksjonen.no terms",
                "observed_at": "2026-07-26T12:17:00Z",
                "basis": "Published VAT amount for the selected lot",
                "zero_cost_confirmed": False,
                "verified": True,
            },
            {
                "component": "transport",
                "amount_nok": 350,
                "currency": "NOK",
                "source_url": "https://www.bring.no/tjenester/pakker-og-gods",
                "source_name": "Bring quote",
                "observed_at": "2026-07-26T12:18:00Z",
                "basis": "Written transport quote for collection and delivery",
                "zero_cost_confirmed": False,
                "verified": True,
            },
            {
                "component": "dismantling",
                "amount_nok": 0,
                "currency": "NOK",
                "source_url": "https://www.auksjonen.no/auksjoner/arbeidsjakke/200002",
                "source_name": "Auksjonen.no lot terms",
                "observed_at": "2026-07-26T12:19:00Z",
                "basis": "No dismantling is required for boxed clothing",
                "zero_cost_confirmed": True,
                "verified": True,
            },
            {
                "component": "storage",
                "amount_nok": 0,
                "currency": "NOK",
                "source_url": "https://namsos.kommune.no/naering",
                "source_name": "Operator storage confirmation",
                "observed_at": "2026-07-26T12:20:00Z",
                "basis": "Existing shop storage is available without incremental cost",
                "zero_cost_confirmed": True,
                "verified": True,
            },
        ]
    }


def _market_ready_report() -> dict[str, object]:
    return enrich_with_comparables(
        build_final_report(),
        _verified_comparables(),
        now=datetime(2026, 7, 27, tzinfo=timezone.utc),
    )


def test_complete_verified_costs_reach_ready_for_financial_review() -> None:
    report = enrich_with_costs(_market_ready_report(), _verified_costs())

    costs = report["acquisition_cost_evidence"]
    assert costs["status"] == "COMPLETE"
    assert costs["accepted_count"] == 6
    assert costs["true_acquisition_cost_nok"] == 650.0
    assert costs["missing_required_cost_fields"] == []

    financial = report["financial_integration"]
    assert financial["verified_comparable_count"] == 3
    assert financial["verified_cost_component_count"] == 6
    assert financial["market_evidence_status"] == "COMPLETE"
    assert financial["cost_evidence_status"] == "COMPLETE"
    assert financial["true_acquisition_cost_nok"] == 650.0
    assert financial["conservative_resale_value_nok"] == 1800.0
    assert financial["expected_profit_nok"] == 1150.0
    assert financial["roi_percent"] == 176.92
    assert financial["decision_gate"] == "READY_FOR_FINANCIAL_REVIEW"
    assert report["final_outcome"] == "ANALYSIS_READY"
    assert report["analysis_invoked"] is True

    assert report["automatic_purchase_decision"] is False
    assert report["automatic_bid"] is False
    assert report["automatic_contact"] is False
    assert report["automatic_payment"] is False


def test_unverified_cost_component_keeps_evidence_required() -> None:
    payload = _verified_costs()
    payload["costs"][3]["verified"] = False  # type: ignore[index]

    report = enrich_with_costs(_market_ready_report(), payload)

    costs = report["acquisition_cost_evidence"]
    assert costs["status"] == "INCOMPLETE"
    assert costs["accepted_count"] == 5
    assert "transport_cost_nok" in costs["missing_required_cost_fields"]

    financial = report["financial_integration"]
    assert financial["cost_evidence_status"] == "INCOMPLETE"
    assert "transport_cost_nok" in financial["missing_required_evidence"]
    assert financial["expected_profit_nok"] is None
    assert financial["roi_percent"] is None
    assert financial["decision_gate"] == "EVIDENCE_REQUIRED"
    assert report["final_outcome"] == "EVIDENCE_REQUIRED"


def test_cost_enriched_outputs_remain_machine_and_operator_readable(
    tmp_path: Path,
) -> None:
    report = enrich_with_costs(_market_ready_report(), _verified_costs())
    paths = write_report_outputs(report, tmp_path)

    stored = json.loads(paths["report"].read_text(encoding="utf-8"))
    summary = paths["summary"].read_text(encoding="utf-8")

    assert stored["acquisition_cost_evidence"]["accepted_count"] == 6
    assert stored["financial_integration"]["decision_gate"] == (
        "READY_FOR_FINANCIAL_REVIEW"
    )
    assert "Verified cost components: 6" in summary
    assert "Acquisition-cost status: COMPLETE" in summary
    assert "True acquisition cost NOK: 650.0" in summary
    assert "Expected profit NOK: 1150.0" in summary
    assert "ROI percent: 176.92" in summary
    assert "Automatic purchase/bid/contact/payment: false" in summary
