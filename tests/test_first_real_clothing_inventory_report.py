import json
from pathlib import Path

from scripts.run_first_real_clothing_inventory_report import (
    DEFAULT_INPUT_DIR,
    build_first_real_report,
)
from scripts.run_clothing_inventory_single_case import (
    build_operator_summary,
    write_report_outputs,
)


def test_first_real_report_is_traceable_and_remains_watch() -> None:
    report = build_first_real_report()

    confirmed = report["dossier"]["confirmed_facts"]
    claims = report["dossier"]["seller_claims"]
    assert confirmed["source_url"] == "https://www.auksjonen.no/auksjoner/overskudd_klaer"
    assert "Blåkläder 3463" in confirmed["source_title"]
    assert claims["quantity"] == 25
    assert claims["asking_price_nok"] == 1000.0
    assert report["canonical_opportunity"]["source"]["listing_status"] == "ENDED"

    market = report["market_comparables"]
    assert market["status"] == "COMPLETE"
    assert market["accepted_count"] == 3
    assert market["conservative_market_value_nok"] == 24975.0
    assert len({item["url"] for item in market["accepted"]}) == 3

    costs = report["acquisition_cost_evidence"]
    assert costs["status"] == "INCOMPLETE"
    assert costs["accepted_count"] == 1
    assert costs["true_acquisition_cost_nok"] is None
    assert costs["missing_required_cost_fields"] == [
        "auction_fee_nok",
        "vat_nok",
        "transport_cost_nok",
        "dismantling_cost_nok",
        "storage_cost_nok",
    ]

    financial = report["financial_integration"]
    assert financial["decision_gate"] == "EVIDENCE_REQUIRED"
    assert financial["expected_profit_nok"] is None
    assert financial["roi_percent"] is None

    assert report["final_outcome"] == "EVIDENCE_REQUIRED"
    assert report["final_decision"] == "WATCH"
    assert report["decision_intelligence"]["decision_confidence"] == "LOW"
    assert report["requires_human_approval"] is False
    assert report["automatic_purchase_decision"] is False
    assert report["automatic_bid"] is False
    assert report["automatic_contact"] is False
    assert report["automatic_payment"] is False


def test_first_real_report_inputs_expose_methodology_and_unknown_costs() -> None:
    comparables = json.loads(
        (DEFAULT_INPUT_DIR / "verified-comparables.json").read_text(encoding="utf-8")
    )
    costs = json.loads(
        (DEFAULT_INPUT_DIR / "verified-acquisition-costs.json").read_text(
            encoding="utf-8"
        )
    )

    assert comparables["valuation_method"] == "lot_equivalent_from_published_unit_price"
    assert "new-retail ceiling" in comparables["warning"]
    assert all(item["verified"] is True for item in comparables["comparables"])
    assert [item["quantity_multiplier"] for item in comparables["comparables"]] == [
        25,
        25,
        25,
    ]

    assert len(costs["costs"]) == 1
    assert costs["costs"][0]["component"] == "auction_price"
    assert "remain unknown" in costs["status_note"]


def test_first_real_report_writes_operator_outputs(tmp_path: Path) -> None:
    report = build_first_real_report()
    paths = write_report_outputs(report, tmp_path)

    stored = json.loads(paths["report"].read_text(encoding="utf-8"))
    summary = paths["summary"].read_text(encoding="utf-8")

    assert stored["real_execution"]["sale_status"] == "ENDED"
    assert stored["final_decision"] == "WATCH"
    assert "Final decision: WATCH" in summary
    assert "Verified comparables: 3" in summary
    assert "Verified cost components: 1" in summary
    assert "Automatic purchase/bid/contact/payment: false" in summary
    assert build_operator_summary(report) == summary
