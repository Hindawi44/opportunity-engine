import pytest

from opportunity_engine.ods.decision import (
    DecisionInputs,
    ExecutiveDecision,
    build_executive_decision,
)
from opportunity_engine.ods.financial import FinancialInputs, build_financial_report


def _financial(*, units: float = 50, margin_cost: float = 400):
    return build_financial_report(
        FinancialInputs(
            startup_cost=100_000,
            monthly_fixed_cost=20_000,
            unit_price=1_000,
            unit_variable_cost=margin_cost,
            monthly_units=units,
            working_capital_months=3,
        )
    )


def test_go_requires_complete_strong_evidence_and_viable_finance():
    report = build_executive_decision(
        DecisionInputs(
            opportunity_confidence=86,
            validation_readiness=80,
            evidence_quality=90,
            market_health=78,
            financial_report=_financial(),
        )
    )

    assert report.decision is ExecutiveDecision.GO
    assert report.score >= 75
    assert not report.missing_evidence
    assert report.first_7_days


def test_wait_when_evidence_is_missing():
    report = build_executive_decision(
        DecisionInputs(
            opportunity_confidence=85,
            validation_readiness=75,
        )
    )

    assert report.decision is ExecutiveDecision.WAIT
    assert "financial assumptions" in report.missing_evidence
    assert report.blockers


def test_wait_when_base_financial_scenario_is_unprofitable():
    report = build_executive_decision(
        DecisionInputs(
            opportunity_confidence=88,
            validation_readiness=82,
            evidence_quality=90,
            market_health=80,
            financial_report=_financial(units=20),
        )
    )

    assert report.decision is ExecutiveDecision.WAIT
    assert any("does not produce" in item for item in report.blockers)


def test_rejects_weak_confidence_or_validation():
    report = build_executive_decision(
        DecisionInputs(
            opportunity_confidence=40,
            validation_readiness=70,
            evidence_quality=90,
            market_health=80,
            financial_report=_financial(),
        )
    )

    assert report.decision is ExecutiveDecision.REJECT
    assert "stop new spending" in report.first_7_days[0]


def test_invalid_scores_are_rejected():
    with pytest.raises(ValueError, match="between 0 and 100"):
        DecisionInputs(opportunity_confidence=101, validation_readiness=50)
