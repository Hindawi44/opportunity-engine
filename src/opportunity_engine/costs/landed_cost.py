"""Conservative landed-cost estimate contract.

The contract preserves unknown inputs, separates recoverable cash outflows from
net economic cost, and never changes discovery, ranking, alerts, or the official
opportunity decision.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Callable, Iterable


SCHEMA_VERSION = "landed-cost-estimate-v1"
_COMPONENT_STATUSES = frozenset(
    {"CONFIRMED", "ESTIMATED", "UNKNOWN", "NOT_APPLICABLE"}
)
_ECONOMIC_TREATMENTS = frozenset(
    {
        "ECONOMIC_COST",
        "RECOVERABLE_CASH_OUTFLOW",
        "UNKNOWN",
        "NOT_APPLICABLE",
    }
)
_CURRENCY_CODE = re.compile(r"^[A-Z]{3}$")
_COUNTRY_CODE = re.compile(r"^[A-Z]{2}$")


class LandedCostEstimateError(ValueError):
    """Raised when a Landed Cost Estimate V1 payload violates the contract."""


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LandedCostEstimateError(f"required file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise LandedCostEstimateError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise LandedCostEstimateError(f"JSON root must be an object: {path}")
    return payload


def _non_empty(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LandedCostEstimateError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_non_empty(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _non_empty(value, field_name)


def _optional_non_negative_number(
    value: object,
    field_name: str,
) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LandedCostEstimateError(f"{field_name} must be null or a number")
    if value < 0:
        raise LandedCostEstimateError(f"{field_name} must not be negative")
    return value


def _string_list(
    value: object,
    field_name: str,
    *,
    allow_empty: bool = True,
) -> list[str]:
    if not isinstance(value, list):
        raise LandedCostEstimateError(f"{field_name} must be a list")
    if not allow_empty and not value:
        raise LandedCostEstimateError(f"{field_name} must not be empty")
    result = [_non_empty(item, f"{field_name}[]") for item in value]
    if len(set(result)) != len(result):
        raise LandedCostEstimateError(f"{field_name} must not contain duplicates")
    return result


def _validate_destination(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LandedCostEstimateError("destination must be an object")
    required = {"country_code", "city", "postal_code", "coordinates"}
    if set(value) != required:
        raise LandedCostEstimateError(
            "destination fields are incomplete or unsupported"
        )

    country_code = _non_empty(value["country_code"], "destination.country_code")
    if _COUNTRY_CODE.fullmatch(country_code) is None:
        raise LandedCostEstimateError(
            "destination.country_code must be a two-letter uppercase code"
        )
    city = _non_empty(value["city"], "destination.city")
    postal_code = _optional_non_empty(
        value["postal_code"], "destination.postal_code"
    )

    coordinates = value["coordinates"]
    validated_coordinates: dict[str, float | int] | None = None
    if coordinates is not None:
        if not isinstance(coordinates, dict) or set(coordinates) != {
            "latitude",
            "longitude",
        }:
            raise LandedCostEstimateError(
                "destination.coordinates must be null or contain latitude and longitude"
            )
        latitude = coordinates["latitude"]
        longitude = coordinates["longitude"]
        if (
            isinstance(latitude, bool)
            or not isinstance(latitude, (int, float))
            or isinstance(longitude, bool)
            or not isinstance(longitude, (int, float))
        ):
            raise LandedCostEstimateError(
                "destination coordinates must be numeric"
            )
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise LandedCostEstimateError(
                "destination coordinates are outside valid ranges"
            )
        validated_coordinates = {
            "latitude": latitude,
            "longitude": longitude,
        }

    return {
        "country_code": country_code,
        "city": city,
        "postal_code": postal_code,
        "coordinates": validated_coordinates,
    }


@dataclass(frozen=True, slots=True)
class CostComponentV1:
    """One auditable component of a landed-cost estimate."""

    component_id: str
    label: str
    status: str
    economic_treatment: str
    required_for_qualification: bool
    low_nok: float | int | None
    expected_nok: float | int | None
    high_nok: float | int | None
    source_ref: str | None
    notes: tuple[str, ...]

    def __post_init__(self) -> None:
        _non_empty(self.component_id, "component_id")
        _non_empty(self.label, "label")
        if self.status not in _COMPONENT_STATUSES:
            raise LandedCostEstimateError(
                f"unsupported component status: {self.status}"
            )
        if self.economic_treatment not in _ECONOMIC_TREATMENTS:
            raise LandedCostEstimateError(
                f"unsupported economic_treatment: {self.economic_treatment}"
            )
        if not isinstance(self.required_for_qualification, bool):
            raise LandedCostEstimateError(
                "required_for_qualification must be boolean"
            )

        amounts = (
            _optional_non_negative_number(self.low_nok, "low_nok"),
            _optional_non_negative_number(self.expected_nok, "expected_nok"),
            _optional_non_negative_number(self.high_nok, "high_nok"),
        )

        if self.status in {"UNKNOWN", "NOT_APPLICABLE"}:
            if any(value is not None for value in amounts):
                raise LandedCostEstimateError(
                    f"{self.status} components must not contain amounts"
                )
        else:
            if any(value is None for value in amounts):
                raise LandedCostEstimateError(
                    f"{self.status} components require low, expected, and high amounts"
                )
            low, expected, high = amounts
            assert low is not None and expected is not None and high is not None
            if not low <= expected <= high:
                raise LandedCostEstimateError(
                    "component amounts must satisfy low <= expected <= high"
                )

        if self.status == "CONFIRMED":
            if not (self.low_nok == self.expected_nok == self.high_nok):
                raise LandedCostEstimateError(
                    "CONFIRMED components must use one exact amount"
                )
            if self.source_ref is None:
                raise LandedCostEstimateError(
                    "CONFIRMED components require source_ref"
                )

        if self.status == "ESTIMATED" and not self.notes:
            raise LandedCostEstimateError(
                "ESTIMATED components require at least one note or assumption"
            )

        if self.status == "NOT_APPLICABLE":
            if self.economic_treatment != "NOT_APPLICABLE":
                raise LandedCostEstimateError(
                    "NOT_APPLICABLE status requires NOT_APPLICABLE treatment"
                )
        elif self.economic_treatment == "NOT_APPLICABLE":
            raise LandedCostEstimateError(
                "NOT_APPLICABLE treatment requires NOT_APPLICABLE status"
            )

        if self.status == "UNKNOWN" and self.economic_treatment != "UNKNOWN":
            raise LandedCostEstimateError(
                "UNKNOWN status requires UNKNOWN economic treatment"
            )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CostComponentV1":
        required = {
            "component_id",
            "label",
            "status",
            "economic_treatment",
            "required_for_qualification",
            "low_nok",
            "expected_nok",
            "high_nok",
            "source_ref",
            "notes",
        }
        if set(payload) != required:
            raise LandedCostEstimateError(
                "cost component fields are incomplete or unsupported"
            )
        return cls(
            component_id=_non_empty(payload["component_id"], "component_id"),
            label=_non_empty(payload["label"], "label"),
            status=_non_empty(payload["status"], "status"),
            economic_treatment=_non_empty(
                payload["economic_treatment"], "economic_treatment"
            ),
            required_for_qualification=payload["required_for_qualification"],
            low_nok=_optional_non_negative_number(payload["low_nok"], "low_nok"),
            expected_nok=_optional_non_negative_number(
                payload["expected_nok"], "expected_nok"
            ),
            high_nok=_optional_non_negative_number(payload["high_nok"], "high_nok"),
            source_ref=_optional_non_empty(payload["source_ref"], "source_ref"),
            notes=tuple(_string_list(payload["notes"], "notes")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "label": self.label,
            "status": self.status,
            "economic_treatment": self.economic_treatment,
            "required_for_qualification": self.required_for_qualification,
            "low_nok": self.low_nok,
            "expected_nok": self.expected_nok,
            "high_nok": self.high_nok,
            "source_ref": self.source_ref,
            "notes": list(self.notes),
        }

    @property
    def has_amount(self) -> bool:
        return self.status in {"CONFIRMED", "ESTIMATED"}


@dataclass(frozen=True, slots=True)
class LandedCostEstimateV1:
    """Auditable input contract for one opportunity and destination."""

    estimate_id: str
    opportunity_id: str
    destination: dict[str, Any]
    currency_code: str
    components: tuple[CostComponentV1, ...]
    assumptions: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise LandedCostEstimateError(
                f"schema_version must be {SCHEMA_VERSION}"
            )
        _non_empty(self.estimate_id, "estimate_id")
        _non_empty(self.opportunity_id, "opportunity_id")
        _validate_destination(self.destination)
        if _CURRENCY_CODE.fullmatch(self.currency_code) is None:
            raise LandedCostEstimateError(
                "currency_code must be a three-letter uppercase code"
            )
        if not self.components:
            raise LandedCostEstimateError("components must not be empty")
        component_ids = [component.component_id for component in self.components]
        if len(set(component_ids)) != len(component_ids):
            raise LandedCostEstimateError("component_id values must be unique")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LandedCostEstimateV1":
        required = {
            "schema_version",
            "estimate_id",
            "opportunity_id",
            "destination",
            "currency_code",
            "components",
            "assumptions",
            "evidence_refs",
        }
        if set(payload) != required:
            raise LandedCostEstimateError(
                "estimate fields are incomplete or unsupported"
            )
        raw_components = payload["components"]
        if not isinstance(raw_components, list):
            raise LandedCostEstimateError("components must be a list")
        components: list[CostComponentV1] = []
        for index, raw_component in enumerate(raw_components):
            if not isinstance(raw_component, dict):
                raise LandedCostEstimateError(
                    f"components[{index}] must be an object"
                )
            components.append(CostComponentV1.from_dict(raw_component))
        return cls(
            schema_version=_non_empty(payload["schema_version"], "schema_version"),
            estimate_id=_non_empty(payload["estimate_id"], "estimate_id"),
            opportunity_id=_non_empty(payload["opportunity_id"], "opportunity_id"),
            destination=_validate_destination(payload["destination"]),
            currency_code=_non_empty(payload["currency_code"], "currency_code"),
            components=tuple(components),
            assumptions=tuple(
                _string_list(payload["assumptions"], "assumptions")
            ),
            evidence_refs=tuple(
                _string_list(payload["evidence_refs"], "evidence_refs")
            ),
        )

    @classmethod
    def from_path(cls, path: Path) -> "LandedCostEstimateV1":
        return cls.from_dict(_load_json_object(path))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "estimate_id": self.estimate_id,
            "opportunity_id": self.opportunity_id,
            "destination": deepcopy(self.destination),
            "currency_code": self.currency_code,
            "components": [component.to_dict() for component in self.components],
            "assumptions": list(self.assumptions),
            "evidence_refs": list(self.evidence_refs),
        }


def _sum_range(
    components: Iterable[CostComponentV1],
    predicate: Callable[[CostComponentV1], bool] | None = None,
) -> dict[str, float | int]:
    selected = [
        component
        for component in components
        if component.has_amount and (predicate is None or predicate(component))
    ]
    return {
        "low_nok": sum(component.low_nok or 0 for component in selected),
        "expected_nok": sum(component.expected_nok or 0 for component in selected),
        "high_nok": sum(component.high_nok or 0 for component in selected),
    }


def _destination_precision(destination: dict[str, Any]) -> str:
    if destination["coordinates"] is not None:
        return "COORDINATE_LEVEL"
    if destination["postal_code"] is not None:
        return "POSTAL_CODE_LEVEL"
    return "CITY_LEVEL_INPUT_ONLY"


def build_landed_cost_snapshot(
    estimate: LandedCostEstimateV1,
) -> dict[str, Any]:
    """Build conservative totals and readiness without inventing missing costs."""
    known_components = [
        component for component in estimate.components if component.has_amount
    ]
    missing_inputs = [
        component.component_id
        for component in estimate.components
        if component.status == "UNKNOWN"
    ]
    missing_required_inputs = [
        component.component_id
        for component in estimate.components
        if component.required_for_qualification and component.status == "UNKNOWN"
    ]
    unknown_treatments = [
        component.component_id
        for component in known_components
        if component.economic_treatment == "UNKNOWN"
    ]

    known_cash_required = _sum_range(known_components)
    recoverable_cash_outflow = _sum_range(
        known_components,
        lambda component: (
            component.economic_treatment == "RECOVERABLE_CASH_OUTFLOW"
        ),
    )
    known_net_economic_cost = _sum_range(
        known_components,
        lambda component: component.economic_treatment == "ECONOMIC_COST",
    )

    complete_cash_required: dict[str, float | int] | None = None
    if not missing_required_inputs:
        complete_cash_required = known_cash_required

    complete_net_economic_cost: dict[str, float | int] | None = None
    if not missing_required_inputs and not unknown_treatments:
        complete_net_economic_cost = known_net_economic_cost

    if not known_components:
        status = "REQUIRES_COST_INPUTS"
        confidence = "NONE"
    elif missing_required_inputs or unknown_treatments:
        status = "PARTIAL_ESTIMATE"
        confidence = "LOW" if missing_required_inputs else "MEDIUM"
    elif any(component.status == "ESTIMATED" for component in known_components):
        status = "COMPLETE"
        confidence = "MEDIUM"
    else:
        status = "COMPLETE"
        confidence = "HIGH"

    qualification_ready = (
        status == "COMPLETE"
        and complete_cash_required is not None
        and complete_net_economic_cost is not None
    )

    return {
        **estimate.to_dict(),
        "estimate_status": status,
        "confidence": confidence,
        "destination_precision": _destination_precision(estimate.destination),
        "known_cash_required_range": known_cash_required,
        "complete_cash_required_range": complete_cash_required,
        "known_recoverable_cash_outflow_range": recoverable_cash_outflow,
        "known_net_economic_cost_range": known_net_economic_cost,
        "complete_net_economic_cost_range": complete_net_economic_cost,
        "missing_inputs": missing_inputs,
        "missing_required_inputs": missing_required_inputs,
        "unknown_economic_treatments": unknown_treatments,
        "qualification_readiness": {
            "ready": qualification_ready,
            "status": (
                "QUALIFICATION_COST_READY"
                if qualification_ready
                else "REQUIRES_COST_REVIEW"
            ),
        },
        "scope": {
            "route_or_shipping_quote_lookup_enabled": False,
            "tax_or_customs_rule_lookup_enabled": False,
            "changes_final_decision": False,
            "changes_ranking": False,
            "changes_top5": False,
            "changes_alerts": False,
            "automatic_purchase_allowed": False,
        },
    }
