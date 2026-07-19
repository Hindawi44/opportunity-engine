from opportunity_engine.ods.market_pricing import MarketPriceReport
from opportunity_engine.ods.opportunity_profit import (
    OpportunityDecisionPolicy,
    OpportunityProfitDecisionEngine,
)
from opportunity_engine.ods.real_cost import RealCostReport


def _market(**overrides):
    values = dict(
        opportunity_id="unified-auksjonen-123",
        comparable_count=4,
        low_price_nok=18000,
        median_price_nok=22000,
        high_price_nok=25000,
        conservative_resale_nok=20000,
        confidence="medium",
        comparable_ids=("a", "b", "c", "d"),
        warnings=(),
    )
    values.update(overrides)
    return MarketPriceReport(**values)


def _costs(**overrides):
    values = dict(
        purchase_price_nok=10000,
        auction_fee_nok=1500,
        vat_nok=2875,
        direct_costs_nok=1000,
        contingency_nok=375,
        total_cost_nok=15750,
        missing_fields=(),
        warnings=(),
        is_complete=True,
    )
    values.update(overrides)
    return RealCostReport(**values)


def test_strong_profitable_opportunity_is_buy() -> None:
    result = OpportunityProfitDecisionEngine().decide(
        _market(conservative_resale_nok=24000, confidence="high"),
        _costs(total_cost_nok=15000),
    )

    assert result.decision == "buy"
    assert result.decision_label == "🟢 اشترِ"
    assert result.expected_profit_nok == 9000
    assert result.roi == 0.6
    assert result.is_actionable is True


def test_negative_profit_is_rejected() -> None:
    result = OpportunityProfitDecisionEngine().decide(
        _market(conservative_resale_nok=14000),
        _costs(total_cost_nok=15000),
    )

    assert result.decision == "reject"
    assert result.expected_profit_nok == -1000


def test_incomplete_inputs_are_monitor_only() -> None:
    result = OpportunityProfitDecisionEngine().decide(
        _market(conservative_resale_nok=None, confidence="insufficient"),
        _costs(total_cost_nok=None, missing_fields=("transport_nok",), is_complete=False),
    )

    assert result.decision == "monitor"
    assert result.is_actionable is False
    assert "conservative_resale_nok" in result.blockers
    assert "total_cost_nok" in result.blockers
    assert "cost:transport_nok" in result.blockers


def test_maximum_purchase_price_excludes_known_non_purchase_costs() -> None:
    result = OpportunityProfitDecisionEngine().decide(
        _market(conservative_resale_nok=27000),
        _costs(purchase_price_nok=10000, total_cost_nok=15000),
    )

    # Maximum total cost at 35% target ROI is 20,000. Known non-purchase costs are 5,000.
    assert result.maximum_total_cost_nok == 20000
    assert result.maximum_purchase_price_nok == 15000


def test_policy_rejects_invalid_thresholds() -> None:
    try:
        OpportunityDecisionPolicy(strong_min_roi=0.2, monitor_min_roi=0.3)
    except ValueError as exc:
        assert "monitor_min_roi" in str(exc)
    else:
        raise AssertionError("invalid policy should fail")
