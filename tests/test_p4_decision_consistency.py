from scripts.build_decision_intelligence import _decision
from scripts.sync_final_decisions import sync_alerts, sync_dashboard


def incomplete_item():
    return {
        "opportunity_id": "opp-1",
        "title": "Test",
        "asking_price_nok": 5_000.0,
        "opportunity_score": 30.0,
        "recommendation": "REJECT",
        "recommendation_ar": "رفض",
        "decision": "EVIDENCE_REQUIRED",
        "missing_evidence": ["transport_cost_nok", "three_verified_market_comparables"],
        "total_cost_nok": None,
        "conservative_resale_value_nok": None,
        "expected_profit_nok": None,
        "roi_percent": None,
    }


def test_final_decision_is_the_only_official_recommendation():
    result = _decision(incomplete_item())
    assert result["final_decision"] == "WATCH"
    assert result["recommendation"] == result["final_decision"]
    assert result["recommendation_ar"] == result["final_decision_ar"]
    assert result["official_decision_field"] == "final_decision"


def test_missing_evidence_warning_is_arabic_not_raw_keys():
    result = _decision(incomplete_item())
    warning = " ".join(result["decision_warnings_ar"])
    assert "تكلفة النقل" in warning
    assert "ثلاث مقارنات سوقية موثقة" in warning
    assert "transport_cost_nok" not in warning
    assert "three_verified_market_comparables" not in warning


def test_dashboard_reads_canonical_final_decision():
    decision = _decision(incomplete_item())
    dashboard = {"rows": [{"opportunity_id": "opp-1", "decision": "REJECT"}]}
    result = sync_dashboard(dashboard, {"opp-1": decision})
    row = result["rows"][0]
    assert row["final_decision"] == "WATCH"
    assert row["decision"] == "WATCH"
    assert row["recommendation"] == "WATCH"
    assert row["decision_source"] == "P4.1_final_decision"


def test_alerts_use_final_decision_and_drop_rejected_items():
    watch = _decision(incomplete_item())
    alerts = {"alerts": [{"opportunity_id": "opp-1", "recommendation": "REJECT"}]}
    result = sync_alerts(alerts, {"opp-1": watch})
    assert result["alerts"][0]["recommendation"] == "WATCH"
    assert result["alerts"][0]["final_decision"] == "WATCH"

    rejected_input = incomplete_item()
    rejected_input.update({
        "decision": "REVIEW_NUMBERS",
        "missing_evidence": [],
        "total_cost_nok": 10_000.0,
        "conservative_resale_value_nok": 8_000.0,
        "expected_profit_nok": -2_000.0,
        "roi_percent": -20.0,
    })
    rejected = _decision(rejected_input)
    removed = sync_alerts(alerts, {"opp-1": rejected})
    assert removed["alerts"] == []
