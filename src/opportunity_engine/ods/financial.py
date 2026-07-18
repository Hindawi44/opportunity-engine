"""Conservative financial intelligence for ODS opportunities.

The module calculates transparent scenario economics from explicit user inputs. It
never invents revenue, cost, or demand assumptions and is not financial advice.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import LifecycleState, OpportunityCandidate


@dataclass(frozen=True)
class FinancialInputs:
    startup_cost: float
    monthly_fixed_cost: float
    unit_price: float
    unit_variable_cost: float
    monthly_units: float
    working_capital_months: float = 3.0

    def __post_init__(self) -> None:
        values = {
            "startup_cost": self.startup_cost,
            "monthly_fixed_cost": self.monthly_fixed_cost,
            "unit_price": self.unit_price,
            "unit_variable_cost": self.unit_variable_cost,
            "monthly_units": self.monthly_units,
            "working_capital_months": self.working_capital_months,
        }
        if any(value < 0 for value in values.values()):
            raise ValueError("financial inputs must not be negative")
        if self.unit_price <= 0:
            raise ValueError("unit_price must be positive")
        if self.unit_variable_cost >= self.unit_price:
            raise ValueError("unit_variable_cost must be lower than unit_price")


@dataclass(frozen=True)
class FinancialScenario:
    name: str
    monthly_units: float
    monthly_revenue: float
    monthly_variable_cost: float
    monthly_operating_profit: float
    annual_operating_profit: float
    payback_months: float | None


@dataclass(frozen=True)
class FinancialReport:
    required_capital: float
    contribution_margin_per_unit: float
    contribution_margin_pct: float
    break_even_units_monthly: float
    break_even_revenue_monthly: float
    scenarios: tuple[FinancialScenario, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class FinancialAssessmentEvidence:
    """Auditable provenance for the assumptions used in a financial report."""

    assumption_sources: tuple[str, ...]

    def __post_init__(self) -> None:
        cleaned = tuple(item.strip() for item in self.assumption_sources if item.strip())
        if not cleaned:
            raise ValueError("financial assessment requires at least one assumption source")
        if len(cleaned) != len(self.assumption_sources):
            raise ValueError("financial assumption sources must not be empty")


def build_financial_report(inputs: FinancialInputs) -> FinancialReport:
    """Calculate break-even and three bounded demand scenarios."""
    margin = inputs.unit_price - inputs.unit_variable_cost
    margin_pct = margin / inputs.unit_price * 100.0
    break_even_units = inputs.monthly_fixed_cost / margin if margin else 0.0
    break_even_revenue = break_even_units * inputs.unit_price
    required_capital = inputs.startup_cost + inputs.monthly_fixed_cost * inputs.working_capital_months

    scenario_specs = (
        ("conservative", 0.70),
        ("base", 1.00),
        ("upside", 1.30),
    )
    scenarios = tuple(
        _scenario(
            name=name,
            units=inputs.monthly_units * multiplier,
            price=inputs.unit_price,
            variable_cost=inputs.unit_variable_cost,
            fixed_cost=inputs.monthly_fixed_cost,
            required_capital=required_capital,
        )
        for name, multiplier in scenario_specs
    )

    warnings: list[str] = [
        "Results depend entirely on the entered assumptions and are not a profit forecast.",
        "Taxes, VAT timing, financing costs, owner salary, and exceptional costs are excluded.",
    ]
    if inputs.monthly_units < break_even_units:
        warnings.append("Base demand assumption is below monthly break-even volume.")
    if margin_pct < 20:
        warnings.append("Contribution margin is below 20%, leaving limited room for estimation error.")

    return FinancialReport(
        required_capital=round(required_capital, 2),
        contribution_margin_per_unit=round(margin, 2),
        contribution_margin_pct=round(margin_pct, 2),
        break_even_units_monthly=round(break_even_units, 2),
        break_even_revenue_monthly=round(break_even_revenue, 2),
        scenarios=scenarios,
        warnings=tuple(warnings),
    )


def advance_financially_assessed(
    opportunity: OpportunityCandidate,
    report: FinancialReport,
    evidence: FinancialAssessmentEvidence,
) -> OpportunityCandidate:
    """Advance only a validated opportunity backed by a complete financial report.

    This transition records that economics were assessed; it does not assert that the
    opportunity is profitable or suitable for investment.
    """

    if opportunity.lifecycle_state is not LifecycleState.VALIDATED_OPPORTUNITY:
        raise ValueError("financial assessment requires VALIDATED_OPPORTUNITY")
    expected_scenarios = {"conservative", "base", "upside"}
    actual_scenarios = {scenario.name for scenario in report.scenarios}
    if actual_scenarios != expected_scenarios:
        raise ValueError("financial assessment requires conservative, base, and upside scenarios")
    if report.required_capital < 0:
        raise ValueError("required capital must not be negative")
    if report.contribution_margin_per_unit <= 0:
        raise ValueError("financial assessment requires a positive contribution margin")
    if not evidence.assumption_sources:
        raise ValueError("financial assessment requires assumption evidence")
    return opportunity.transition_to(LifecycleState.FINANCIALLY_ASSESSED)


def _scenario(
    *,
    name: str,
    units: float,
    price: float,
    variable_cost: float,
    fixed_cost: float,
    required_capital: float,
) -> FinancialScenario:
    revenue = units * price
    total_variable = units * variable_cost
    monthly_profit = revenue - total_variable - fixed_cost
    annual_profit = monthly_profit * 12.0
    payback = required_capital / monthly_profit if monthly_profit > 0 else None
    return FinancialScenario(
        name=name,
        monthly_units=round(units, 2),
        monthly_revenue=round(revenue, 2),
        monthly_variable_cost=round(total_variable, 2),
        monthly_operating_profit=round(monthly_profit, 2),
        annual_operating_profit=round(annual_profit, 2),
        payback_months=round(payback, 2) if payback is not None else None,
    )
