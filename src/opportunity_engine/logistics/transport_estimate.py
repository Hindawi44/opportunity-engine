"""Conservative transport-estimate input contract.

The contract records route, shipment, handling, and quote evidence without
performing map, carrier, tax, or external-price lookups. Unknown inputs remain
``None`` and never become zero.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any


SCHEMA_VERSION = "transport-estimate-input-v1"
_QUOTE_STATUSES = frozenset({"UNKNOWN", "ESTIMATED", "CONFIRMED", "NOT_APPLICABLE"})
_TRANSPORT_MODES = frozenset({"UNKNOWN", "SELF_PICKUP", "CARRIER", "COURIER", "FREIGHT"})
_CARGO_TYPES = frozenset({"UNKNOWN", "BOXES", "PALLETIZED", "LOOSE", "BULKY", "MIXED"})
_COUNTRY_CODE = re.compile(r"^[A-Z]{2}$")
_CURRENCY_CODE = re.compile(r"^[A-Z]{3}$")


class TransportEstimateError(ValueError):
    """Raised when a Transport Estimate Input V1 payload is invalid."""


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TransportEstimateError(f"required file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise TransportEstimateError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise TransportEstimateError(f"JSON root must be an object: {path}")
    return payload


def _non_empty(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TransportEstimateError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_non_empty(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _non_empty(value, field_name)


def _optional_positive_number(value: object, field_name: str) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TransportEstimateError(f"{field_name} must be null or a number")
    if value <= 0:
        raise TransportEstimateError(f"{field_name} must be positive when provided")
    return value


def _optional_positive_integer(value: object, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise TransportEstimateError(f"{field_name} must be null or a positive integer")
    return value


def _optional_bool(value: object, field_name: str) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    raise TransportEstimateError(f"{field_name} must be null or boolean")


def _string_list(value: object, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise TransportEstimateError(f"{field_name} must be a list")
    result = [_non_empty(item, f"{field_name}[]") for item in value]
    if len(set(result)) != len(result):
        raise TransportEstimateError(f"{field_name} must not contain duplicates")
    return result


def _validate_location(value: object, field_name: str, *, city_required: bool) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TransportEstimateError(f"{field_name} must be an object")
    required = {"country_code", "city", "postal_code", "coordinates"}
    if set(value) != required:
        raise TransportEstimateError(f"{field_name} fields are incomplete or unsupported")

    country_code = _non_empty(value["country_code"], f"{field_name}.country_code")
    if _COUNTRY_CODE.fullmatch(country_code) is None:
        raise TransportEstimateError(
            f"{field_name}.country_code must be a two-letter uppercase code"
        )
    city = (
        _non_empty(value["city"], f"{field_name}.city")
        if city_required
        else _optional_non_empty(value["city"], f"{field_name}.city")
    )
    postal_code = _optional_non_empty(value["postal_code"], f"{field_name}.postal_code")

    coordinates = value["coordinates"]
    validated_coordinates: dict[str, float | int] | None = None
    if coordinates is not None:
        if not isinstance(coordinates, dict) or set(coordinates) != {"latitude", "longitude"}:
            raise TransportEstimateError(
                f"{field_name}.coordinates must be null or contain latitude and longitude"
            )
        latitude = coordinates["latitude"]
        longitude = coordinates["longitude"]
        if (
            isinstance(latitude, bool)
            or not isinstance(latitude, (int, float))
            or isinstance(longitude, bool)
            or not isinstance(longitude, (int, float))
        ):
            raise TransportEstimateError(f"{field_name} coordinates must be numeric")
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise TransportEstimateError(f"{field_name} coordinates are outside valid ranges")
        validated_coordinates = {"latitude": latitude, "longitude": longitude}

    return {
        "country_code": country_code,
        "city": city,
        "postal_code": postal_code,
        "coordinates": validated_coordinates,
    }


def _validate_shipment(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TransportEstimateError("shipment must be an object")
    required = {
        "cargo_type",
        "weight_kg",
        "volume_m3",
        "pallet_count",
        "package_count",
        "item_count",
        "longest_length_m",
    }
    if set(value) != required:
        raise TransportEstimateError("shipment fields are incomplete or unsupported")
    cargo_type = _non_empty(value["cargo_type"], "shipment.cargo_type")
    if cargo_type not in _CARGO_TYPES:
        raise TransportEstimateError(f"unsupported shipment.cargo_type: {cargo_type}")
    return {
        "cargo_type": cargo_type,
        "weight_kg": _optional_positive_number(value["weight_kg"], "shipment.weight_kg"),
        "volume_m3": _optional_positive_number(value["volume_m3"], "shipment.volume_m3"),
        "pallet_count": _optional_positive_integer(value["pallet_count"], "shipment.pallet_count"),
        "package_count": _optional_positive_integer(value["package_count"], "shipment.package_count"),
        "item_count": _optional_positive_integer(value["item_count"], "shipment.item_count"),
        "longest_length_m": _optional_positive_number(
            value["longest_length_m"], "shipment.longest_length_m"
        ),
    }


def _validate_handling(value: object) -> dict[str, bool | None]:
    if not isinstance(value, dict):
        raise TransportEstimateError("handling must be an object")
    required = {
        "loading_required",
        "unloading_required",
        "forklift_required",
        "tail_lift_required",
        "dismantling_required",
    }
    if set(value) != required:
        raise TransportEstimateError("handling fields are incomplete or unsupported")
    return {key: _optional_bool(value[key], f"handling.{key}") for key in sorted(required)}


@dataclass(frozen=True, slots=True)
class TransportQuoteV1:
    """Manual or externally supplied quote evidence; no lookup is performed."""

    status: str
    currency_code: str
    low_nok: float | int | None
    expected_nok: float | int | None
    high_nok: float | int | None
    source_ref: str | None
    notes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.status not in _QUOTE_STATUSES:
            raise TransportEstimateError(f"unsupported quote status: {self.status}")
        if _CURRENCY_CODE.fullmatch(self.currency_code) is None:
            raise TransportEstimateError("quote.currency_code must be a three-letter uppercase code")
        amounts = (
            _optional_positive_number(self.low_nok, "quote.low_nok"),
            _optional_positive_number(self.expected_nok, "quote.expected_nok"),
            _optional_positive_number(self.high_nok, "quote.high_nok"),
        )
        if self.status in {"UNKNOWN", "NOT_APPLICABLE"}:
            if any(amount is not None for amount in amounts):
                raise TransportEstimateError(f"{self.status} quote must not contain amounts")
        else:
            if any(amount is None for amount in amounts):
                raise TransportEstimateError(f"{self.status} quote requires low, expected, and high")
            low, expected, high = amounts
            assert low is not None and expected is not None and high is not None
            if not low <= expected <= high:
                raise TransportEstimateError("quote amounts must satisfy low <= expected <= high")
        if self.status == "CONFIRMED":
            if not (self.low_nok == self.expected_nok == self.high_nok):
                raise TransportEstimateError("CONFIRMED quote must use one exact amount")
            if self.source_ref is None:
                raise TransportEstimateError("CONFIRMED quote requires source_ref")
        if self.status == "ESTIMATED" and not self.notes:
            raise TransportEstimateError("ESTIMATED quote requires at least one assumption note")
        if self.status == "NOT_APPLICABLE" and not self.notes:
            raise TransportEstimateError("NOT_APPLICABLE quote requires a reason note")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TransportQuoteV1":
        required = {
            "status",
            "currency_code",
            "low_nok",
            "expected_nok",
            "high_nok",
            "source_ref",
            "notes",
        }
        if set(payload) != required:
            raise TransportEstimateError("quote fields are incomplete or unsupported")
        return cls(
            status=_non_empty(payload["status"], "quote.status"),
            currency_code=_non_empty(payload["currency_code"], "quote.currency_code"),
            low_nok=payload["low_nok"],
            expected_nok=payload["expected_nok"],
            high_nok=payload["high_nok"],
            source_ref=_optional_non_empty(payload["source_ref"], "quote.source_ref"),
            notes=tuple(_string_list(payload["notes"], "quote.notes")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "currency_code": self.currency_code,
            "low_nok": self.low_nok,
            "expected_nok": self.expected_nok,
            "high_nok": self.high_nok,
            "source_ref": self.source_ref,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class TransportEstimateInputV1:
    """Auditable transport inputs for one opportunity and buyer destination."""

    estimate_id: str
    opportunity_id: str
    origin: dict[str, Any]
    destination: dict[str, Any]
    shipment: dict[str, Any]
    handling: dict[str, bool | None]
    transport_mode: str
    quote: TransportQuoteV1
    assumptions: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise TransportEstimateError(f"schema_version must be {SCHEMA_VERSION}")
        _non_empty(self.estimate_id, "estimate_id")
        _non_empty(self.opportunity_id, "opportunity_id")
        _validate_location(self.origin, "origin", city_required=False)
        _validate_location(self.destination, "destination", city_required=True)
        _validate_shipment(self.shipment)
        _validate_handling(self.handling)
        if self.transport_mode not in _TRANSPORT_MODES:
            raise TransportEstimateError(f"unsupported transport_mode: {self.transport_mode}")
        if self.quote.currency_code != "NOK":
            raise TransportEstimateError("Transport Estimate Input V1 currently requires NOK quotes")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TransportEstimateInputV1":
        required = {
            "schema_version",
            "estimate_id",
            "opportunity_id",
            "origin",
            "destination",
            "shipment",
            "handling",
            "transport_mode",
            "quote",
            "assumptions",
            "evidence_refs",
        }
        if set(payload) != required:
            raise TransportEstimateError("transport estimate fields are incomplete or unsupported")
        if not isinstance(payload["quote"], dict):
            raise TransportEstimateError("quote must be an object")
        return cls(
            schema_version=_non_empty(payload["schema_version"], "schema_version"),
            estimate_id=_non_empty(payload["estimate_id"], "estimate_id"),
            opportunity_id=_non_empty(payload["opportunity_id"], "opportunity_id"),
            origin=_validate_location(payload["origin"], "origin", city_required=False),
            destination=_validate_location(payload["destination"], "destination", city_required=True),
            shipment=_validate_shipment(payload["shipment"]),
            handling=_validate_handling(payload["handling"]),
            transport_mode=_non_empty(payload["transport_mode"], "transport_mode"),
            quote=TransportQuoteV1.from_dict(payload["quote"]),
            assumptions=tuple(_string_list(payload["assumptions"], "assumptions")),
            evidence_refs=tuple(_string_list(payload["evidence_refs"], "evidence_refs")),
        )

    @classmethod
    def from_path(cls, path: Path) -> "TransportEstimateInputV1":
        return cls.from_dict(_load_json_object(path))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "estimate_id": self.estimate_id,
            "opportunity_id": self.opportunity_id,
            "origin": deepcopy(self.origin),
            "destination": deepcopy(self.destination),
            "shipment": deepcopy(self.shipment),
            "handling": deepcopy(self.handling),
            "transport_mode": self.transport_mode,
            "quote": self.quote.to_dict(),
            "assumptions": list(self.assumptions),
            "evidence_refs": list(self.evidence_refs),
        }


def _route_precision(estimate: TransportEstimateInputV1) -> str:
    origin = estimate.origin
    destination = estimate.destination
    if origin["coordinates"] is not None and destination["coordinates"] is not None:
        return "COORDINATE_LEVEL"
    if origin["postal_code"] is not None and destination["postal_code"] is not None:
        return "POSTAL_CODE_LEVEL"
    if origin["city"] is not None:
        return "CITY_LEVEL_INPUT_ONLY"
    return "INCOMPLETE"


def build_transport_estimate_snapshot(estimate: TransportEstimateInputV1) -> dict[str, Any]:
    """Resolve readiness and confidence without deriving a transport price."""
    route_precision = _route_precision(estimate)
    metric_fields = (
        "weight_kg",
        "volume_m3",
        "pallet_count",
        "package_count",
        "item_count",
        "longest_length_m",
    )
    known_metrics = [field for field in metric_fields if estimate.shipment[field] is not None]
    unknown_handling = [field for field, value in estimate.handling.items() if value is None]
    missing_inputs: list[str] = []
    if route_precision == "INCOMPLETE":
        missing_inputs.append("origin.city_or_postal_code_or_coordinates")
    if estimate.shipment["cargo_type"] == "UNKNOWN":
        missing_inputs.append("shipment.cargo_type")
    if not known_metrics:
        missing_inputs.append("shipment.one_of_weight_volume_pallet_package_item_or_length")
    if estimate.transport_mode == "UNKNOWN":
        missing_inputs.append("transport_mode")
    missing_inputs.extend(f"handling.{field}" for field in unknown_handling)

    quote = estimate.quote
    if quote.status == "CONFIRMED":
        status = "CONFIRMED_QUOTE"
        confidence = "HIGH"
        landed_cost_input_ready = True
    elif quote.status == "ESTIMATED":
        status = "ESTIMATE_AVAILABLE"
        confidence = "MEDIUM"
        landed_cost_input_ready = True
    elif quote.status == "NOT_APPLICABLE":
        status = "TRANSPORT_NOT_APPLICABLE"
        confidence = "HIGH"
        landed_cost_input_ready = True
    elif route_precision == "INCOMPLETE":
        status = "REQUIRES_ROUTE_INPUTS"
        confidence = "NONE"
        landed_cost_input_ready = False
    elif estimate.shipment["cargo_type"] == "UNKNOWN" or not known_metrics:
        status = "REQUIRES_SHIPMENT_INPUTS"
        confidence = "LOW"
        landed_cost_input_ready = False
    elif estimate.transport_mode == "UNKNOWN":
        status = "REQUIRES_TRANSPORT_MODE"
        confidence = "LOW"
        landed_cost_input_ready = False
    else:
        status = "READY_FOR_MANUAL_QUOTE"
        confidence = "LOW"
        landed_cost_input_ready = False

    quote_range = None
    if quote.status in {"ESTIMATED", "CONFIRMED"}:
        quote_range = {
            "low_nok": quote.low_nok,
            "expected_nok": quote.expected_nok,
            "high_nok": quote.high_nok,
        }

    return {
        **estimate.to_dict(),
        "transport_status": status,
        "confidence": confidence,
        "route_precision": route_precision,
        "known_shipment_metrics": known_metrics,
        "unknown_handling_requirements": unknown_handling,
        "missing_inputs": missing_inputs,
        "transport_cost_range": quote_range,
        "landed_cost_input_readiness": {
            "ready": landed_cost_input_ready,
            "status": (
                "TRANSPORT_COMPONENT_READY"
                if landed_cost_input_ready
                else "TRANSPORT_COMPONENT_PENDING"
            ),
        },
        "scope": {
            "map_or_route_lookup_enabled": False,
            "carrier_quote_lookup_enabled": False,
            "external_price_lookup_enabled": False,
            "automatic_distance_calculation_enabled": False,
            "changes_final_decision": False,
            "changes_ranking": False,
            "changes_top5": False,
            "changes_alerts": False,
            "automatic_purchase_allowed": False,
        },
    }
