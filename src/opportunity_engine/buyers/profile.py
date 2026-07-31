"""Stable buyer-profile contract for opportunity matching.

Buyer Profile V1 records confirmed buyer facts and preserves unknown commercial
constraints as ``None``. It is configuration-only: it does not rank opportunities,
calculate landed cost, or change any discovery or final decision.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any


SCHEMA_VERSION = "buyer-profile-v1"
_ALLOWED_BUYER_TYPES = frozenset({"BUSINESS", "INDIVIDUAL"})
_ALLOWED_RISK_TOLERANCES = frozenset({"LOW", "MEDIUM", "HIGH"})
_COUNTRY_CODE = re.compile(r"^[A-Z]{2}$")
_CURRENCY_CODE = re.compile(r"^[A-Z]{3}$")

_REQUIRED_CONSTRAINTS_FOR_MATCHING = (
    "commercial_constraints.budget_nok",
    "commercial_constraints.maximum_shipping_nok",
    "commercial_constraints.minimum_expected_margin_ratio",
    "risk_policy.risk_tolerance",
)


class BuyerProfileError(ValueError):
    """Raised when a Buyer Profile V1 payload violates the stable contract."""


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BuyerProfileError(f"required file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise BuyerProfileError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise BuyerProfileError(f"JSON root must be an object: {path}")
    return payload


def _non_empty(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BuyerProfileError(f"{field_name} must be a non-empty string")
    return value.strip()


def _object(value: object, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BuyerProfileError(f"{field_name} must be an object")
    return deepcopy(value)


def _string_list(value: object, field_name: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise BuyerProfileError(f"{field_name} must be a non-empty list")
    result = [_non_empty(item, f"{field_name}[]") for item in value]
    if len(set(result)) != len(result):
        raise BuyerProfileError(f"{field_name} must not contain duplicates")
    return result


def _optional_non_negative_number(value: object, field_name: str) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BuyerProfileError(f"{field_name} must be null or a number")
    if value < 0:
        raise BuyerProfileError(f"{field_name} must not be negative")
    return value


def _path_value(payload: dict[str, Any], dotted_path: str) -> object:
    current: object = payload
    for part in dotted_path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


@dataclass(frozen=True, slots=True)
class BuyerProfileV1:
    """Confirmed buyer identity plus conservative commercial constraints."""

    profile_id: str
    buyer_type: str
    display_name: str
    home_market_profile_id: str
    location: dict[str, Any]
    settlement_currency: str
    interests: dict[str, Any]
    commercial_constraints: dict[str, Any]
    operational_capacity: dict[str, Any]
    risk_policy: dict[str, Any]
    safety: dict[str, Any]
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise BuyerProfileError(f"schema_version must be {SCHEMA_VERSION}")
        _non_empty(self.profile_id, "profile_id")
        if self.buyer_type not in _ALLOWED_BUYER_TYPES:
            raise BuyerProfileError(f"unsupported buyer_type: {self.buyer_type}")
        _non_empty(self.display_name, "display_name")
        _non_empty(self.home_market_profile_id, "home_market_profile_id")

        country_code = _non_empty(self.location.get("country_code"), "location.country_code")
        if _COUNTRY_CODE.fullmatch(country_code) is None:
            raise BuyerProfileError("location.country_code must be a two-letter uppercase code")
        _non_empty(self.location.get("city"), "location.city")
        if self.location.get("postal_code") is not None:
            _non_empty(self.location.get("postal_code"), "location.postal_code")
        coordinates = self.location.get("coordinates")
        if coordinates is not None:
            if not isinstance(coordinates, dict):
                raise BuyerProfileError("location.coordinates must be null or an object")
            latitude = coordinates.get("latitude")
            longitude = coordinates.get("longitude")
            if not isinstance(latitude, (int, float)) or isinstance(latitude, bool):
                raise BuyerProfileError("location.coordinates.latitude must be numeric")
            if not isinstance(longitude, (int, float)) or isinstance(longitude, bool):
                raise BuyerProfileError("location.coordinates.longitude must be numeric")
            if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
                raise BuyerProfileError("location.coordinates are outside valid ranges")

        if _CURRENCY_CODE.fullmatch(self.settlement_currency) is None:
            raise BuyerProfileError("settlement_currency must be a three-letter uppercase code")
        categories = _string_list(self.interests.get("categories"), "interests.categories")
        markets = _string_list(self.interests.get("markets"), "interests.markets")
        if any(_COUNTRY_CODE.fullmatch(code) is None for code in markets):
            raise BuyerProfileError("interests.markets must contain two-letter uppercase codes")
        if not categories:
            raise BuyerProfileError("interests.categories must not be empty")

        required_commercial = {
            "budget_nok",
            "maximum_purchase_price_nok",
            "maximum_shipping_nok",
            "minimum_expected_margin_ratio",
            "maximum_total_exposure_nok",
            "maximum_sell_through_months",
        }
        if set(self.commercial_constraints) != required_commercial:
            raise BuyerProfileError("commercial_constraints fields are incomplete or unsupported")
        for field_name in required_commercial - {
            "minimum_expected_margin_ratio",
            "maximum_sell_through_months",
        }:
            _optional_non_negative_number(
                self.commercial_constraints[field_name],
                f"commercial_constraints.{field_name}",
            )
        margin = self.commercial_constraints["minimum_expected_margin_ratio"]
        if margin is not None:
            _optional_non_negative_number(
                margin,
                "commercial_constraints.minimum_expected_margin_ratio",
            )
            if margin > 1:
                raise BuyerProfileError(
                    "commercial_constraints.minimum_expected_margin_ratio must be between 0 and 1"
                )
        months = self.commercial_constraints["maximum_sell_through_months"]
        if months is not None and (
            isinstance(months, bool) or not isinstance(months, int) or months <= 0
        ):
            raise BuyerProfileError(
                "commercial_constraints.maximum_sell_through_months must be null or a positive integer"
            )

        required_capacity = {
            "storage_available",
            "pickup_capability",
            "pallet_handling_capability",
        }
        if set(self.operational_capacity) != required_capacity:
            raise BuyerProfileError("operational_capacity fields are incomplete or unsupported")
        for key, value in self.operational_capacity.items():
            if value is not None and not isinstance(value, bool):
                raise BuyerProfileError(f"operational_capacity.{key} must be null or boolean")

        risk_tolerance = self.risk_policy.get("risk_tolerance")
        if risk_tolerance is not None and risk_tolerance not in _ALLOWED_RISK_TOLERANCES:
            raise BuyerProfileError(f"unsupported risk_tolerance: {risk_tolerance}")
        for key in (
            "requires_verified_seller",
            "requires_verified_active_listing",
            "requires_complete_landed_cost",
            "unknown_constraints_block_qualification",
        ):
            if self.risk_policy.get(key) is not True:
                raise BuyerProfileError(f"risk_policy.{key} must be true")

        for key in (
            "automatic_purchase_allowed",
            "automatic_bid_allowed",
            "automatic_contact_allowed",
        ):
            if self.safety.get(key) is not False:
                raise BuyerProfileError(f"safety.{key} must be false")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BuyerProfileV1":
        required = {
            "schema_version",
            "profile_id",
            "buyer_type",
            "display_name",
            "home_market_profile_id",
            "location",
            "settlement_currency",
            "interests",
            "commercial_constraints",
            "operational_capacity",
            "risk_policy",
            "safety",
        }
        missing = sorted(required - payload.keys())
        extra = sorted(payload.keys() - required)
        if missing:
            raise BuyerProfileError("missing profile fields: " + ", ".join(missing))
        if extra:
            raise BuyerProfileError("unsupported profile fields: " + ", ".join(extra))
        return cls(
            schema_version=_non_empty(payload["schema_version"], "schema_version"),
            profile_id=_non_empty(payload["profile_id"], "profile_id"),
            buyer_type=_non_empty(payload["buyer_type"], "buyer_type"),
            display_name=_non_empty(payload["display_name"], "display_name"),
            home_market_profile_id=_non_empty(
                payload["home_market_profile_id"], "home_market_profile_id"
            ),
            location=_object(payload["location"], "location"),
            settlement_currency=_non_empty(
                payload["settlement_currency"], "settlement_currency"
            ),
            interests=_object(payload["interests"], "interests"),
            commercial_constraints=_object(
                payload["commercial_constraints"], "commercial_constraints"
            ),
            operational_capacity=_object(
                payload["operational_capacity"], "operational_capacity"
            ),
            risk_policy=_object(payload["risk_policy"], "risk_policy"),
            safety=_object(payload["safety"], "safety"),
        )

    @classmethod
    def from_path(cls, path: Path) -> "BuyerProfileV1":
        return cls.from_dict(_load_json_object(path))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "buyer_type": self.buyer_type,
            "display_name": self.display_name,
            "home_market_profile_id": self.home_market_profile_id,
            "location": deepcopy(self.location),
            "settlement_currency": self.settlement_currency,
            "interests": deepcopy(self.interests),
            "commercial_constraints": deepcopy(self.commercial_constraints),
            "operational_capacity": deepcopy(self.operational_capacity),
            "risk_policy": deepcopy(self.risk_policy),
            "safety": deepcopy(self.safety),
        }

    def missing_matching_constraints(self) -> tuple[str, ...]:
        payload = self.to_dict()
        return tuple(
            path
            for path in _REQUIRED_CONSTRAINTS_FOR_MATCHING
            if _path_value(payload, path) is None
        )


def build_buyer_profile_snapshot(
    buyer: BuyerProfileV1,
    market_profile: object,
) -> dict[str, Any]:
    """Resolve buyer identity against a loaded MarketProfileV1-like object."""
    market_profile_id = getattr(market_profile, "profile_id", None)
    market_code = getattr(market_profile, "market_code", None)
    currency_code = getattr(market_profile, "currency_code", None)
    if buyer.home_market_profile_id != market_profile_id:
        raise BuyerProfileError("buyer home_market_profile_id does not match market profile")
    if buyer.location["country_code"] != market_code:
        raise BuyerProfileError("buyer country does not match home market")
    if buyer.settlement_currency != currency_code:
        raise BuyerProfileError("buyer settlement currency does not match home market")
    if market_code not in buyer.interests["markets"]:
        raise BuyerProfileError("buyer interests must include the home market")

    missing = buyer.missing_matching_constraints()
    ready = not missing
    return {
        **buyer.to_dict(),
        "matching_readiness": {
            "ready": ready,
            "status": "READY" if ready else "BLOCKED_MISSING_CONSTRAINTS",
            "missing_required_constraints": list(missing),
        },
        "scope": {
            "landed_cost_calculation_enabled": False,
            "opportunity_ranking_enabled": False,
            "decision_changes_enabled": False,
        },
    }
