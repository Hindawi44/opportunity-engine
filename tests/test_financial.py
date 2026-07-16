import pytest

from opportunity_engine.ods.financial import FinancialInputs, build_financial_report


def test_financial_report_calculates_break_even_and_scenarios():
    report = build_financial_report(
        FinancialInputs(
            startup_cost=100_000,
            monthly_fixed_cost=20_000,
            unit_price=1_000,
            unit_variable_cost=400,
            monthly_units=50,
            working_capital_months=3,
        )
    )

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
