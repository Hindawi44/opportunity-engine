import pytest

from opportunity_engine.ods.decision import (
    DecisionInputs,
    ExecutiveDecision,
    advance_decision_candidate,
    build_executive_decision,
)
from opportunity_engine.ods.financial import FinancialInputs, build_financial_report
from opportunity_engine.ods.models import LifecycleState, OpportunityCandidate


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


def _opportunity(state: LifecycleState) -> OpportunityCandidate:
    return OpportunityCandidate(
        opportunity_id="opp-1",
        title="Example opportunity",
        description="Validated and financially assessed opportunity",
        category="test",
        evidence=("validation evidence", "financial evidence"),
        confidence=0.9,
        source_plugin="test",
        lifecycle_state=state,
    )


def test_financially_assessed_item_can_advance_to_decision_candidate():
    advanced = advance_decision_candidate(
        _opportunity(LifecycleState.FINANCIALLY_ASSESSED),
        opportunity_confidence=86,
        validation_readiness=80,
        evidence_quality=90,
        market_health=78,
        financial_report=_financial(),
    )

    assert advanced.lifecycle_state is LifecycleState.DECISION_CANDIDATE


def test_decision_candidate_gate_rejects_wrong_lifecycle():
    with pytest.raises(ValueError, match="requires lifecycle state financially_assessed"):
        advance_decision_candidate(
            _opportunity(LifecycleState.VALIDATED_OPPORTUNITY),
            opportunity_confidence=86,
            validation_readiness=80,
            evidence_quality=90,
            market_health=78,
            financial_report=_financial(),
        )


def test_decision_candidate_gate_rejects_invalid_component_score():
    with pytest.raises(ValueError, match="evidence_quality must be between 0 and 100"):
        advance_decision_candidate(
            _opportunity(LifecycleState.FINANCIALLY_ASSESSED),
            opportunity_confidence=86,
            validation_readiness=80,
            evidence_quality=101,
            market_health=78,
            financial_report=_financial(),
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


def test_decision_engine_rejects_non_decision_candidate_lifecycle():
    for state in (
        LifecycleState.DOCUMENT,
        LifecycleState.SIGNAL,
        LifecycleState.LEAD,
        LifecycleState.VERIFIED_LEAD,
        LifecycleState.HYPOTHESIS,
        LifecycleState.VALIDATED_OPPORTUNITY,
        LifecycleState.FINANCIALLY_ASSESSED,
    ):
        with pytest.raises(ValueError, match="requires lifecycle state decision_candidate"):
            DecisionInputs(
                opportunity_confidence=90,
                validation_readiness=90,
                evidence_quality=90,
                market_health=90,
                financial_report=_financial(),
                lifecycle_state=state,
            )
