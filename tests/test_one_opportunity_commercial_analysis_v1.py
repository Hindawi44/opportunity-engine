import pytest

from opportunity_engine.discovery.one_opportunity_commercial_analysis import (
    CommercialInputError,
    apply_commercial_inputs,
    render_commercial_analysis,
)


OPPORTUNITY_ID = "https://ny.auksjonen.no/auksjon/torget/test/528194"


def _daily_analysis(*, source_price: float | None = 5000.0) -> dict:
    return {
        "schema_version": "one-opportunity-daily-analysis-1.0",
        "generated_at": "2026-08-03T12:00:00+00:00",
        "execution_mode": "MANUAL_READ_ONLY",
        "selection_status": "SELECTED",
        "selected_opportunity": {
            "opportunity_identity": OPPORTUNITY_ID,
            "workflow_status": "ACTIVE_OPPORTUNITY",
            "listing_status": "ACTIVE",
        },
        "analysis_state": "REQUIRES_COMMERCIAL_INPUTS",
        "known_facts": {
            "title": "10 stk arbeidsplagg",
            "market_code": "NO",
            "source_names": ["Auksjonen.no"],
            "source_price": {
                "amount": source_price,
                "currency": "NOK",
                "kind": "SOURCE_PRICE",
                "is_final_payable_price": False,
            },
        },
        "required_analysis_tasks": [],
        "financial_readiness": {"ready_for_financial_engine": False},
        "next_human_action": {
            "action": "COMPLETE_ANALYSIS_INPUTS",
            "opportunity_identity": OPPORTUNITY_ID,
        },
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def test_complete_inputs_run_existing_conservative_decision_engine() -> None:
    report = apply_commercial_inputs(
        _daily_analysis(),
        opportunity_identity=OPPORTUNITY_ID,
        quantity_condition_confirmed=True,
        final_payable_price_nok="7000",
        transport_nok="1000",
        conservative_resale_nok="12000",
        resale_comparable_count="3",
        review_note="Quantity and condition checked.",
    )
    assert report["analysis_state"] == "FINANCIAL_DECISION_COMPLETE"
    assert report["financial_readiness"]["total_cost_nok"] == 8000.0
    assert report["financial_readiness"]["expected_profit_nok"] == 4000.0
    assert report["financial_readiness"]["roi"] == 0.5
    assert report["financial_readiness"]["maximum_final_payable_price_nok"] == 7888.89
    assert report["financial_readiness"]["maximum_source_bid_nok"] is None
    assert report["financial_decision"]["decision"] == "BUY"
    assert report["next_human_action"]["action"] == "REVIEW_BUY_OR_BID_CANDIDATE"
    assert report["automatic_purchase"] is False
    assert report["automatic_bid"] is False


def test_low_comparable_count_cannot_produce_direct_buy() -> None:
    report = apply_commercial_inputs(
        _daily_analysis(),
        opportunity_identity=OPPORTUNITY_ID,
        quantity_condition_confirmed=True,
        final_payable_price_nok=7000,
        transport_nok=1000,
        conservative_resale_nok=12000,
        resale_comparable_count=1,
    )
    assert report["financial_decision"]["decision"] == "WATCH"
    assert report["financial_decision"]["confidence"] == "low"


def test_unconfirmed_quantity_blocks_financial_decision() -> None:
    report = apply_commercial_inputs(
        _daily_analysis(),
        opportunity_identity=OPPORTUNITY_ID,
        quantity_condition_confirmed=False,
        final_payable_price_nok=7000,
        transport_nok=0,
        conservative_resale_nok=12000,
        resale_comparable_count=3,
    )
    assert report["analysis_state"] == "REQUIRES_COMMERCIAL_INPUTS"
    assert report["financial_decision"] is None
    assert report["financial_readiness"]["total_cost_nok"] is None
    assert "confirm quantity and condition" in report["required_analysis_tasks"][0]


def test_wrong_opportunity_identity_is_rejected() -> None:
    with pytest.raises(CommercialInputError, match="do not match"):
        apply_commercial_inputs(
            _daily_analysis(),
            opportunity_identity="different",
            quantity_condition_confirmed=True,
            final_payable_price_nok=7000,
            transport_nok=1000,
            conservative_resale_nok=12000,
            resale_comparable_count=3,
        )


def test_invalid_or_negative_values_are_rejected() -> None:
    with pytest.raises(CommercialInputError, match="positive"):
        apply_commercial_inputs(
            _daily_analysis(),
            opportunity_identity=OPPORTUNITY_ID,
            quantity_condition_confirmed=True,
            final_payable_price_nok=0,
            transport_nok=1000,
            conservative_resale_nok=12000,
            resale_comparable_count=3,
        )


def test_zero_source_price_is_treated_as_missing() -> None:
    report = apply_commercial_inputs(
        _daily_analysis(source_price=0.0),
        opportunity_identity=OPPORTUNITY_ID,
        quantity_condition_confirmed=False,
        final_payable_price_nok=7000,
        transport_nok=1000,
        conservative_resale_nok=12000,
        resale_comparable_count=3,
    )
    assert report["known_facts"]["source_price"]["amount"] is None
    assert report["known_facts"]["source_price"]["kind"] == "UNKNOWN"
    assert report["known_facts"]["source_price"]["zero_value_treated_as_missing"] is True


def test_phone_summary_contains_one_human_action_and_financials() -> None:
    report = apply_commercial_inputs(
        _daily_analysis(),
        opportunity_identity=OPPORTUNITY_ID,
        quantity_condition_confirmed=True,
        final_payable_price_nok=7000,
        transport_nok=1000,
        conservative_resale_nok=12000,
        resale_comparable_count=3,
    )
    summary = render_commercial_analysis(report)
    assert summary.count("الإجراء البشري الوحيد:") == 1
    assert "إجمالي التكلفة: 8000.0 NOK" in summary
    assert "الربح المتوقع: 4000.0 NOK" in summary
    assert "لا شراء، لا مزايدة" in summary
