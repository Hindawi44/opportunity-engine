"""Conservative portfolio and capital allocation for verified opportunities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class CapitalAllocationPolicy:
    total_capital_nok: float
    reserve_fraction: float = 0.20
    max_single_opportunity_fraction: float = 0.25
    minimum_allocation_nok: float = 500.0

    def __post_init__(self) -> None:
        if self.total_capital_nok < 0:
            raise ValueError("total_capital_nok must not be negative")
        if not 0 <= self.reserve_fraction < 1:
            raise ValueError("reserve_fraction must be between 0 and 1")
        if not 0 < self.max_single_opportunity_fraction <= 1:
            raise ValueError("max_single_opportunity_fraction must be between 0 and 1")
        if self.minimum_allocation_nok < 0:
            raise ValueError("minimum_allocation_nok must not be negative")


@dataclass(frozen=True)
class CapitalAllocationCandidate:
    opportunity_id: str
    decision: str
    discovery_score: float
    maximum_purchase_price_nok: float | None
    total_cost_nok: float | None
    expected_profit_nok: float | None
    roi: float | None
    is_actionable: bool
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class OpportunityAllocation:
    opportunity_id: str
    priority: int
    eligible: bool
    suggested_max_bid_nok: float | None
    reserved_capital_nok: float | None
    capital_share: float | None
    expected_profit_nok: float | None
    roi: float | None
    reasons: tuple[str, ...]
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class CapitalAllocationPlan:
    total_capital_nok: float
    reserve_capital_nok: float
    investable_capital_nok: float
    allocated_capital_nok: float
    unallocated_capital_nok: float
    allocation_count: int
    allocations: tuple[OpportunityAllocation, ...]
    warnings: tuple[str, ...]


class CapitalAllocationEngine:
    """Allocate only to complete, actionable buy decisions.

    The engine never raises a bid above the decision engine's conservative maximum
    purchase price and always preserves the configured cash reserve.
    """

    def allocate(
        self,
        candidates: Iterable[CapitalAllocationCandidate],
        policy: CapitalAllocationPolicy,
    ) -> CapitalAllocationPlan:
        reserve = round(policy.total_capital_nok * policy.reserve_fraction, 2)
        investable = round(max(0.0, policy.total_capital_nok - reserve), 2)
        single_cap = round(policy.total_capital_nok * policy.max_single_opportunity_fraction, 2)
        remaining = investable
        allocations: list[OpportunityAllocation] = []
        warnings: list[str] = []

        ranked = sorted(
            candidates,
            key=lambda item: (
                item.decision == "buy",
                item.is_actionable,
                item.discovery_score,
                item.roi if item.roi is not None else -1.0,
                item.expected_profit_nok if item.expected_profit_nok is not None else -1.0,
            ),
            reverse=True,
        )

        for priority, candidate in enumerate(ranked, start=1):
            blockers = list(candidate.blockers)
            reasons: list[str] = []
            eligible = True

            if candidate.decision != "buy":
                eligible = False
                blockers.append("decision_not_buy")
            if not candidate.is_actionable:
                eligible = False
                blockers.append("decision_not_actionable")
            if candidate.maximum_purchase_price_nok is None:
                eligible = False
                blockers.append("maximum_purchase_price_nok")
            if candidate.total_cost_nok is None:
                eligible = False
                blockers.append("total_cost_nok")
            if candidate.discovery_score < 65:
                eligible = False
                blockers.append("discovery_score_below_65")

            suggested_bid = None
            reserved_capital = None
            share = None
            if eligible:
                suggested_bid = min(candidate.maximum_purchase_price_nok or 0.0, single_cap, remaining)
                required_capital = min(candidate.total_cost_nok or 0.0, single_cap, remaining)
                if suggested_bid < policy.minimum_allocation_nok or required_capital < policy.minimum_allocation_nok:
                    eligible = False
                    blockers.append("insufficient_remaining_capital")
                    suggested_bid = None
                else:
                    suggested_bid = round(suggested_bid, 2)
                    reserved_capital = round(required_capital, 2)
                    remaining = round(max(0.0, remaining - reserved_capital), 2)
                    share = (
                        round(reserved_capital / policy.total_capital_nok, 4)
                        if policy.total_capital_nok > 0
                        else None
                    )
                    reasons.append("الفرصة قرار شراء قابل للتنفيذ ودرجة اكتشافها قوية.")
                    reasons.append("الحد المقترح لا يتجاوز الحد المحافظ للمزايدة ولا سقف الفرصة الواحدة.")

            allocations.append(
                OpportunityAllocation(
                    opportunity_id=candidate.opportunity_id,
                    priority=priority,
                    eligible=eligible,
                    suggested_max_bid_nok=suggested_bid,
                    reserved_capital_nok=reserved_capital,
                    capital_share=share,
                    expected_profit_nok=candidate.expected_profit_nok,
                    roi=candidate.roi,
                    reasons=tuple(reasons),
                    blockers=tuple(dict.fromkeys(blockers)),
                )
            )

        allocated = round(investable - remaining, 2)
        if policy.total_capital_nok == 0:
            warnings.append("رأس المال المتاح يساوي صفرًا؛ لم يتم اقتراح أي تخصيص.")
        if not any(item.eligible for item in allocations):
            warnings.append("لا توجد فرصة شراء مكتملة وقوية تستحق تخصيص رأس المال حاليًا.")

        return CapitalAllocationPlan(
            total_capital_nok=round(policy.total_capital_nok, 2),
            reserve_capital_nok=reserve,
            investable_capital_nok=investable,
            allocated_capital_nok=allocated,
            unallocated_capital_nok=remaining,
            allocation_count=sum(item.eligible for item in allocations),
            allocations=tuple(allocations),
            warnings=tuple(warnings),
        )
