from opportunity_engine.ods.market_pricing import MarketPriceReport
from opportunity_engine.ods.opportunity_profit import OpportunityProfitDecisionEngine
from opportunity_engine.ods.opportunity_value import OpportunityValueEngine
from opportunity_engine.ods.real_cost import RealCostReport


OPPORTUNITY_ID = "finn-455975035"


def _market() -> MarketPriceReport:
    """Conservative normalized pair value from three used-market asking comparables.

    Source listing is a pair of round metal clothing racks. Comparable asking prices
    visible on the same FINN listing page were 750, 1,000 and 2,300 NOK per rack.
    Normalized to pairs: 1,500 / 2,000 / 4,600 NOK. The canonical conservative
    pair value is therefore 1,700 NOK (85% of the 2,000 NOK median), with low
    confidence because the price spread is wide.
    """
    return MarketPriceReport(
        opportunity_id=OPPORTUNITY_ID,
        comparable_count=3,
        low_price_nok=1500.0,
        median_price_nok=2000.0,
        high_price_nok=4600.0,
        conservative_resale_nok=1700.0,
        confidence="low",
        comparable_ids=(
            "finn-similar-metal-rack-750x2",
            "finn-similar-round-rack-1000x2",
            "finn-similar-round-rack-2300x2",
        ),
        warnings=("Comparable prices have a wide spread.",),
    )


def _costs(*, direct_costs_nok: float, total_cost_nok: float | None, complete: bool) -> RealCostReport:
    missing = () if complete else ("transport_nok",)
    return RealCostReport(
        purchase_price_nok=1000.0,
        auction_fee_nok=0.0,
        vat_nok=0.0,
        direct_costs_nok=direct_costs_nok,
        contingency_nok=0.0 if complete else None,
        total_cost_nok=total_cost_nok,
        missing_fields=missing,
        warnings=(),
        is_complete=complete,
    )


def test_live_shadow_001_missing_transport_fails_closed_to_monitor() -> None:
    value = OpportunityValueEngine().evaluate(
        _market(),
        _costs(direct_costs_nok=0.0, total_cost_nok=None, complete=False),
    )
    decision = OpportunityProfitDecisionEngine().decide(value)

    assert "cost:transport_nok" in value.blockers
    assert decision.decision == "monitor"
    assert decision.is_actionable is False


def test_live_shadow_001_even_zero_logistics_is_not_a_buy() -> None:
    value = OpportunityValueEngine().evaluate(
        _market(),
        _costs(direct_costs_nok=0.0, total_cost_nok=1000.0, complete=True),
    )
    decision = OpportunityProfitDecisionEngine().decide(value)

    assert value.expected_profit_nok == 700.0
    assert value.roi == 0.7
    assert value.confidence == "low"
    assert decision.decision == "monitor"
    assert decision.decision != "buy"


def test_live_shadow_001_rejects_once_extra_costs_reach_750_nok() -> None:
    value = OpportunityValueEngine().evaluate(
        _market(),
        _costs(direct_costs_nok=750.0, total_cost_nok=1750.0, complete=True),
    )
    decision = OpportunityProfitDecisionEngine().decide(value)

    assert value.expected_profit_nok == -50.0
    assert value.roi == -0.0286
    assert decision.decision == "reject"
