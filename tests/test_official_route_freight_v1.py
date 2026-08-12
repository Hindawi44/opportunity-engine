from __future__ import annotations

from opportunity_engine.discovery.central_intelligence_orchestrator_cli_hook import (
    render_daily_central_report,
)
from opportunity_engine.logistics.official_route_freight import (
    BRING_SHIPPING_GUIDE_URL,
    GOOGLE_ROUTES_URL,
    build_official_route_freight_intelligence,
)


def _central() -> dict:
    return {
        "status": "SUCCESS",
        "market_visibility": ["NO", "SE", "DE", "IT"],
        "today_snapshot": {
            "actionable_now_count": 1,
            "market_watch_count": 0,
            "fabric_candidate_count": 0,
            "market_decision_quality": "BENCHMARK_APPLIED",
        },
        "top_actionable_opportunity": {
            "case_id": "case:de-stock",
            "headline": "German clothing stock",
            "case_type": "B2B_INVENTORY",
            "source_urls": ["https://example.test/stock"],
            "market_benchmark": {
                "benchmark_classification": "BELOW_MARKET_REQUIRES_VERIFICATION",
                "comparable_count": 5,
            },
        },
        "top_market_signal": None,
        "top_fabric_supplier": None,
        "primary_human_action": {
            "action_type": "VERIFY_LANDED_COST_FOR_BELOW_MARKET_OPPORTUNITY",
            "target_id": "case:de-stock",
            "target": "German clothing stock",
        },
        "automatic_purchase": False,
    }


def _reports(details: dict, *, location: str = "Berlin") -> tuple[dict, dict, dict]:
    item = {
        "intelligence_id": "item:de-stock",
        "record_kind": "B2B_STOCK_OFFER",
        "source_name": "Example",
        "source_country": "DE",
        "source_url": "https://example.test/stock",
        "title": "German clothing stock",
        "location": location,
        "details": details,
    }
    items = {"items": [item]}
    cases = {"cases": [{"case_id": "case:de-stock", "item_ids": ["item:de-stock"]}]}
    comparables = {
        "target_benchmarks": [
            {
                "case_id": "case:de-stock",
                "intelligence_id": "item:de-stock",
                "benchmark_classification": "BELOW_MARKET_REQUIRES_VERIFICATION",
            }
        ]
    }
    return items, cases, comparables


def _buyer(postal_code: str | None = None) -> dict:
    return {
        "profile_id": "TEST_NAMSOS",
        "location": {
            "country_code": "NO",
            "city": "Namsos",
            "postal_code": postal_code,
            "coordinates": None,
        },
        "settlement_currency": "NOK",
    }


def test_google_route_uses_selected_case_and_never_creates_a_freight_price() -> None:
    items, cases, comparables = _reports({})
    calls: list[tuple[str, dict, dict]] = []

    def route_post(url: str, headers: dict, payload: dict) -> dict:
        calls.append((url, headers, payload))
        return {"routes": [{"distanceMeters": 1812500, "duration": "84500s"}]}

    def bring_post(url: str, headers: dict, payload: dict) -> dict:
        raise AssertionError("Bring must not be called without shipment inputs")

    report, brief = build_official_route_freight_intelligence(
        central_brief=_central(),
        items_report=items,
        cases_report=cases,
        comparables=comparables,
        buyer_profile=_buyer(),
        environment={"GOOGLE_MAPS_API_KEY": "google-test-key"},
        route_post=route_post,
        bring_post=bring_post,
    )

    assert len(calls) == 1
    assert calls[0][0] == GOOGLE_ROUTES_URL
    assert calls[0][2]["origin"]["address"] == "Berlin, Germany"
    assert calls[0][2]["destination"]["address"] == "Namsos, Norway"
    assert report["route"]["status"] == "OFFICIAL_ROUTE_AVAILABLE"
    assert report["route"]["distance_km"] == 1812.5
    assert report["route"]["route_precision"] == "CITY_LEVEL"
    assert report["route"]["route_is_freight_price"] is False
    assert report["freight_quote"]["status"] == "SHIPMENT_INPUT_REQUIRED"
    assert "shipment.weight_kg" in report["freight_quote"]["missing_inputs"]
    assert "destination.postal_code" in report["freight_quote"]["missing_inputs"]
    assert brief["primary_human_action"]["action_type"] == "PROVIDE_SHIPMENT_INPUTS_FOR_OFFICIAL_QUOTE"
    assert brief["automatic_purchase"] is False


def test_bring_is_called_once_only_when_structured_quote_inputs_are_complete() -> None:
    items, cases, comparables = _reports(
        {"postal_code": "10115", "weight_kg": 420, "pallet_count": 2}
    )
    route_calls = 0
    bring_calls: list[tuple[str, dict, dict]] = []

    def route_post(url: str, headers: dict, payload: dict) -> dict:
        nonlocal route_calls
        route_calls += 1
        return {"routes": [{"distanceMeters": 1900000, "duration": "90000s"}]}

    def bring_post(url: str, headers: dict, payload: dict) -> dict:
        bring_calls.append((url, headers, payload))
        return {
            "uniqueId": "bring-quote-123",
            "consignments": [
                {
                    "products": [
                        {
                            "id": "4000",
                            "productionCode": "4000",
                            "price": {
                                "listPrice": {
                                    "priceWithoutAdditionalServices": {
                                        "amountWithoutVAT": "4800.00",
                                        "vat": "1200.00",
                                        "amountWithVAT": "6000.00",
                                    },
                                    "currencyCode": "NOK",
                                }
                            },
                        }
                    ]
                }
            ],
        }

    report, brief = build_official_route_freight_intelligence(
        central_brief=_central(),
        items_report=items,
        cases_report=cases,
        comparables=comparables,
        buyer_profile=_buyer("7800"),
        environment={
            "GOOGLE_MAPS_API_KEY": "google-test-key",
            "MYBRING_API_UID": "test@example.test",
            "MYBRING_API_KEY": "bring-test-key",
            "MYBRING_CLIENT_URL": "https://example.test",
        },
        route_post=route_post,
        bring_post=bring_post,
    )

    assert route_calls == 1
    assert len(bring_calls) == 1
    url, headers, payload = bring_calls[0]
    assert url == BRING_SHIPPING_GUIDE_URL
    assert headers["X-Mybring-API-Uid"] == "test@example.test"
    consignment = payload["consignments"][0]
    assert consignment["products"] == [{"id": "4000"}]
    assert consignment["fromCountryCode"] == "DE"
    assert consignment["fromPostalCode"] == "10115"
    assert consignment["toCountryCode"] == "NO"
    assert consignment["toPostalCode"] == "7800"
    assert consignment["packages"][0]["grossWeight"] == 420
    assert consignment["packages"][0]["numberOfPallets"] == 2

    freight = report["freight_quote"]
    assert freight["status"] == "OFFICIAL_QUOTE_AVAILABLE"
    assert freight["quote"]["amount_with_vat"] == 6000.0
    assert freight["quote"]["currency"] == "NOK"
    assert freight["quote"]["price_type"] == "LISTPRICE"
    assert freight["usable_for_nok_landed_cost"] is True
    assert brief["primary_human_action"]["action_type"] == "CALCULATE_FULL_LANDED_COST_WITH_OFFICIAL_FREIGHT"


def test_missing_credentials_never_become_an_estimated_quote() -> None:
    items, cases, comparables = _reports(
        {"postal_code": "10115", "weight_kg": 420, "pallet_count": 2}
    )

    def route_post(url: str, headers: dict, payload: dict) -> dict:
        return {"routes": [{"distanceMeters": 1900000, "duration": "90000s"}]}

    def bring_post(url: str, headers: dict, payload: dict) -> dict:
        raise AssertionError("Bring must not be called without credentials")

    report, _ = build_official_route_freight_intelligence(
        central_brief=_central(),
        items_report=items,
        cases_report=cases,
        comparables=comparables,
        buyer_profile=_buyer("7800"),
        environment={"GOOGLE_MAPS_API_KEY": "google-test-key"},
        route_post=route_post,
        bring_post=bring_post,
    )

    freight = report["freight_quote"]
    assert freight["status"] == "BLOCKED_CONFIGURATION"
    assert freight["request_count"] == 0
    assert report["price_estimation_fallback_allowed"] is False
    assert "quote" not in freight


def test_same_daily_report_shows_route_quote_and_missing_input_status() -> None:
    items, cases, comparables = _reports({})

    def route_post(url: str, headers: dict, payload: dict) -> dict:
        return {"routes": [{"distanceMeters": 1812500, "duration": "84500s"}]}

    def bring_post(url: str, headers: dict, payload: dict) -> dict:
        raise AssertionError("Bring must not be called")

    _, brief = build_official_route_freight_intelligence(
        central_brief=_central(),
        items_report=items,
        cases_report=cases,
        comparables=comparables,
        buyer_profile=_buyer(),
        environment={"GOOGLE_MAPS_API_KEY": "google-test-key"},
        route_post=route_post,
        bring_post=bring_post,
    )
    text = render_daily_central_report(brief)

    assert "العنوان: German clothing stock" in text
    assert "الرابط: https://example.test/stock" in text
    assert "الطريق: 1812.5 km | CITY_LEVEL | OFFICIAL_ROUTE_AVAILABLE" in text
    assert "الشحن الرسمي: BRING_SHIPPING_GUIDE: SHIPMENT_INPUT_REQUIRED" in text
    assert "بيانات الشحن الناقصة:" in text
    assert "automatic_purchase: false" in text
