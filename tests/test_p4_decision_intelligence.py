from scripts.build_decision_intelligence import _decision


def _base():
    return {
        "opportunity_id": "x1",
        "title": "Test",
        "asking_price_nok": 10_000.0,
        "opportunity_score": 80.0,
        "recommendation": "BUY_REVIEW",
        "decision": "REVIEW_NUMBERS",
        "total_cost_nok": 12_000.0,
        "conservative_resale_value_nok": 20_000.0,
        "expected_profit_nok": 8_000.0,
        "roi_percent": 66.67,
        "missing_evidence": [],
    }


def test_complete_profitable_opportunity_becomes_buy_review():
    result = _decision(_base())
    assert result["final_decision"] == "BUY_REVIEW"
    assert result["maximum_safe_bid_nok"] == 14_000.0
    assert result["automatic_purchase"] is False
    assert result["requires_human_approval"] is True


def test_missing_evidence_never_becomes_buy_review():
    item = _base()
    item["decision"] = "EVIDENCE_REQUIRED"
    item["missing_evidence"] = ["transport_cost_nok"]
    item["total_cost_nok"] = None
    item["expected_profit_nok"] = None
    item["roi_percent"] = None
    result = _decision(item)
    assert result["final_decision"] == "WATCH"
    assert result["maximum_safe_bid_nok"] is None
    assert result["decision_confidence"] == "LOW"


def test_negative_profit_is_rejected():
    item = _base()
    item["expected_profit_nok"] = -500.0
    item["roi_percent"] = -4.0
    result = _decision(item)
    assert result["final_decision"] == "REJECT"


def test_price_above_safe_bid_is_watch():
    item = _base()
    item["asking_price_nok"] = 16_000.0
    item["total_cost_nok"] = 18_000.0
    item["expected_profit_nok"] = 2_000.0
    item["roi_percent"] = 30.0
    result = _decision(item)
    assert result["maximum_safe_bid_nok"] == 14_000.0
    assert result["final_decision"] == "WATCH"
