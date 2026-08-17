from opportunity_engine.ods.market_pricing import MarketPriceReport
from opportunity_engine.ods.opportunity_profit import (
    OpportunityDecisionPolicy,
    OpportunityProfitDecisionEngine,
)
from opportunity_engine.ods.opportunity_value import (
    OpportunityValueEngine,
    OpportunityValuePolicy,
    OpportunityValueReport,
)
from opportunity_engine.ods.real_cost import RealCostReport


def _market(**overrides):
    values = dict(
        opportunity_id="value-owner-1",
        comparable_count=4,
        low_price_nok=18000,
        median_price_nok=22000,
        high_price_nok=25000,
        conservative_resale_nok=24000,
        confidence="high",
        comparable_ids=("a", "b", "c", "d"),
        warnings=(),
    )
    values.update(overrides)
    return MarketPriceReport(**values)


def _costs(**overrides):
    values = dict(
        purchase_price_nok=10000,
        auction_fee_nok=1500,
        vat_nok=0,
        direct_costs_nok=3500,
        contingency_nok=0,
        total_cost_nok=15000,
        missing_fields=(),
        warnings=(),
        is_complete=True,
    )
    values.update(overrides)
    return RealCostReport(**values)


def test_value_engine_is_single_owner_of_financial_math() -> None:
    value = OpportunityValueEngine().evaluate(_market(), _costs())

    assert value.expected_profit_nok == 9000
    assert value.roi == 0.6
    assert value.margin_on_resale == 0.375
    assert value.maximum_total_cost_nok == 17777.78
    assert value.maximum_purchase_price_nok == 12777.78


def test_decision_engine_consumes_canonical_value_without_recalculation() -> None:
    value = OpportunityValueReport(
        opportunity_id="value-owner-2",
        conservative_resale_nok=100000,
        total_cost_nok=1000,
        expected_profit_nok=-1,
        roi=-0.001,
        margin_on_resale=-0.00001,
        maximum_total_cost_nok=500,
        maximum_purchase_price_nok=400,
        confidence="high",
        blockers=(),
        warnings=(),
    )

    decision = OpportunityProfitDecisionEngine().decide(value)

    # If Decision recalculated from resale/total this would become a BUY.
    assert decision.decision == "reject"
    assert decision.expected_profit_nok == -1
    assert decision.roi == -0.001
    assert decision.maximum_total_cost_nok == 500
    assert decision.maximum_purchase_price_nok == 400


def test_max_bid_target_belongs_to_value_policy_not_decision_policy() -> None:
    assert OpportunityValuePolicy().target_roi_for_max_bid == 0.35
    assert not hasattr(OpportunityDecisionPolicy(), "target_roi_for_max_bid")


def test_incomplete_value_stays_non_actionable_monitor() -> None:
    value = OpportunityValueEngine().evaluate(
        _market(conservative_resale_nok=None, confidence="insufficient"),
        _costs(total_cost_nok=None, missing_fields=("transport_nok",), is_complete=False),
    )

    decision = OpportunityProfitDecisionEngine().decide(value)

    assert decision.decision == "monitor"
    assert decision.is_actionable is False
    assert "conservative_resale_nok" in decision.blockers
    assert "total_cost_nok" in decision.blockers
    assert "cost:transport_nok" in decision.blockers
