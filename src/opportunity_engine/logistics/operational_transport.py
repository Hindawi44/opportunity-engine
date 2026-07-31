"""Build a zero-safe operational transport input from landed-cost selection.

The adapter reuses the exact opportunity selected by the operational landed-cost
sidecar, combines it with the buyer destination and market boundary, and copies
only explicit structured logistics values. It never parses listing prose,
calculates distance, requests a quote, or invents a transport price.
"""
from __future__ import annotations

from typing import Any

from opportunity_engine.buyers import BuyerProfileV1
from opportunity_engine.markets import MarketProfileV1

from .transport_estimate import (
    TransportEstimateError,
    TransportEstimateInputV1,
    TransportQuoteV1,
    build_transport_estimate_snapshot,
)


EXPORT_SCHEMA_VERSION = "operational-transport-input-export-v1"
_SUPPORTED_CARGO_TYPES = frozenset(
    {"UNKNOWN", "BOXES", "PALLETIZED", "LOOSE", "BULKY", "MIXED"}
)
_SUPPORTED_TRANSPORT_MODES = frozenset(
    {"UNKNOWN", "SELF_PICKUP", "CARRIER", "COURIER", "FREIGHT"}
)
_SHIPMENT_FIELDS = (
    "weight_kg",
    "volume_m3",
    "pallet_count",
    "package_count",
    "item_count",
    "longest_length_m",
)
_HANDLING_FIELDS = (
    "loading_required",
    "unloading_required",
    "forklift_required",
    "tail_lift_required",
    "dismantling_required",
)


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
        raise TransportEstimateError(f"{field_name} must be null or numeric")
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


def _optional_coordinates(value: object, field_name: str) -> dict[str, float | int] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {"latitude", "longitude"}:
        raise TransportEstimateError(
            f"{field_name} must be null or contain latitude and longitude"
        )
    latitude = value["latitude"]
    longitude = value["longitude"]
    if (
        isinstance(latitude, bool)
        or not isinstance(latitude, (int, float))
        or isinstance(longitude, bool)
        or not isinstance(longitude, (int, float))
    ):
        raise TransportEstimateError(f"{field_name} values must be numeric")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise TransportEstimateError(f"{field_name} values are outside valid ranges")
    return {"latitude": latitude, "longitude": longitude}


def _validate_context(buyer: BuyerProfileV1, market: MarketProfileV1) -> None:
    if buyer.home_market_profile_id != market.profile_id:
        raise TransportEstimateError("buyer home market does not match market profile")
    if buyer.location["country_code"] != market.market_code:
        raise TransportEstimateError("buyer country does not match market profile")
    if buyer.settlement_currency != market.currency_code:
        raise TransportEstimateError("buyer currency does not match market profile")


def _transport_component(landed_snapshot: dict[str, Any]) -> dict[str, Any]:
    components = landed_snapshot.get("components")
    if not isinstance(components, list):
        raise TransportEstimateError("landed_cost_estimate.components must be a list")
    matches = [
        component
        for component in components
        if isinstance(component, dict) and component.get("component_id") == "transport"
    ]
    if len(matches) != 1:
        raise TransportEstimateError(
            "landed-cost snapshot must contain exactly one transport component"
        )
    return matches[0]


def _quote_from_transport_component(component: dict[str, Any]) -> TransportQuoteV1:
    status = _non_empty(component.get("status"), "transport_component.status")
    if status not in {"UNKNOWN", "ESTIMATED", "CONFIRMED", "NOT_APPLICABLE"}:
        raise TransportEstimateError(f"unsupported transport component status: {status}")

    raw_notes = component.get("notes", [])
    if not isinstance(raw_notes, list) or any(
        not isinstance(note, str) or not note.strip() for note in raw_notes
    ):
        raise TransportEstimateError("transport_component.notes must be a string list")
    notes = tuple(note.strip() for note in raw_notes)
    source_ref = _optional_non_empty(
        component.get("source_ref"), "transport_component.source_ref"
    )

    if status == "UNKNOWN":
        return TransportQuoteV1(
            status="UNKNOWN",
            currency_code="NOK",
            low_nok=None,
            expected_nok=None,
            high_nok=None,
            source_ref=None,
            notes=(),
        )
    if status == "NOT_APPLICABLE":
        return TransportQuoteV1(
            status="NOT_APPLICABLE",
            currency_code="NOK",
            low_nok=None,
            expected_nok=None,
            high_nok=None,
            source_ref=source_ref,
            notes=notes or (
                "The landed-cost transport component is documented as not applicable.",
            ),
        )

    low = _optional_positive_number(
        component.get("low_nok"), "transport_component.low_nok"
    )
    expected = _optional_positive_number(
        component.get("expected_nok"), "transport_component.expected_nok"
    )
    high = _optional_positive_number(
        component.get("high_nok"), "transport_component.high_nok"
    )
    return TransportQuoteV1(
        status=status,
        currency_code="NOK",
        low_nok=low,
        expected_nok=expected,
        high_nok=high,
        source_ref=source_ref,
        notes=(
            notes
            if notes
            else (
                "Transport amount copied from the operational landed-cost sidecar.",
            )
        ),
    )


def _shipment_from_source(source: dict[str, Any]) -> dict[str, Any]:
    raw_cargo_type = source.get("cargo_type")
    cargo_type = "UNKNOWN" if raw_cargo_type is None else _non_empty(
        raw_cargo_type, "source_opportunity.cargo_type"
    ).upper()
    if cargo_type not in _SUPPORTED_CARGO_TYPES:
        raise TransportEstimateError(f"unsupported source cargo_type: {cargo_type}")

    return {
        "cargo_type": cargo_type,
        "weight_kg": _optional_positive_number(
            source.get("weight_kg"), "source_opportunity.weight_kg"
        ),
        "volume_m3": _optional_positive_number(
            source.get("volume_m3"), "source_opportunity.volume_m3"
        ),
        "pallet_count": _optional_positive_integer(
            source.get("pallet_count"), "source_opportunity.pallet_count"
        ),
        "package_count": _optional_positive_integer(
            source.get("package_count"), "source_opportunity.package_count"
        ),
        "item_count": _optional_positive_integer(
            source.get("item_count"), "source_opportunity.item_count"
        ),
        "longest_length_m": _optional_positive_number(
            source.get("longest_length_m"), "source_opportunity.longest_length_m"
        ),
    }


def _handling_from_source(source: dict[str, Any]) -> dict[str, bool | None]:
    return {
        field: _optional_bool(source.get(field), f"source_opportunity.{field}")
        for field in _HANDLING_FIELDS
    }


def build_operational_transport_export(
    landed_cost_payload: dict[str, Any],
    buyer: BuyerProfileV1,
    market: MarketProfileV1,
) -> dict[str, Any]:
    """Build a zero-safe transport-input sidecar for the selected opportunity."""
    if not isinstance(landed_cost_payload, dict):
        raise TransportEstimateError("landed-cost payload must be an object")
    _validate_context(buyer, market)

    source_buyer_id = landed_cost_payload.get("buyer_profile_id")
    if source_buyer_id is not None and source_buyer_id != buyer.profile_id:
        raise TransportEstimateError("landed-cost buyer_profile_id does not match buyer")

    base = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "source_schema_version": landed_cost_payload.get("schema_version"),
        "buyer_profile_id": buyer.profile_id,
        "market_profile_id": market.profile_id,
        "origin_country_basis": "MARKET_PROFILE",
    }

    selection_status = landed_cost_payload.get("selection_status")
    if selection_status == "NO_ELIGIBLE_OPPORTUNITY":
        return {
            **base,
            "selection_status": "NO_ELIGIBLE_OPPORTUNITY",
            "selection_reason": (
                "The operational landed-cost sidecar did not select an opportunity."
            ),
            "source_opportunity": None,
            "transport_input": None,
            "transport_snapshot": None,
        }
    if selection_status != "SELECTED":
        raise TransportEstimateError(
            "landed-cost selection_status must be SELECTED or NO_ELIGIBLE_OPPORTUNITY"
        )

    source = landed_cost_payload.get("source_opportunity")
    landed_snapshot = landed_cost_payload.get("landed_cost_estimate")
    if not isinstance(source, dict) or not isinstance(landed_snapshot, dict):
        raise TransportEstimateError(
            "selected landed-cost payload requires source_opportunity and landed_cost_estimate"
        )

    opportunity_id = _non_empty(
        source.get("opportunity_id"), "source_opportunity.opportunity_id"
    )
    if landed_snapshot.get("opportunity_id") != opportunity_id:
        raise TransportEstimateError(
            "source opportunity does not match landed-cost opportunity_id"
        )

    destination = landed_snapshot.get("destination")
    if destination != buyer.location:
        raise TransportEstimateError(
            "landed-cost destination does not match the buyer profile location"
        )
    if landed_snapshot.get("currency_code") != buyer.settlement_currency:
        raise TransportEstimateError(
            "landed-cost currency does not match the buyer settlement currency"
        )

    source_country = source.get("source_country_code")
    origin_country = (
        market.market_code
        if source_country is None
        else _non_empty(source_country, "source_opportunity.source_country_code")
    )
    if origin_country != market.market_code:
        raise TransportEstimateError(
            "source country falls outside the selected domestic market profile"
        )

    raw_mode = source.get("transport_mode")
    transport_mode = "UNKNOWN" if raw_mode is None else _non_empty(
        raw_mode, "source_opportunity.transport_mode"
    ).upper()
    if transport_mode not in _SUPPORTED_TRANSPORT_MODES:
        raise TransportEstimateError(
            f"unsupported source transport_mode: {transport_mode}"
        )

    transport_component = _transport_component(landed_snapshot)
    estimate = TransportEstimateInputV1(
        estimate_id=f"transport-{opportunity_id}-to-{buyer.profile_id.lower()}",
        opportunity_id=opportunity_id,
        origin={
            "country_code": origin_country,
            "city": _optional_non_empty(
                source.get("source_city"), "source_opportunity.source_city"
            ),
            "postal_code": _optional_non_empty(
                source.get("source_postal_code"),
                "source_opportunity.source_postal_code",
            ),
            "coordinates": _optional_coordinates(
                source.get("source_coordinates"),
                "source_opportunity.source_coordinates",
            ),
        },
        destination={
            "country_code": buyer.location["country_code"],
            "city": buyer.location["city"],
            "postal_code": buyer.location.get("postal_code"),
            "coordinates": buyer.location.get("coordinates"),
        },
        shipment=_shipment_from_source(source),
        handling=_handling_from_source(source),
        transport_mode=transport_mode,
        quote=_quote_from_transport_component(transport_component),
        assumptions=(
            "Origin country is taken from the Norway market profile when the selected source does not provide a structured country code.",
            "No shipment measurements are parsed from listing title or prose.",
            "No map, route, distance, carrier, or external-price lookup was performed.",
        ),
        evidence_refs=(
            f"data/operational_landed_cost_v1.json#{opportunity_id}",
            f"config/buyers/mahmoud_namsos_v1.json#{buyer.profile_id}",
            f"config/markets/no_v1.json#{market.profile_id}",
        ),
    )
    snapshot = build_transport_estimate_snapshot(estimate)

    return {
        **base,
        "selection_status": "SELECTED",
        "selection_reason": (
            "Reused the operational landed-cost selection and copied only structured logistics inputs."
        ),
        "source_opportunity": {
            "opportunity_id": opportunity_id,
            "title": source.get("title"),
            "url": source.get("url"),
            "source_city": source.get("source_city"),
            "final_decision": source.get("final_decision"),
            "opportunity_score": source.get("opportunity_score"),
        },
        "transport_input": estimate.to_dict(),
        "transport_snapshot": snapshot,
    }
