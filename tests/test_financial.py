import pytest

from opportunity_engine.ods import LifecycleState, OpportunityCandidate
from opportunity_engine.ods.financial import (
    FinancialAssessmentEvidence,
    FinancialInputs,
    advance_financially_assessed,
    build_financial_report,
)


def _financial_report():
    return build_financial_report(
        FinancialInputs(
            startup_cost=100_000,
            monthly_fixed_cost=20_000,
            unit_price=1_000,
            unit_variable_cost=400,
            monthly_units=50,
            working_capital_months=3,
        )
    )


def _opportunity(state: LifecycleState) -> OpportunityCandidate:
    return OpportunityCandidate(
        opportunity_id="opp-financial-1",
        title="Validated opportunity",
        description="Validated through measured experiments.",
        category="service",
        confidence=0.8,
        lifecycle_state=state,
    )


def test_financial_report_calculates_break_even_and_scenarios():
    report = _financial_report()

    assert report.required_capital == 160_000
    assert report.contribution_margin_per_unit == 600
    assert report.contribution_margin_pct == 60
    assert report.break_even_units_monthly == pytest.approx(33.33, abs=0.01)
    assert report.break_even_revenue_monthly == pytest.approx(33_333.33, abs=0.01)
    assert [scenario.name for scenario in report.scenarios] == ["conservative", "base", "upside"]
    assert report.scenarios[1].monthly_operating_profit == 10_000
    assert report.scenarios[1].payback_months == 16


def test_loss_scenario_has_no_payback_period():
    report = build_financial_report(
        FinancialInputs(
            startup_cost=50_000,
            monthly_fixed_cost=25_000,
            unit_price=500,
            unit_variable_cost=300,
            monthly_units=50,
        )
    )

    assert report.scenarios[1].monthly_operating_profit < 0
    assert report.scenarios[1].payback_months is None
    assert any("below monthly break-even" in warning for warning in report.warnings)


def test_rejects_invalid_margin_assumption():
    with pytest.raises(ValueError, match="lower than unit_price"):
        FinancialInputs(
            startup_cost=1,
            monthly_fixed_cost=1,
            unit_price=100,
            unit_variable_cost=100,
            monthly_units=1,
        )


def test_low_margin_adds_warning():
    report = build_financial_report(
        FinancialInputs(
            startup_cost=10_000,
            monthly_fixed_cost=1_000,
            unit_price=100,
            unit_variable_cost=85,
            monthly_units=100,
        )
    )
    assert any("below 20%" in warning for warning in report.warnings)


def test_validated_opportunity_advances_after_documented_financial_assessment():
    advanced = advance_financially_assessed(
        _opportunity(LifecycleState.VALIDATED_OPPORTUNITY),
        _financial_report(),
        FinancialAssessmentEvidence(
            assumption_sources=(
                "supplier quote dated 2026-07-18",
                "three signed customer price tests",
            )
        ),
    )

    assert advanced.lifecycle_state is LifecycleState.FINANCIALLY_ASSESSED


def test_financial_gate_rejects_unvalidated_opportunity():
    with pytest.raises(ValueError, match="requires VALIDATED_OPPORTUNITY"):
        advance_financially_assessed(
            _opportunity(LifecycleState.HYPOTHESIS),
            _financial_report(),
            FinancialAssessmentEvidence(assumption_sources=("documented assumptions",)),
        )


def test_financial_gate_requires_assumption_evidence():
    with pytest.raises(ValueError, match="at least one assumption source"):
        FinancialAssessmentEvidence(assumption_sources=())
