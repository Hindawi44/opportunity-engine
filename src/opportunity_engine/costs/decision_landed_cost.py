"""Apply Landed Cost Estimate V1 to one operational decision record.

This adapter is additive. It selects one ranked decision record, copies only
explicit cost values, preserves unknown inputs, and never changes the official
decision, scoring, ranking, alerts, or discovery outputs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from opportunity_engine.buyers import BuyerProfileV1

from .landed_cost import (
    CostComponentV1,
    LandedCostEstimateError,
    LandedCostEstimateV1,
    build_landed_cost_snapshot,
)


EXPORT_SCHEMA_VERSION = "operational-landed-cost-export-v1"


@dataclass(frozen=True, slots=True)
class _ComponentMapping:
    component_id: str
    label: str
    source_field: str
    missing_evidence_field: str


_COMPONENT_MAPPINGS: tuple[_ComponentMapping, ...] = (
    _ComponentMapping("auction_fee", "Auction or platform fee", "auction_fee_nok", "auction_fee_nok"),
    _ComponentMapping("transport", "Transport to buyer destination", "transport_cost_nok", "transport_cost_nok"),
    _ComponentMapping("dismantling", "Dismantling or loading", "dismantling_cost_nok", "dismantling_cost_nok"),
    _ComponentMapping("storage", "Storage", "storage_cost_nok", "storage_cost_nok"),
    _ComponentMapping("repair", "Repair or condition allowance", "repair_cost_nok", "repair_cost_nok"),
    _ComponentMapping("other_costs", "Other documented costs", "other_costs_nok", "other_costs_nok"),
    _ComponentMapping("vat", "VAT cash outflow", "vat_nok", "vat_nok"),
)


def _non_empty(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LandedCostEstimateError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_non_negative_number(value: object, field_name: str) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LandedCostEstimateError(f"{field_name} must be null or a number")
    if value < 0:
        raise LandedCostEstimateError(f"{field_name} must not be negative")
    return value


def _decision_records(decision_payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(decision_payload, dict):
        raise LandedCostEstimateError("decision payload must be an object")
    decisions = decision_payload.get("decisions")
    if not isinstance(decisions, list):
        raise LandedCostEstimateError("decision payload decisions must be a list")
    records: list[dict[str, Any]] = []
    for index, record in enumerate(decisions):
        if not isinstance(record, dict):
            raise LandedCostEstimateError(
                f"decision payload decisions[{index}] must be an object"
            )
        records.append(record)
    declared_count = decision_payload.get("decision_count")
    if declared_count is not None and declared_count != len(records):
        raise LandedCostEstimateError(
            "decision_count does not match the number of decision records"
        )
    return records


def select_operational_decision(
    decision_payload: dict[str, Any],
    *,
    opportunity_id: str | None = None,
) -> dict[str, Any] | None:
    """Select one explicit record or the first ranked record with a known price."""
    records = _decision_records(decision_payload)
    if opportunity_id is not None:
        requested = _non_empty(opportunity_id, "opportunity_id")
        for record in records:
            if record.get("opportunity_id") == requested:
                _non_empty(record.get("opportunity_id"), "record.opportunity_id")
                _optional_non_negative_number(
                    record.get("asking_price_nok"), "record.asking_price_nok"
                )
                return record
        raise LandedCostEstimateError(
            f"opportunity_id not found in decision payload: {requested}"
        )

    for record in records:
        record_id = record.get("opportunity_id")
        price = record.get("asking_price_nok")
        if (
            isinstance(record_id, str)
            and record_id.strip()
            and not isinstance(price, bool)
            and isinstance(price, (int, float))
            and price >= 0
        ):
            return record
    return None


def _source_ref(opportunity_id: str, field_name: str) -> str:
    return f"data/decision_intelligence.json#{opportunity_id}:{field_name}"


def _vat_treatment(record: dict[str, Any]) -> str:
    recoverable = record.get("vat_recoverable")
    if recoverable is True:
        return "RECOVERABLE_CASH_OUTFLOW"
    if recoverable is False:
        return "ECONOMIC_COST"
    status = record.get("vat_status")
    if isinstance(status, str):
        normalized = status.strip().upper()
        if normalized in {"RECOVERABLE", "DEDUCTIBLE", "REFUNDABLE"}:
            return "RECOVERABLE_CASH_OUTFLOW"
        if normalized in {"NON_RECOVERABLE", "NOT_RECOVERABLE", "ECONOMIC_COST"}:
            return "ECONOMIC_COST"
    return "UNKNOWN"


def _known_component(
    *,
    mapping: _ComponentMapping,
    amount: float | int,
    opportunity_id: str,
    required: bool,
    record: dict[str, Any],
) -> CostComponentV1:
    treatment = "ECONOMIC_COST"
    notes: tuple[str, ...] = ()
    if mapping.component_id == "vat":
        treatment = _vat_treatment(record)
        if treatment == "UNKNOWN":
            notes = (
                "VAT amount is present, but recoverability is not established by the decision record.",
            )
    return CostComponentV1(
        component_id=mapping.component_id,
        label=mapping.label,
        status="CONFIRMED",
        economic_treatment=treatment,
        required_for_qualification=required,
        low_nok=amount,
        expected_nok=amount,
        high_nok=amount,
        source_ref=_source_ref(opportunity_id, mapping.source_field),
        notes=notes,
    )


def _unknown_component(
    *,
    mapping: _ComponentMapping,
    required: bool,
    record: dict[str, Any],
    buyer: BuyerProfileV1,
) -> CostComponentV1:
    notes: list[str] = []
    source_city = record.get("city")
    if mapping.component_id == "transport":
        if isinstance(source_city, str) and source_city.strip():
            notes.append(
                f"Transport is unknown from {source_city.strip()} to {buyer.location['city']}."
            )
        else:
            notes.append(
                f"Transport is unknown because the source location is incomplete; destination is {buyer.location['city']}."
            )
    elif required:
        notes.append(
            f"The official decision record lists {mapping.missing_evidence_field} as missing evidence."
        )
    return CostComponentV1(
        component_id=mapping.component_id,
        label=mapping.label,
        status="UNKNOWN",
        economic_treatment="UNKNOWN",
        required_for_qualification=required,
        low_nok=None,
        expected_nok=None,
        high_nok=None,
        source_ref=None,
        notes=tuple(notes),
    )


def _missing_evidence(record: dict[str, Any]) -> set[str]:
    raw = record.get("missing_evidence", [])
    if raw is None:
        return set()
    if not isinstance(raw, list):
        raise LandedCostEstimateError("record.missing_evidence must be a list")
    return {
        _non_empty(item, "record.missing_evidence[]")
        for item in raw
    }


def build_estimate_from_decision_record(
    record: dict[str, Any],
    buyer: BuyerProfileV1,
) -> LandedCostEstimateV1:
    """Map one official decision record without deriving absent values."""
    opportunity_id = _non_empty(record.get("opportunity_id"), "record.opportunity_id")
    asking_price = _optional_non_negative_number(
        record.get("asking_price_nok"), "record.asking_price_nok"
    )
    missing = _missing_evidence(record)

    components: list[CostComponentV1] = []
    if asking_price is None:
        components.append(
            CostComponentV1(
                component_id="purchase_price",
                label="Current asking or bid price",
                status="UNKNOWN",
                economic_treatment="UNKNOWN",
                required_for_qualification=True,
                low_nok=None,
                expected_nok=None,
                high_nok=None,
                source_ref=None,
                notes=("The official decision record has no asking_price_nok value.",),
            )
        )
    else:
        components.append(
            CostComponentV1(
                component_id="purchase_price",
                label="Current asking or bid price",
                status="CONFIRMED",
                economic_treatment="ECONOMIC_COST",
                required_for_qualification=True,
                low_nok=asking_price,
                expected_nok=asking_price,
                high_nok=asking_price,
                source_ref=_source_ref(opportunity_id, "asking_price_nok"),
                notes=(
                    "This is the current asking or bid amount, not a final acquisition commitment.",
                ),
            )
        )

    for mapping in _COMPONENT_MAPPINGS:
        amount = _optional_non_negative_number(
            record.get(mapping.source_field),
            f"record.{mapping.source_field}",
        )
        required = mapping.missing_evidence_field in missing or amount is not None
        if amount is None:
            components.append(
                _unknown_component(
                    mapping=mapping,
                    required=required,
                    record=record,
                    buyer=buyer,
                )
            )
        else:
            components.append(
                _known_component(
                    mapping=mapping,
                    amount=amount,
                    opportunity_id=opportunity_id,
                    required=required,
                    record=record,
                )
            )

    source_city = record.get("city")
    assumptions = [
        "No route, carrier quote, VAT rule, customs rule, or external price lookup was performed.",
        "The selected decision record remains the owner of final_decision and opportunity_score.",
    ]
    if isinstance(source_city, str) and source_city.strip():
        assumptions.append(
            f"The source city is copied as {source_city.strip()}; destination precision remains buyer-profile precision."
        )

    evidence_refs = [_source_ref(opportunity_id, "record")]
    url = record.get("url")
    if isinstance(url, str) and url.strip():
        evidence_refs.append(url.strip())

    return LandedCostEstimateV1(
        estimate_id=f"landed-cost-{opportunity_id}-to-{buyer.profile_id.lower()}",
        opportunity_id=opportunity_id,
        destination={
            "country_code": buyer.location["country_code"],
            "city": buyer.location["city"],
            "postal_code": buyer.location.get("postal_code"),
            "coordinates": buyer.location.get("coordinates"),
        },
        currency_code=buyer.settlement_currency,
        components=tuple(components),
        assumptions=tuple(assumptions),
        evidence_refs=tuple(evidence_refs),
    )


def build_operational_landed_cost_export(
    decision_payload: dict[str, Any],
    buyer: BuyerProfileV1,
    *,
    opportunity_id: str | None = None,
) -> dict[str, Any]:
    """Build a zero-safe sidecar for one real operational opportunity."""
    record = select_operational_decision(
        decision_payload,
        opportunity_id=opportunity_id,
    )
    base = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "source_schema_version": decision_payload.get("schema_version"),
        "source_generated_at": decision_payload.get("generated_at"),
        "source_official_decision_field": decision_payload.get(
            "official_decision_field"
        ),
        "buyer_profile_id": buyer.profile_id,
        "selection_policy": (
            "EXPLICIT_OPPORTUNITY_ID"
            if opportunity_id is not None
            else "FIRST_RANKED_RECORD_WITH_KNOWN_ASKING_PRICE"
        ),
    }
    if record is None:
        return {
            **base,
            "selection_status": "NO_ELIGIBLE_OPPORTUNITY",
            "selection_reason": (
                "No decision record contains both a non-empty opportunity_id "
                "and a non-negative asking_price_nok."
            ),
            "source_opportunity": None,
            "landed_cost_estimate": None,
        }

    estimate = build_estimate_from_decision_record(record, buyer)
    snapshot = build_landed_cost_snapshot(estimate)
    source_summary = {
        "opportunity_id": record.get("opportunity_id"),
        "title": record.get("title"),
        "url": record.get("url"),
        "source_city": record.get("city"),
        "asking_price_nok": record.get("asking_price_nok"),
        "final_decision": record.get("final_decision"),
        "opportunity_score": record.get("opportunity_score"),
        "priority": record.get("priority"),
    }

    purchase_component = next(
        component
        for component in snapshot["components"]
        if component["component_id"] == "purchase_price"
    )
    if purchase_component["expected_nok"] != record.get("asking_price_nok"):
        raise LandedCostEstimateError(
            f"asking_price_nok changed for {estimate.opportunity_id}"
        )
    if snapshot["scope"]["changes_final_decision"] is not False:
        raise LandedCostEstimateError("landed-cost sidecar may not change final_decision")

    return {
        **base,
        "selection_status": "SELECTED",
        "selection_reason": (
            "Selected one operational decision record and copied only explicit cost values."
        ),
        "source_opportunity": source_summary,
        "landed_cost_estimate": snapshot,
    }
