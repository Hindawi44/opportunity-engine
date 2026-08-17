"""Canonical financial value calculation for auction opportunities.

This module is the single owner of derived financial value. It combines a
market-value report and a real-cost report into auditable profit, ROI, resale
margin, and conservative maximum-cost fields. It does not issue BUY/WATCH/REJECT.
"""

from __future__ import annotations

from dataclasses import dataclass

from .market_pricing import MarketPriceReport
from .real_cost import RealCostReport


@dataclass(frozen=True)
class OpportunityValuePolicy:
    """Policy used only to derive conservative financial value ceilings."""

    target_roi_for_max_bid: float = 0.35

    def __post_init__(self) -> None:
        if not 0 <= self.target_roi_for_max_bid <= 1:
            raise ValueError(
                "target_roi_for_max_bid must be expressed as a decimal between 0 and 1"
            )


@dataclass(frozen=True)
class OpportunityValueReport:
    """Canonical derived financial value consumed by downstream decision logic."""

    opportunity_id: str
    conservative_resale_nok: float | None
    total_cost_nok: float | None
    expected_profit_nok: float | None
    roi: float | None
    margin_on_resale: float | None
    maximum_total_cost_nok: float | None
    maximum_purchase_price_nok: float | None
    confidence: str
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]


class OpportunityValueEngine:
    """Calculate canonical value without making a commercial decision."""

    def __init__(self, policy: OpportunityValuePolicy | None = None) -> None:
        self.policy = policy or OpportunityValuePolicy()

    def evaluate(
        self,
        market: MarketPriceReport,
        costs: RealCostReport,
    ) -> OpportunityValueReport:
        blockers: list[str] = []
        warnings = list(market.warnings) + list(costs.warnings)

        resale = market.conservative_resale_nok
        total = costs.total_cost_nok

        if resale is None:
            blockers.append("conservative_resale_nok")
        if total is None:
            blockers.append("total_cost_nok")
        if market.confidence == "insufficient":
            blockers.append("market_comparables")
        if not costs.is_complete:
            blockers.extend(f"cost:{name}" for name in costs.missing_fields)

        profit = None if resale is None or total is None else resale - total
        roi = None if profit is None or total is None or total <= 0 else profit / total
        margin = None if profit is None or resale is None or resale <= 0 else profit / resale

        maximum_total = None
        maximum_purchase = None
        if resale is not None:
            maximum_total = resale / (1 + self.policy.target_roi_for_max_bid)
            if costs.purchase_price_nok is not None and total is not None:
                non_purchase_costs = total - costs.purchase_price_nok
                maximum_purchase = max(0.0, maximum_total - non_purchase_costs)

        if market.confidence == "low":
            warnings.append("Market confidence is low; verify comparables manually.")
        if maximum_purchase is not None and costs.purchase_price_nok is not None:
            if costs.purchase_price_nok > maximum_purchase:
                warnings.append("Current purchase price exceeds the conservative maximum bid.")

        return OpportunityValueReport(
            opportunity_id=market.opportunity_id,
            conservative_resale_nok=_round(resale),
            total_cost_nok=_round(total),
            expected_profit_nok=_round(profit),
            roi=_round_ratio(roi),
            margin_on_resale=_round_ratio(margin),
            maximum_total_cost_nok=_round(maximum_total),
            maximum_purchase_price_nok=_round(maximum_purchase),
            confidence=self._combined_confidence(market, costs, blockers),
            blockers=tuple(dict.fromkeys(blockers)),
            warnings=tuple(dict.fromkeys(warnings)),
        )

    @staticmethod
    def _combined_confidence(
        market: MarketPriceReport,
        costs: RealCostReport,
        blockers: list[str],
    ) -> str:
        if blockers:
            return "insufficient"
        if not costs.is_complete or market.confidence == "low":
            return "low"
        return market.confidence


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


def _round_ratio(value: float | None) -> float | None:
    return None if value is None else round(value, 4)
