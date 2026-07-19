"""Conservative real-cost calculation for auction opportunities."""

from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass(frozen=True)
class RealCostInputs:
    """Explicit cost inputs; unknown values remain ``None``."""

    purchase_price_nok: float | None
    auction_fee_nok: float | None = None
    auction_fee_rate: float | None = None
    vat_rate: float = 0.25
    vat_status: str = "unknown"
    transport_nok: float | None = None
    dismantling_nok: float | None = None
    storage_nok: float | None = None
    repair_nok: float | None = None
    cleaning_nok: float | None = None
    selling_cost_nok: float | None = None
    other_cost_nok: float | None = None
    contingency_rate: float = 0.0

    def __post_init__(self) -> None:
        allowed = {"included", "excluded", "not_applicable", "unknown"}
        if self.vat_status not in allowed:
            raise ValueError(f"vat_status must be one of {sorted(allowed)}")
        for item in fields(self):
            value = getattr(self, item.name)
            if item.name == "vat_status" or value is None:
                continue
            if value < 0:
                raise ValueError(f"{item.name} must not be negative")
        if self.auction_fee_rate is not None and self.auction_fee_rate > 1:
            raise ValueError("auction_fee_rate must be expressed as a decimal")
        if self.vat_rate > 1 or self.contingency_rate > 1:
            raise ValueError("rates must be expressed as decimals")


@dataclass(frozen=True)
class RealCostReport:
    purchase_price_nok: float | None
    auction_fee_nok: float | None
    vat_nok: float | None
    direct_costs_nok: float
    contingency_nok: float | None
    total_cost_nok: float | None
    missing_fields: tuple[str, ...]
    warnings: tuple[str, ...]
    is_complete: bool


class RealCostEngine:
    """Calculate total acquisition cost without inventing missing amounts."""

    OPTIONAL_COST_FIELDS = (
        "transport_nok",
        "dismantling_nok",
        "storage_nok",
        "repair_nok",
        "cleaning_nok",
        "selling_cost_nok",
        "other_cost_nok",
    )

    def calculate(self, inputs: RealCostInputs) -> RealCostReport:
        missing: list[str] = []
        warnings: list[str] = []

        purchase = inputs.purchase_price_nok
        if purchase is None:
            missing.append("purchase_price_nok")

        fee = inputs.auction_fee_nok
        if fee is None and inputs.auction_fee_rate is not None and purchase is not None:
            fee = purchase * inputs.auction_fee_rate
        elif fee is None:
            missing.append("auction_fee_nok")

        vat: float | None
        taxable_base = None if purchase is None or fee is None else purchase + fee
        if inputs.vat_status in {"included", "not_applicable"}:
            vat = 0.0
        elif inputs.vat_status == "excluded":
            vat = None if taxable_base is None else taxable_base * inputs.vat_rate
        else:
            vat = None
            missing.append("vat_status")
            warnings.append("VAT treatment is unknown; total cost is provisional.")

        optional_values: list[float] = []
        for field_name in self.OPTIONAL_COST_FIELDS:
            value = getattr(inputs, field_name)
            if value is None:
                missing.append(field_name)
            else:
                optional_values.append(value)

        direct_costs = sum(optional_values)
        known_base = None if purchase is None or fee is None or vat is None else purchase + fee + vat + direct_costs
        contingency = None if known_base is None else known_base * inputs.contingency_rate
        total = None if known_base is None else known_base + contingency

        if any(name in missing for name in self.OPTIONAL_COST_FIELDS):
            warnings.append("One or more operating costs are missing; no zero value was assumed.")

        return RealCostReport(
            purchase_price_nok=_round_optional(purchase),
            auction_fee_nok=_round_optional(fee),
            vat_nok=_round_optional(vat),
            direct_costs_nok=round(direct_costs, 2),
            contingency_nok=_round_optional(contingency),
            total_cost_nok=_round_optional(total),
            missing_fields=tuple(missing),
            warnings=tuple(warnings),
            is_complete=not missing,
        )


def _round_optional(value: float | None) -> float | None:
    return None if value is None else round(value, 2)
