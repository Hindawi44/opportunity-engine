"""Official route and freight intelligence for the already-selected central case.

This module never selects an opportunity, estimates a freight price, contacts a
seller/carrier, books transport, or performs a commercial action.  It enriches
only the top commercial case already chosen by Central Intelligence:

* Google Routes may provide an official road distance/duration;
* Bring Shipping Guide may provide a source-backed price when the structured
  postal and shipment inputs required by the carrier are available.

Missing inputs and missing credentials stay explicit.  No fallback price is
invented.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SCHEMA_VERSION = "official-route-freight-intelligence-1.0"
OUTPUT_FILENAME = "official-route-freight-quote.json"
GOOGLE_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
BRING_SHIPPING_GUIDE_URL = "https://api.bring.com/shippingguide/api/v2/products"
BRING_PRODUCT_ID = "4000"
DECISION_OWNER = "HUMAN_OPERATOR"

_COUNTRY_NAMES = {
    "NO": "Norway",
    "SE": "Sweden",
    "DE": "Germany",
    "IT": "Italy",
    "DK": "Denmark",
    "FI": "Finland",
    "NL": "Netherlands",
    "BE": "Belgium",
    "GB": "United Kingdom",
    "PL": "Poland",
    "FR": "France",
    "ES": "Spain",
    "PT": "Portugal",
}
_COMMERCIAL_KINDS = {"CANONICAL_OPPORTUNITY", "B2B_STOCK_OFFER", "AUCTION_LOT"}

JsonPost = Callable[[str, Mapping[str, str], Mapping[str, Any]], Mapping[str, Any]]


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if float(value) > 0 else None
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _integer(value: object) -> int | None:
    number = _number(value)
    if number is None or not float(number).is_integer():
        return None
    return int(number)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _default_json_post(
    url: str, headers: Mapping[str, str], payload: Mapping[str, Any]
) -> Mapping[str, Any]:
    data = json.dumps(dict(payload), ensure_ascii=False).encode("utf-8")
    request = Request(url, data=data, headers=dict(headers), method="POST")
    try:
        with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed official HTTPS endpoints
            raw = response.read(2_000_000)
    except HTTPError as exc:
        body = exc.read(20_000).decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body[:1000]}") from exc
    except URLError as exc:
        raise RuntimeError(f"network error: {exc.reason}") from exc
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("official API returned invalid JSON") from exc
    if not isinstance(decoded, Mapping):
        raise RuntimeError("official API returned a non-object JSON payload")
    return decoded


def _nested_value(details: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = details.get(key)
        if value not in (None, "", [], {}):
            return value
    metadata = details.get("metadata")
    if isinstance(metadata, Mapping):
        for key in keys:
            value = metadata.get(key)
            if value not in (None, "", [], {}):
                return value
    return None


def _find_case(cases_report: Mapping[str, Any], case_id: str) -> dict[str, Any] | None:
    for case in _rows(cases_report.get("cases")):
        if _compact(case.get("case_id")) == case_id:
            return case
    return None


def _selected_intelligence_id(
    *,
    case_id: str,
    comparables: Mapping[str, Any],
    cases_report: Mapping[str, Any],
) -> str | None:
    for benchmark in _rows(comparables.get("target_benchmarks")):
        if _compact(benchmark.get("case_id")) == case_id:
            value = _compact(benchmark.get("intelligence_id"))
            if value:
                return value
    case = _find_case(cases_report, case_id)
    if not case:
        return None
    for value in case.get("item_ids") or []:
        item_id = _compact(value)
        if item_id:
            return item_id
    return None


def _resolve_selected_item(
    *,
    central_brief: Mapping[str, Any],
    items_report: Mapping[str, Any],
    cases_report: Mapping[str, Any],
    comparables: Mapping[str, Any],
) -> dict[str, Any] | None:
    opportunity = central_brief.get("top_actionable_opportunity")
    if not isinstance(opportunity, Mapping):
        return None
    case_id = _compact(opportunity.get("case_id"))
    if not case_id:
        return None
    items = _rows(items_report.get("items"))
    by_id = {_compact(item.get("intelligence_id")): item for item in items}
    selected_id = _selected_intelligence_id(
        case_id=case_id, comparables=comparables, cases_report=cases_report
    )
    selected = by_id.get(selected_id or "")
    if selected is not None:
        return selected

    source_urls = {
        _compact(value) for value in (opportunity.get("source_urls") or []) if _compact(value)
    }
    candidates: list[dict[str, Any]] = []
    case = _find_case(cases_report, case_id)
    if case:
        for value in case.get("item_ids") or []:
            item = by_id.get(_compact(value))
            if item and _compact(item.get("record_kind")).upper() in _COMMERCIAL_KINDS:
                candidates.append(item)
    if source_urls:
        for item in candidates:
            if _compact(item.get("source_url")) in source_urls:
                return item
    return candidates[0] if candidates else None


def _country_code(item: Mapping[str, Any]) -> str | None:
    code = _compact(item.get("source_country")).upper()
    return code if re.fullmatch(r"[A-Z]{2}", code) else None


def _postal_from_details(details: Mapping[str, Any]) -> str | None:
    value = _nested_value(
        details,
        "source_postal_code",
        "postal_code",
        "postalCode",
        "zip_code",
        "zip",
    )
    text = _compact(value)
    return text or None


def _location_input(item: Mapping[str, Any]) -> dict[str, Any]:
    details = item.get("details") if isinstance(item.get("details"), Mapping) else {}
    country_code = _country_code(item)
    postal_code = _postal_from_details(details)
    city = _compact(
        _nested_value(details, "source_city", "city") or item.get("location")
    ) or None
    country_name = _COUNTRY_NAMES.get(country_code or "", country_code or "")
    if postal_code and city:
        address = f"{postal_code} {city}, {country_name}".strip(" ,")
        precision = "POSTAL_CODE_LEVEL"
    elif postal_code:
        address = f"{postal_code}, {country_name}".strip(" ,")
        precision = "POSTAL_CODE_LEVEL"
    elif city:
        address = f"{city}, {country_name}".strip(" ,")
        precision = "CITY_LEVEL"
    else:
        address = None
        precision = "INCOMPLETE"
    return {
        "country_code": country_code,
        "city": city,
        "postal_code": postal_code,
        "address": address,
        "precision": precision,
    }


def _destination_input(buyer: Mapping[str, Any]) -> dict[str, Any]:
    location = buyer.get("location") if isinstance(buyer.get("location"), Mapping) else {}
    country_code = _compact(location.get("country_code")).upper() or None
    city = _compact(location.get("city")) or None
    postal_code = _compact(location.get("postal_code")) or None
    country_name = _COUNTRY_NAMES.get(country_code or "", country_code or "")
    if postal_code and city:
        address = f"{postal_code} {city}, {country_name}".strip(" ,")
        precision = "POSTAL_CODE_LEVEL"
    elif city:
        address = f"{city}, {country_name}".strip(" ,")
        precision = "CITY_LEVEL"
    else:
        address = None
        precision = "INCOMPLETE"
    return {
        "country_code": country_code,
        "city": city,
        "postal_code": postal_code,
        "address": address,
        "precision": precision,
    }


def _route_result(
    origin: Mapping[str, Any],
    destination: Mapping[str, Any],
    environment: Mapping[str, str],
    json_post: JsonPost,
) -> dict[str, Any]:
    if not origin.get("address") or not destination.get("address"):
        return {
            "status": "ROUTE_INPUT_REQUIRED",
            "provider": "GOOGLE_ROUTES",
            "missing_inputs": [
                key
                for key, value in (
                    ("origin.location", origin.get("address")),
                    ("destination.location", destination.get("address")),
                )
                if not value
            ],
            "request_count": 0,
        }
    api_key = _compact(environment.get("GOOGLE_MAPS_API_KEY"))
    if not api_key:
        return {
            "status": "BLOCKED_CONFIGURATION",
            "provider": "GOOGLE_ROUTES",
            "block_reason": "GOOGLE_MAPS_API_KEY_MISSING",
            "request_count": 0,
        }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "routes.distanceMeters,routes.duration",
    }
    payload = {
        "origin": {"address": origin["address"]},
        "destination": {"address": destination["address"]},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_UNAWARE",
        "computeAlternativeRoutes": False,
        "languageCode": "en-US",
        "units": "METRIC",
    }
    try:
        response = json_post(GOOGLE_ROUTES_URL, headers, payload)
    except Exception as exc:  # API failures are reported, not allowed to break the daily bulletin
        return {
            "status": "BLOCKED_RETRIEVAL",
            "provider": "GOOGLE_ROUTES",
            "error": f"{type(exc).__name__}: {_compact(exc)[:500]}",
            "request_count": 1,
        }
    routes = response.get("routes") if isinstance(response.get("routes"), list) else []
    route = routes[0] if routes and isinstance(routes[0], Mapping) else {}
    distance = _number(route.get("distanceMeters"))
    duration_text = _compact(route.get("duration"))
    duration_seconds = None
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)s", duration_text)
    if match:
        duration_seconds = float(match.group(1))
    if distance is None:
        return {
            "status": "BLOCKED_RETRIEVAL",
            "provider": "GOOGLE_ROUTES",
            "error": "NO_ROUTE_RETURNED",
            "request_count": 1,
        }
    precision = (
        "POSTAL_CODE_LEVEL"
        if origin.get("postal_code") and destination.get("postal_code")
        else "CITY_LEVEL"
    )
    return {
        "status": "OFFICIAL_ROUTE_AVAILABLE",
        "provider": "GOOGLE_ROUTES",
        "distance_meters": int(round(distance)),
        "distance_km": round(distance / 1000.0, 1),
        "duration_seconds": int(round(duration_seconds)) if duration_seconds is not None else None,
        "route_precision": precision,
        "route_is_freight_price": False,
        "request_count": 1,
    }


def _shipment_input(item: Mapping[str, Any]) -> dict[str, Any]:
    details = item.get("details") if isinstance(item.get("details"), Mapping) else {}
    weight = _number(_nested_value(details, "weight_kg", "gross_weight_kg"))
    pallets = _integer(_nested_value(details, "pallet_count", "number_of_pallets", "numberOfPallets"))
    length = _number(_nested_value(details, "length_cm", "package_length_cm"))
    width = _number(_nested_value(details, "width_cm", "package_width_cm"))
    height = _number(_nested_value(details, "height_cm", "package_height_cm"))
    volume = _number(_nested_value(details, "bring_volume", "volume"))
    return {
        "weight_kg": weight,
        "pallet_count": pallets,
        "length_cm": length,
        "width_cm": width,
        "height_cm": height,
        "bring_volume": volume,
    }


def _bring_missing_inputs(
    origin: Mapping[str, Any],
    destination: Mapping[str, Any],
    shipment: Mapping[str, Any],
) -> list[str]:
    missing: list[str] = []
    for field, value in (
        ("origin.country_code", origin.get("country_code")),
        ("origin.postal_code", origin.get("postal_code")),
        ("destination.country_code", destination.get("country_code")),
        ("destination.postal_code", destination.get("postal_code")),
        ("shipment.weight_kg", shipment.get("weight_kg")),
    ):
        if value in (None, ""):
            missing.append(field)
    has_dimensions = all(shipment.get(key) is not None for key in ("length_cm", "width_cm", "height_cm"))
    if not (
        has_dimensions
        or shipment.get("pallet_count") is not None
        or shipment.get("bring_volume") is not None
    ):
        missing.append("shipment.one_of_dimensions_pallet_count_or_bring_volume")
    return missing


def _price_candidates(response: Mapping[str, Any]) -> list[dict[str, Any]]:
    consignments = response.get("consignments") if isinstance(response.get("consignments"), list) else []
    result: list[dict[str, Any]] = []
    for consignment in consignments:
        if not isinstance(consignment, Mapping):
            continue
        for product in _rows(consignment.get("products")):
            errors = _rows(product.get("errors"))
            if errors:
                continue
            price = product.get("price") if isinstance(product.get("price"), Mapping) else {}
            for price_type in ("netPrice", "listPrice"):
                block = price.get(price_type)
                if not isinstance(block, Mapping):
                    continue
                totals = block.get("priceWithAdditionalServices")
                if not isinstance(totals, Mapping):
                    totals = block.get("priceWithoutAdditionalServices")
                if not isinstance(totals, Mapping):
                    continue
                amount = _number(totals.get("amountWithVAT"))
                amount_without_vat = _number(totals.get("amountWithoutVAT"))
                currency = _compact(block.get("currencyCode")).upper()
                if amount is None and amount_without_vat is None:
                    continue
                result.append(
                    {
                        "product_id": product.get("id"),
                        "production_code": product.get("productionCode"),
                        "price_type": price_type.upper(),
                        "currency": currency or None,
                        "amount_with_vat": amount,
                        "amount_without_vat": amount_without_vat,
                        "source_ref": f"{BRING_SHIPPING_GUIDE_URL}#{response.get('uniqueId') or 'response'}",
                    }
                )
    return result


def _bring_result(
    origin: Mapping[str, Any],
    destination: Mapping[str, Any],
    shipment: Mapping[str, Any],
    environment: Mapping[str, str],
    json_post: JsonPost,
) -> dict[str, Any]:
    missing = _bring_missing_inputs(origin, destination, shipment)
    if missing:
        return {
            "status": "SHIPMENT_INPUT_REQUIRED",
            "provider": "BRING_SHIPPING_GUIDE",
            "product_id": BRING_PRODUCT_ID,
            "missing_inputs": missing,
            "request_count": 0,
            "price_is_estimated": False,
        }
    uid = _compact(environment.get("MYBRING_API_UID"))
    key = _compact(environment.get("MYBRING_API_KEY"))
    client_url = _compact(environment.get("MYBRING_CLIENT_URL"))
    if not uid or not key or not client_url:
        missing_credentials = [
            name
            for name, value in (
                ("MYBRING_API_UID", uid),
                ("MYBRING_API_KEY", key),
                ("MYBRING_CLIENT_URL", client_url),
            )
            if not value
        ]
        return {
            "status": "BLOCKED_CONFIGURATION",
            "provider": "BRING_SHIPPING_GUIDE",
            "product_id": BRING_PRODUCT_ID,
            "block_reason": "BRING_CREDENTIALS_MISSING",
            "missing_credentials": missing_credentials,
            "request_count": 0,
        }

    product: dict[str, Any] = {"id": BRING_PRODUCT_ID}
    customer_number = _compact(environment.get("MYBRING_CUSTOMER_NUMBER"))
    if customer_number:
        product["customerNumber"] = customer_number
        product["autoSelectCustomerNumber"] = False

    package: dict[str, Any] = {
        "id": "1",
        "grossWeight": shipment["weight_kg"],
        "nonStackable": False,
        "volumeSpecial": False,
    }
    if shipment.get("pallet_count") is not None:
        package["numberOfPallets"] = shipment["pallet_count"]
    if all(shipment.get(key) is not None for key in ("length_cm", "width_cm", "height_cm")):
        package.update(
            {
                "length": shipment["length_cm"],
                "width": shipment["width_cm"],
                "height": shipment["height_cm"],
            }
        )
    if shipment.get("bring_volume") is not None:
        package["volume"] = shipment["bring_volume"]

    now = datetime.now(timezone.utc)
    payload = {
        "language": "EN",
        "withPrice": True,
        "withExpectedDelivery": True,
        "withGuiInformation": True,
        "withEstimatedDeliveryTime": False,
        "withEnvironmentalData": False,
        "numberOfAlternativeDeliveryDates": 0,
        "edi": False,
        "postingAtPostoffice": False,
        "trace": False,
        "consignments": [
            {
                "id": "central-intelligence-1",
                "products": [product],
                "fromCountryCode": origin["country_code"],
                "toCountryCode": destination["country_code"],
                "fromPostalCode": origin["postal_code"],
                "toPostalCode": destination["postal_code"],
                "toCity": destination.get("city"),
                "shippingDate": {
                    "day": str(now.day),
                    "month": str(now.month),
                    "year": str(now.year),
                },
                "packages": [package],
                "additionalServices": [],
                "pickupPoints": [],
            }
        ],
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Mybring-API-Uid": uid,
        "X-Mybring-API-Key": key,
        "X-Bring-Client-URL": client_url,
    }
    try:
        response = json_post(BRING_SHIPPING_GUIDE_URL, headers, payload)
    except Exception as exc:
        return {
            "status": "BLOCKED_RETRIEVAL",
            "provider": "BRING_SHIPPING_GUIDE",
            "product_id": BRING_PRODUCT_ID,
            "error": f"{type(exc).__name__}: {_compact(exc)[:500]}",
            "request_count": 1,
        }
    prices = _price_candidates(response)
    if not prices:
        errors: list[dict[str, Any]] = []
        for consignment in _rows(response.get("consignments")):
            for product_row in _rows(consignment.get("products")):
                errors.extend(_rows(product_row.get("errors")))
        return {
            "status": "OFFICIAL_QUOTE_UNAVAILABLE",
            "provider": "BRING_SHIPPING_GUIDE",
            "product_id": BRING_PRODUCT_ID,
            "provider_errors": errors[:10],
            "request_count": 1,
            "source_ref": f"{BRING_SHIPPING_GUIDE_URL}#{response.get('uniqueId') or 'response'}",
        }
    prices.sort(key=lambda row: 0 if row.get("price_type") == "NETPRICE" else 1)
    selected = prices[0]
    currency = selected.get("currency")
    usable_for_landed_cost = currency == "NOK" and selected.get("amount_with_vat") is not None
    return {
        "status": "OFFICIAL_QUOTE_AVAILABLE",
        "provider": "BRING_SHIPPING_GUIDE",
        "product_id": BRING_PRODUCT_ID,
        "quote": selected,
        "all_official_prices": prices[:5],
        "customer_number_used": bool(customer_number),
        "usable_for_nok_landed_cost": usable_for_landed_cost,
        "fx_required": bool(currency and currency != "NOK"),
        "request_count": 1,
        "automatic_booking": False,
    }


def _safe_action(brief: dict[str, Any], freight: Mapping[str, Any]) -> None:
    opportunity = brief.get("top_actionable_opportunity")
    if not isinstance(opportunity, Mapping):
        return
    action = brief.get("primary_human_action")
    if not isinstance(action, dict):
        action = {}
        brief["primary_human_action"] = action
    status = _compact(freight.get("status")).upper()
    if status == "OFFICIAL_QUOTE_AVAILABLE" and freight.get("usable_for_nok_landed_cost") is True:
        action.update(
            {
                "action_type": "CALCULATE_FULL_LANDED_COST_WITH_OFFICIAL_FREIGHT",
                "recommended_next_action": "CALCULATE_DUTY_VAT_FEES_AND_FULL_LANDED_COST",
                "reason": "An official Bring freight quote is available for the selected opportunity; complete the remaining landed-cost components before a purchase decision.",
            }
        )
    elif status == "SHIPMENT_INPUT_REQUIRED":
        action.update(
            {
                "action_type": "PROVIDE_SHIPMENT_INPUTS_FOR_OFFICIAL_QUOTE",
                "recommended_next_action": "VERIFY_POSTAL_CODES_WEIGHT_AND_PACKAGE_OR_PALLET_MEASUREMENTS",
                "reason": "The selected opportunity needs structured shipment inputs before Bring can return an official freight price.",
                "shipping_missing_inputs": list(freight.get("missing_inputs") or []),
            }
        )
    elif status == "BLOCKED_CONFIGURATION":
        action.setdefault("shipping_note", "Official Bring quote is configured but API credentials are not available.")


def build_official_route_freight_intelligence(
    *,
    central_brief: Mapping[str, Any],
    items_report: Mapping[str, Any],
    cases_report: Mapping[str, Any],
    comparables: Mapping[str, Any],
    buyer_profile: Mapping[str, Any],
    environment: Mapping[str, str],
    route_post: JsonPost = _default_json_post,
    bring_post: JsonPost = _default_json_post,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Enrich one already-selected commercial case with route/freight evidence."""
    brief = deepcopy(dict(central_brief))
    opportunity = brief.get("top_actionable_opportunity")
    base = {
        "schema_version": SCHEMA_VERSION,
        "decision_owner": DECISION_OWNER,
        "selected_case_id": opportunity.get("case_id") if isinstance(opportunity, Mapping) else None,
        "automatic_contact": False,
        "automatic_booking": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
        "price_estimation_fallback_allowed": False,
        "max_google_route_requests": 1,
        "max_bring_quote_requests": 1,
    }
    if not isinstance(opportunity, Mapping):
        report = {
            **base,
            "status": "VALID_ZERO",
            "block_reason": "NO_SELECTED_COMMERCIAL_OPPORTUNITY",
            "route": None,
            "freight_quote": None,
        }
        return report, brief

    item = _resolve_selected_item(
        central_brief=brief,
        items_report=items_report,
        cases_report=cases_report,
        comparables=comparables,
    )
    if not item:
        report = {
            **base,
            "status": "BLOCKED_INPUT",
            "block_reason": "SELECTED_SOURCE_ITEM_NOT_RESOLVED",
            "route": None,
            "freight_quote": None,
        }
        return report, brief

    origin = _location_input(item)
    destination = _destination_input(buyer_profile)
    shipment = _shipment_input(item)
    route = _route_result(origin, destination, environment, route_post)
    freight = _bring_result(origin, destination, shipment, environment, bring_post)
    _safe_action(brief, freight)

    if isinstance(brief.get("top_actionable_opportunity"), dict):
        brief["top_actionable_opportunity"]["route_freight"] = {
            "route_status": route.get("status"),
            "distance_km": route.get("distance_km"),
            "route_precision": route.get("route_precision"),
            "freight_status": freight.get("status"),
            "freight_provider": freight.get("provider"),
            "official_quote": deepcopy(freight.get("quote")),
            "shipping_missing_inputs": list(freight.get("missing_inputs") or []),
        }
    snapshot = brief.get("today_snapshot")
    if not isinstance(snapshot, dict):
        snapshot = {}
        brief["today_snapshot"] = snapshot
    snapshot["official_route_status"] = route.get("status")
    snapshot["official_freight_status"] = freight.get("status")

    statuses = {route.get("status"), freight.get("status")}
    if "OFFICIAL_QUOTE_AVAILABLE" in statuses or "OFFICIAL_ROUTE_AVAILABLE" in statuses:
        status = "SUCCESS"
    elif statuses <= {"BLOCKED_CONFIGURATION", "SHIPMENT_INPUT_REQUIRED", "ROUTE_INPUT_REQUIRED"}:
        status = "REQUIRES_INPUT_OR_CONFIGURATION"
    else:
        status = "PARTIAL_SUCCESS"
    report = {
        **base,
        "status": status,
        "source_item": {
            "intelligence_id": item.get("intelligence_id"),
            "record_kind": item.get("record_kind"),
            "title": item.get("title"),
            "source_url": item.get("source_url"),
            "source_country": item.get("source_country"),
            "location": item.get("location"),
        },
        "origin": origin,
        "destination": destination,
        "shipment": shipment,
        "route": route,
        "freight_quote": freight,
    }
    return report, brief


def apply_official_route_freight(
    output_dir: str | Path,
    central_brief: Mapping[str, Any],
    *,
    environment: Mapping[str, str] | None = None,
    route_post: JsonPost = _default_json_post,
    bring_post: JsonPost = _default_json_post,
    buyer_path: str | Path = "config/buyers/mahmoud_namsos_v1.json",
) -> dict[str, Any]:
    """Read existing daily artifacts, enrich the same central brief, and persist it."""
    directory = Path(output_dir)
    env = environment if environment is not None else os.environ
    report, brief = build_official_route_freight_intelligence(
        central_brief=central_brief,
        items_report=_read_json(directory / "unified-intelligence-items.json"),
        cases_report=_read_json(directory / "unified-market-cases.json"),
        comparables=_read_json(directory / "market-comparables-benchmark.json"),
        buyer_profile=_read_json(Path(buyer_path)),
        environment=env,
        route_post=route_post,
        bring_post=bring_post,
    )
    _write_json(directory / OUTPUT_FILENAME, report)
    _write_json(directory / "central-intelligence-brief.json", brief)

    domain_path = directory / "domain-market-intelligence-brief.json"
    domain = _read_json(domain_path)
    if domain:
        central = domain.get("central_intelligence_orchestrator")
        if not isinstance(central, dict):
            central = {}
            domain["central_intelligence_orchestrator"] = central
        central["today_snapshot"] = deepcopy(brief.get("today_snapshot"))
        central["top_actionable_opportunity"] = deepcopy(brief.get("top_actionable_opportunity"))
        central["primary_human_action"] = deepcopy(brief.get("primary_human_action"))
        central["official_route_freight"] = {
            "status": report.get("status"),
            "route": deepcopy(report.get("route")),
            "freight_quote": deepcopy(report.get("freight_quote")),
            "output_file": OUTPUT_FILENAME,
        }
        _write_json(domain_path, domain)
    return brief
