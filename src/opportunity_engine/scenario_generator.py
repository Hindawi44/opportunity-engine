"""Evidence-aware scenario generation for Opportunity Engine v2.5.1.

The engine creates multiple ways to benefit from an opportunity without
inventing financial values. Calculations are performed only when explicit
inputs are available; otherwise the corresponding value remains ``None`` and
is recorded as missing information.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .living_investment_file import (
    LivingInvestmentFile,
    MissingInformation,
    RevenuePath,
    RevenuePathType,
)


@dataclass(frozen=True, slots=True)
class ScenarioInputs:
    """Verified or user-supplied inputs used by the scenario generator."""

    purchase_price_nok: float | None = None
    auction_fees_nok: float | None = None
    transport_cost_nok: float | None = None
    storage_cost_nok: float | None = None
    repair_cost_nok: float | None = None
    conservative_resale_value_nok: float | None = None
    brokerage_commission_rate: float | None = None
    liquidation_commission_rate: float | None = None
    partner_funding_share: float | None = None
    lot_purchase_fraction: float | None = None
    presale_committed_revenue_nok: float | None = None
    expected_duration_days: int | None = None

    def __post_init__(self) -> None:
        money_fields = (
            self.purchase_price_nok,
            self.auction_fees_nok,
            self.transport_cost_nok,
            self.storage_cost_nok,
            self.repair_cost_nok,
            self.conservative_resale_value_nok,
            self.presale_committed_revenue_nok,
        )
        if any(value is not None and value < 0 for value in money_fields):
            raise ValueError("Financial inputs cannot be negative")
        for value, name in (
            (self.brokerage_commission_rate, "brokerage_commission_rate"),
            (self.liquidation_commission_rate, "liquidation_commission_rate"),
            (self.partner_funding_share, "partner_funding_share"),
            (self.lot_purchase_fraction, "lot_purchase_fraction"),
        ):
            if value is not None and not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.expected_duration_days is not None and self.expected_duration_days <= 0:
            raise ValueError("expected_duration_days must be positive")


@dataclass(frozen=True, slots=True)
class ScenarioGenerationResult:
    opportunity_id: str
    generated_path_ids: tuple[str, ...]
    missing_questions_added: tuple[str, ...]
    best_path_id: str | None


class ScenarioGeneratorEngine:
    """Generate six investment paths and attach them to a living file."""

    GENERATED_PREFIX = "generated-v251-"

    def generate(
        self,
        item: LivingInvestmentFile,
        inputs: ScenarioInputs | None = None,
        *,
        evidence_ids: Iterable[str] = (),
    ) -> ScenarioGenerationResult:
        inputs = inputs or ScenarioInputs(purchase_price_nok=item.asking_price_nok)
        evidence = list(dict.fromkeys(evidence_ids))
        known_evidence = {entry.evidence_id for entry in item.evidence}
        unknown = [entry for entry in evidence if entry not in known_evidence]
        if unknown:
            raise ValueError(f"Unknown evidence ids: {', '.join(unknown)}")

        # Regeneration is deterministic and does not duplicate previous generated paths.
        item.revenue_paths = [
            path for path in item.revenue_paths if not path.path_id.startswith(self.GENERATED_PREFIX)
        ]

        paths = (
            self._purchase(item, inputs, evidence),
            self._brokerage(item, inputs, evidence),
            self._partnership(item, inputs, evidence),
            self._lot_split(item, inputs, evidence),
            self._presale(item, inputs, evidence),
            self._liquidation_management(item, inputs, evidence),
        )
        for path in paths:
            item.add_revenue_path(path)

        questions = self._add_missing_information(item, inputs)
        best_path = self._select_current_best(paths)
        if best_path is not None:
            item.select_best_path(best_path.path_id, best_path.first_step or "Verify the missing inputs")

        return ScenarioGenerationResult(
            opportunity_id=item.opportunity_id,
            generated_path_ids=tuple(path.path_id for path in paths),
            missing_questions_added=tuple(questions),
            best_path_id=best_path.path_id if best_path else None,
        )

    def _purchase(self, item: LivingInvestmentFile, data: ScenarioInputs, evidence: list[str]) -> RevenuePath:
        purchase_price = data.purchase_price_nok
        direct_costs = self._sum_known(
            purchase_price,
            data.auction_fees_nok,
            data.transport_cost_nok,
            data.storage_cost_nok,
            data.repair_cost_nok,
        )
        return RevenuePath(
            path_id=f"{self.GENERATED_PREFIX}purchase",
            path_type=RevenuePathType.PURCHASE,
            title="Direct purchase and resale",
            description="Acquire the opportunity, prepare the assets, and resell them to end buyers.",
            requirements=["Verified ownership and contents", "Funding", "Transport plan", "Confirmed resale channel"],
            estimated_cost_nok=direct_costs,
            estimated_revenue_nok=data.conservative_resale_value_nok,
            duration_days=data.expected_duration_days,
            risks=["Unsold inventory", "Hidden defects", "Underestimated logistics", "Working-capital lockup"],
            first_step="Request a detailed inventory list and verify the all-in acquisition cost.",
            evidence_ids=evidence,
        )

    def _brokerage(self, item: LivingInvestmentFile, data: ScenarioInputs, evidence: list[str]) -> RevenuePath:
        revenue = None
        if data.conservative_resale_value_nok is not None and data.brokerage_commission_rate is not None:
            revenue = data.conservative_resale_value_nok * data.brokerage_commission_rate
        return RevenuePath(
            path_id=f"{self.GENERATED_PREFIX}brokerage",
            path_type=RevenuePathType.BROKERAGE,
            title="Broker the transaction",
            description="Match the seller with specialist buyers and earn a documented commission without buying the full lot.",
            requirements=["Written brokerage mandate", "Buyer list", "Clear commission terms", "Asset documentation"],
            estimated_cost_nok=0.0,
            estimated_revenue_nok=revenue,
            duration_days=data.expected_duration_days,
            risks=["Seller bypass", "Buyer non-performance", "Unclear commission entitlement"],
            first_step="Ask the seller whether a commission-based sales mandate is acceptable.",
            evidence_ids=evidence,
        )

    def _partnership(self, item: LivingInvestmentFile, data: ScenarioInputs, evidence: list[str]) -> RevenuePath:
        total_cost = self._sum_known(
            data.purchase_price_nok,
            data.auction_fees_nok,
            data.transport_cost_nok,
            data.storage_cost_nok,
            data.repair_cost_nok,
        )
        own_capital = None
        if total_cost is not None and data.partner_funding_share is not None:
            own_capital = total_cost * (1 - data.partner_funding_share)
        return RevenuePath(
            path_id=f"{self.GENERATED_PREFIX}partnership",
            path_type=RevenuePathType.PARTNERSHIP,
            title="Capital and operations partnership",
            description="Combine a funding partner, storage/logistics partner, and sales management.",
            requirements=["Partner agreement", "Defined roles", "Profit-sharing formula", "Exit and loss rules"],
            estimated_cost_nok=own_capital,
            estimated_revenue_nok=None,
            duration_days=data.expected_duration_days,
            risks=["Partner conflict", "Undefined loss allocation", "Slow decisions"],
            first_step="Prepare a one-page partner brief with capital, storage, and sales roles.",
            evidence_ids=evidence,
        )

    def _lot_split(self, item: LivingInvestmentFile, data: ScenarioInputs, evidence: list[str]) -> RevenuePath:
        cost = None
        revenue = None
        if data.purchase_price_nok is not None and data.lot_purchase_fraction is not None:
            cost = data.purchase_price_nok * data.lot_purchase_fraction
        if data.conservative_resale_value_nok is not None and data.lot_purchase_fraction is not None:
            revenue = data.conservative_resale_value_nok * data.lot_purchase_fraction
        return RevenuePath(
            path_id=f"{self.GENERATED_PREFIX}lot-split",
            path_type=RevenuePathType.LOT_SPLIT,
            title="Negotiate a partial lot",
            description="Purchase only one trailer, category, or high-demand subset rather than the complete lot.",
            requirements=["Item-level inventory", "Seller permission to split", "Category demand evidence"],
            estimated_cost_nok=cost,
            estimated_revenue_nok=revenue,
            duration_days=data.expected_duration_days,
            risks=["Best items withheld", "Weak remaining assortment", "Seller refuses split"],
            first_step="Identify the smallest independently saleable subset and request a separate price.",
            evidence_ids=evidence,
        )

    def _presale(self, item: LivingInvestmentFile, data: ScenarioInputs, evidence: list[str]) -> RevenuePath:
        return RevenuePath(
            path_id=f"{self.GENERATED_PREFIX}presale",
            path_type=RevenuePathType.PRE_SALE,
            title="Pre-sell before financial commitment",
            description="Secure buyer interest or deposits for documented subsets before committing capital.",
            requirements=["Seller permission to market", "Photos and inventory", "Refund and delivery terms"],
            estimated_cost_nok=0.0,
            estimated_revenue_nok=data.presale_committed_revenue_nok,
            duration_days=data.expected_duration_days,
            risks=["Customer cancellation", "Mismatch between photos and goods", "Premature promises"],
            first_step="Create a non-binding buyer-interest test for three clearly defined product groups.",
            evidence_ids=evidence,
        )

    def _liquidation_management(self, item: LivingInvestmentFile, data: ScenarioInputs, evidence: list[str]) -> RevenuePath:
        revenue = None
        if data.conservative_resale_value_nok is not None and data.liquidation_commission_rate is not None:
            revenue = data.conservative_resale_value_nok * data.liquidation_commission_rate
        return RevenuePath(
            path_id=f"{self.GENERATED_PREFIX}liquidation-management",
            path_type=RevenuePathType.LIQUIDATION_MANAGEMENT,
            title="Manage the liquidation for a percentage",
            description="Photograph, list, negotiate, and coordinate sales on behalf of the owner for a percentage of realised sales.",
            requirements=["Exclusive or defined sales mandate", "Access to goods", "Settlement procedure", "Commission agreement"],
            estimated_cost_nok=0.0,
            estimated_revenue_nok=revenue,
            duration_days=data.expected_duration_days,
            risks=["High operational workload", "Slow sell-through", "Disputes over realised sales"],
            first_step="Offer a limited pilot: manage one category for an agreed percentage and fixed period.",
            evidence_ids=evidence,
        )

    def _add_missing_information(self, item: LivingInvestmentFile, data: ScenarioInputs) -> list[str]:
        required = []
        if data.purchase_price_nok is None:
            required.append(("What is the verified purchase price?", "Capital and profit cannot be calculated.", "Confirm with seller or auction terms"))
        if data.conservative_resale_value_nok is None:
            required.append(("What is the conservative resale value?", "Revenue and downside cannot be estimated.", "Collect verified comparable sales"))
        if data.transport_cost_nok is None:
            required.append(("What will transport and loading cost?", "Logistics may eliminate the margin.", "Request written logistics quotes"))
        if data.brokerage_commission_rate is None:
            required.append(("What brokerage commission will the seller accept?", "Brokerage revenue is unknown.", "Negotiate a written commission mandate"))
        if data.lot_purchase_fraction is None:
            required.append(("Can the lot be divided, and what fraction is commercially attractive?", "The lower-capital path cannot be quantified.", "Request item-level inventory and split pricing"))

        existing = {entry.question for entry in item.missing_information if not entry.resolved}
        added: list[str] = []
        for question, why, method in required:
            if question in existing:
                continue
            item.add_missing_information(question, why, method, priority="high")
            added.append(question)
        return added

    @staticmethod
    def _sum_known(*values: float | None) -> float | None:
        if any(value is None for value in values):
            return None
        return sum(value for value in values if value is not None)

    @staticmethod
    def _select_current_best(paths: tuple[RevenuePath, ...]) -> RevenuePath | None:
        # Prefer a quantified, non-negative path. Lower capital wins when profit is equal.
        quantified = [path for path in paths if path.estimated_profit_nok is not None]
        if not quantified:
            return None
        viable = [path for path in quantified if path.estimated_profit_nok >= 0]
        if not viable:
            return None
        return max(
            viable,
            key=lambda path: (
                path.estimated_profit_nok,
                -(path.estimated_cost_nok or 0.0),
            ),
        )
