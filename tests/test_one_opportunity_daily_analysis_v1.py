from datetime import datetime, timezone

from opportunity_engine.discovery.one_opportunity_daily_analysis import (
    build_daily_analysis,
    render_daily_analysis,
    select_one,
)


NOW = datetime(2026, 8, 3, 11, 30, tzinfo=timezone.utc)
OPPORTUNITY_ID = "https://ny.auksjonen.no/auksjon/torget/test/528194"


def _candidate(identity: str = OPPORTUNITY_ID, *, score: float = 70.0) -> dict:
    return {
        "opportunity_identity": identity,
        "title": "10 stk arbeidsplagg",
        "market_code": "NO",
        "currency": "NOK",
        "source_names": ["Auksjonen.no"],
        "canonical_url": identity,
        "listing_status": "ACTIVE",
        "workflow_status": "ACTIVE_OPPORTUNITY",
        "analysis_eligible": True,
        "top5_eligible": True,
        "discovery_score": score,
    }


def _checkpoint(records: list[dict], preferred: str | None = OPPORTUNITY_ID) -> dict:
    action = {"opportunity_identity": preferred} if preferred else {}
    return {
        "domain": "CLOTHING_INVENTORY",
        "deduplicated_opportunities": records,
        "next_human_action": action,
    }


def _detail() -> dict:
    return {
        "opportunity_id": OPPORTUNITY_ID,
        "title": "10 stk arbeidsplagg",
        "source_url": OPPORTUNITY_ID,
        "currency": "NOK",
        "price": 5000.0,
        "quantity": 10,
        "location": "7800 Namsos",
        "metadata": {
            "analysis_tasks": [
                "confirm quantity and condition from the exact item page",
                "calculate final payable price including auction fees and VAT",
                "calculate pickup or delivery logistics",
                "document conservative resale-market evidence",
            ]
        },
    }


def test_selects_checkpoint_preferred_active_opportunity() -> None:
    other = _candidate("other", score=99)
    selected, reason, count = select_one(_checkpoint([other, _candidate()]))
    assert selected is not None
    assert selected["opportunity_identity"] == OPPORTUNITY_ID
    assert reason == "CHECKPOINT_NEXT_HUMAN_ACTION"
    assert count == 2


def test_builds_one_grounded_analysis_without_inventing_financials() -> None:
    report = build_daily_analysis(
        _checkpoint([_candidate()]),
        detail_records={OPPORTUNITY_ID: _detail()},
        generated_at=NOW,
    )
    assert report["selection_status"] == "SELECTED"
    assert report["eligible_candidate_count"] == 1
    assert report["selected_opportunity"]["opportunity_identity"] == OPPORTUNITY_ID
    assert report["analysis_state"] == "REQUIRES_COMMERCIAL_INPUTS"
    assert report["known_facts"]["source_price"] == {
        "amount": 5000.0,
        "currency": "NOK",
        "kind": "SOURCE_PRICE",
        "is_final_payable_price": False,
    }
    assert report["known_facts"]["quantity"] == 10.0
    assert len(report["required_analysis_tasks"]) == 4
    assert report["financial_readiness"]["total_cost_nok"] is None
    assert report["financial_readiness"]["expected_profit_nok"] is None
    assert report["financial_readiness"]["maximum_purchase_price_nok"] is None
    assert report["next_human_action"]["action"] == "COMPLETE_ANALYSIS_INPUTS"
    assert report["automatic_purchase"] is False
    assert report["automatic_bid"] is False


def test_zero_result_is_truthful_when_no_active_opportunity_exists() -> None:
    blocked = _candidate()
    blocked["workflow_status"] = "REQUIRES_VERIFICATION"
    blocked["analysis_eligible"] = False
    report = build_daily_analysis(_checkpoint([blocked]), generated_at=NOW)
    assert report["selection_status"] == "VALID_ZERO_RESULT"
    assert report["selected_opportunity"] is None
    assert report["next_human_action"]["action"] == "WAIT_FOR_ACTIVE_OPPORTUNITY"
    assert report["financial_readiness"]["expected_profit_nok"] is None


def test_ready_state_requires_all_explicit_commercial_values() -> None:
    detail = _detail()
    detail["metadata"].update(
        {
            "final_payable_price_nok": 7000,
            "transport_nok": 1000,
            "conservative_resale_nok": 12000,
            "resale_comparables": [{"id": "c1"}],
        }
    )
    report = build_daily_analysis(
        _checkpoint([_candidate()]),
        detail_records={OPPORTUNITY_ID: detail},
        generated_at=NOW,
    )
    assert report["analysis_state"] == "READY_FOR_FINANCIAL_ENGINE"
    assert report["required_analysis_tasks"] == []
    assert report["next_human_action"]["action"] == "RUN_FINANCIAL_DECISION_ENGINE"
    assert report["financial_readiness"]["expected_profit_nok"] is None


def test_phone_summary_contains_exactly_one_human_action() -> None:
    report = build_daily_analysis(
        _checkpoint([_candidate()]),
        detail_records={OPPORTUNITY_ID: _detail()},
        generated_at=NOW,
    )
    summary = render_daily_analysis(report)
    assert summary.count("الإجراء البشري الوحيد:") == 1
    assert "COMPLETE_ANALYSIS_INPUTS" in summary
    assert "لا شراء، لا مزايدة" in summary
