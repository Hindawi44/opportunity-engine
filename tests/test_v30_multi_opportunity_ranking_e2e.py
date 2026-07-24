from opportunity_engine.multi_opportunity_ranking import rank_evaluated_opportunities


def _ready(opportunity_id: str, profit: float, roi: float, quality: float) -> dict:
    return {
        "opportunity_id": opportunity_id,
        "decision_gate": "READY_FOR_FINANCIAL_REVIEW",
        "automatic_purchase_decision": False,
        "market_evidence_status": "COMPLETE",
        "cost_evidence_status": "COMPLETE",
        "verified_comparable_count": 3,
        "verified_cost_component_count": 6,
        "expected_profit_nok": profit,
        "roi_percent": roi,
        "evidence_completeness_score": 1.0,
        "comparable_quality_score": quality,
        "risk_level": "MEDIUM",
    }


def test_v30_filters_incomplete_and_ranks_ready_opportunities_deterministically():
    records = [
        _ready("opportunity-b", 22_000, 44.0, 0.82),
        {
            "opportunity_id": "live-auksjonen-berryalloc-route66-20260724",
            "decision_gate": "EVIDENCE_REQUIRED",
            "automatic_purchase_decision": False,
            "market_evidence_status": "INCOMPLETE",
            "cost_evidence_status": "INCOMPLETE",
            "verified_comparable_count": 0,
            "verified_cost_component_count": 1,
            "expected_profit_nok": None,
            "roi_percent": None,
        },
        _ready("opportunity-a", 18_000, 60.0, 0.88),
        _ready("opportunity-c", 26_000, 44.0, 0.91),
    ]

    report = rank_evaluated_opportunities(records, analysis_date="2026-07-24T12:00:00Z")

    assert report["schema_version"] == "3.0"
    assert report["opportunities_processed"] == 4
    assert report["ready_for_financial_review"] == 3
    assert report["excluded_count"] == 1
    assert [item["opportunity_id"] for item in report["rankings"]] == [
        "opportunity-a",
        "opportunity-c",
        "opportunity-b",
    ]
    assert [item["rank"] for item in report["rankings"]] == [1, 2, 3]
    assert report["excluded"][0]["opportunity_id"] == "live-auksjonen-berryalloc-route66-20260724"
    assert report["automatic_purchase_decision"] is False
    assert report["status"] == "PASS"


def test_v30_never_promotes_incomplete_or_automatic_purchase_records():
    report = rank_evaluated_opportunities([
        {
            **_ready("unsafe", 10_000, 50.0, 0.9),
            "automatic_purchase_decision": True,
        },
        {
            **_ready("missing-comparable", 10_000, 50.0, 0.9),
            "verified_comparable_count": 2,
        },
    ])

    assert report["ready_for_financial_review"] == 0
    assert report["excluded_count"] == 2
    assert report["rankings"] == []
    assert report["automatic_purchase_decision"] is False
    assert report["status"] == "NO_ELIGIBLE_OPPORTUNITIES"
