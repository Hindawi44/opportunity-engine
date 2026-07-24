"""Verified V2.8 + V2.9 financial integration without automatic purchase decisions."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


_REQUIRED_COST_FIELDS = (
    "auction_price_nok",
    "auction_fee_nok",
    "vat_nok",
    "transport_cost_nok",
    "dismantling_cost_nok",
    "storage_cost_nok",
)


def _number(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
        return float(value)
    return None


@dataclass(frozen=True, slots=True)
class VerifiedFinancialDecision:
    opportunity_id: str
    verified_comparable_count: int
    verified_cost_component_count: int
    market_evidence_status: str
    cost_evidence_status: str
    true_acquisition_cost_nok: float | None
    conservative_resale_value_nok: float | None
    expected_profit_nok: float | None
    roi_percent: float | None
    missing_required_evidence: tuple[str, ...]
    decision_gate: str
    automatic_purchase_decision: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["missing_required_evidence"] = list(self.missing_required_evidence)
        return payload


def integrate_verified_financial_evidence(
    opportunity_id: str,
    supplied: dict[str, Any],
) -> VerifiedFinancialDecision:
    """Integrate already-verified V2.8 and V2.9 evidence.

    Missing values remain missing. This function does not search, infer evidence, alter
    Financial Score, or issue an automatic purchase recommendation.
    """
    comparables = supplied.get("market_comparables")
    prices: list[float] = []
    if isinstance(comparables, list):
        for item in comparables:
            if not isinstance(item, dict) or item.get("verified") is not True:
                continue
            value = _number(item.get("price_nok"))
            source = str(item.get("source") or "").strip()
            url = str(item.get("url") or "").strip()
            if value is not None and value > 0 and source and url.startswith("https://"):
                prices.append(value)

    cost_values = {field: _number(supplied.get(field)) for field in _REQUIRED_COST_FIELDS}
    missing: list[str] = []
    if len(prices) < 3:
        missing.append("three_verified_market_comparables")
    missing.extend(field for field, value in cost_values.items() if value is None)

    market_complete = len(prices) >= 3
    cost_complete = all(value is not None for value in cost_values.values())
    acquisition = resale = profit = roi = None
    gate = "EVIDENCE_REQUIRED"

    if market_complete and cost_complete:
        acquisition = round(sum(float(value) for value in cost_values.values() if value is not None), 2)
        resale = round(min(prices), 2)
        profit = round(resale - acquisition, 2)
        roi = round((profit / acquisition) * 100.0, 2) if acquisition > 0 else None
        gate = "READY_FOR_FINANCIAL_REVIEW"

    return VerifiedFinancialDecision(
        opportunity_id=opportunity_id,
        verified_comparable_count=len(prices),
        verified_cost_component_count=sum(value is not None for value in cost_values.values()),
        market_evidence_status="COMPLETE" if market_complete else "INCOMPLETE",
        cost_evidence_status="COMPLETE" if cost_complete else "INCOMPLETE",
        true_acquisition_cost_nok=acquisition,
        conservative_resale_value_nok=resale,
        expected_profit_nok=profit,
        roi_percent=roi,
        missing_required_evidence=tuple(missing),
        decision_gate=gate,
        automatic_purchase_decision=False,
    )
