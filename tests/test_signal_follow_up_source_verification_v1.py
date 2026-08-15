from __future__ import annotations

from datetime import datetime, timezone

from opportunity_engine.discovery.germany_venta import VentaPublicPage
from opportunity_engine.discovery.signal_follow_up_source_verification import (
    run_signal_follow_up_source_verification,
)

NOW = datetime(2026, 8, 15, 16, 30, tzinfo=timezone.utc)


def _lead(url: str, *, lead_id: str, title: str, rank: int = 1) -> dict:
    return {
        "lead_id": lead_id,
        "lead_kind": "INVENTORY_OR_LIQUIDATION_SALE_LEAD",
        "title": title,
        "source_url": url,
        "provider": "Brave Search",
        "search_rank": rank,
        "follow_up_relevance_score": 90,
        "verification_status": "UNVERIFIED_PUBLIC_WEB_SEARCH_HIT",
        "source_page_verification_required": True,
        "commercial_facts_confirmed": False,
        "promotion_to_opportunity_allowed": False,
    }


def _report(*leads: dict, target: str = "Adenauer & Co") -> dict:
    return {
        "cases": [
            {
                "case_id": "persistent-entity-case:adenauer",
                "case_title": target,
                "country": "DE",
                "target_label": target,
                "follow_up_stage": "WARENBESTAND",
                "leads": list(leads),
            }
        ]
    }


def test_exact_venta_item_routes_to_existing_verifier_and_surfaces_explicit_facts() -> None:
    url = "https://auction.venta24.de/item/id/100_7_Warenbestand_Adenauer_9001.html"
    html = """
    <html><body>
      <h1>Adenauer &amp; Co Bekleidung Warenbestand</h1>
      <div>Standort | 50667 Köln Objekt 9001</div>
      <div>Gewicht: 240 kg</div>
      <div>Abmessungen: 120 x 80 x 150 cm</div>
      <div>Paletten: 2</div>
      <div>Startpreis: 3500 EUR</div>
      <div>Aktuelles Gebot: 4200 EUR</div>
      <div>Aufgeld: 18 %</div>
      <div>MwSt: 19 %</div>
    </body></html>
    """

    def venta_fetcher(requested: str) -> VentaPublicPage:
        assert requested == url
        return VentaPublicPage(
            requested_url=requested,
            final_url=requested,
            status_code=200,
            content_type="text/html",
            response_bytes=len(html.encode()),
            sha256="venta-sha",
            html=html,
        )

    report = run_signal_follow_up_source_verification(
        _report(_lead(url, lead_id="venta-1", title="Adenauer Warenbestand")),
        observed_at=NOW,
        venta_fetcher=venta_fetcher,
    )

    assert report["status"] == "SUCCESS"
    assert report["verification_request_count"] == 1
    assert report["source_page_verified_count"] == 1
    assert report["verified_with_price_count"] == 1
    assert report["verified_with_weight_count"] == 1
    row = report["verifications"][0]
    assert row["source_kind"] == "VENTA_EXACT_ITEM"
    assert row["source_page_verified"] is True
    assert row["entity_link_verified"] is True
    assert row["source_start_or_minimum_price"] == 3500.0
    assert row["source_displayed_bid"] == 4200.0
    assert row["currency"] == "EUR"
    assert row["weight_kg"] == 240.0
    assert row["pallet_count"] == 2
    assert row["buyer_premium_percent"] == 18.0
    assert row["vat_percent"] == 19.0
    assert row["promotion_to_opportunity_allowed"] is False
    assert row["automatic_contact"] is False
    assert row["automatic_bid"] is False
    assert row["automatic_purchase"] is False
    assert row["automatic_payment"] is False


def test_exact_auksjonen_item_routes_and_extracts_quantity_weight_and_shipping() -> None:
    url = "https://ny.auksjonen.no/auksjon/torget/Stores_For_You_AB_arbeidsjakker/619341"
    html = """
    <html><body>
      <h1>Stores For You AB - 24 stk arbeidsjakker</h1>
      <div>Antall: 24</div>
      <div>Tilstand: Ubrukt</div>
      <div>Hentested: 7800 Namsos, Trøndelag</div>
      <div>Vekt: 84 kg</div>
      <div>Dimensjoner: 120 x 80 x 95 cm</div>
      <div>Antall paller: 1</div>
      <div>Kjøpersalær: 20 %</div>
      <div>MVA: 25 %</div>
    </body></html>
    """

    def auksjonen_fetcher(requested: str) -> tuple[str, str, int, str]:
        assert requested == url
        return html, requested, len(html.encode()), "auksjonen-sha"

    report = run_signal_follow_up_source_verification(
        _report(
            _lead(url, lead_id="auksjonen-1", title="Stores For You AB auksjon"),
            target="Stores For You AB",
        ),
        observed_at=NOW,
        auksjonen_fetcher=auksjonen_fetcher,
    )

    row = report["verifications"][0]
    assert row["source_kind"] == "AUKSJONEN_EXACT_ITEM"
    assert row["source_page_verified"] is True
    assert row["entity_link_verified"] is True
    assert row["quantity"] == 24
    assert row["weight_kg"] == 84.0
    assert row["pallet_count"] == 1
    assert row["source_postal_code"] == "7800"
    assert row["source_city"] == "Namsos"
    assert row["buyer_premium_percent"] == 20.0
    assert row["vat_percent"] == 25.0
    assert row["commercial_facts_confirmed"] is True


def test_generic_or_catalog_url_is_never_fetched_or_guessed() -> None:
    calls: list[str] = []

    def forbidden_fetch(url: str):
        calls.append(url)
        raise AssertionError("unsupported URL must not be fetched")

    report = run_signal_follow_up_source_verification(
        _report(
            _lead(
                "https://example.com/adenauer-liquidation",
                lead_id="generic-1",
                title="Adenauer liquidation",
            ),
            _lead(
                "https://auction.venta24.de/browse/search/1/block/example_123.html",
                lead_id="catalog-1",
                title="Adenauer catalog",
                rank=2,
            ),
        ),
        observed_at=NOW,
        venta_fetcher=forbidden_fetch,
        auksjonen_fetcher=forbidden_fetch,
    )

    assert calls == []
    assert report["status"] == "VALID_ZERO_NO_SUPPORTED_EXACT_ITEM_URLS"
    assert report["verification_request_count"] == 0
    assert report["unsupported_or_non_exact_count"] == 2
    assert all(
        row["source_page_verification_status"] == "UNSUPPORTED_SOURCE_OR_NON_EXACT_ITEM_URL"
        for row in report["verifications"]
    )
    assert report["unsupported_urls_are_never_guessed"] is True


def test_source_failure_is_recorded_without_promotion_or_guessed_facts() -> None:
    url = "https://auction.venta24.de/item/id/100_7_Adenauer_9001.html"

    def failing_fetcher(requested: str) -> VentaPublicPage:
        raise RuntimeError("captcha detected; no bypass attempted")

    report = run_signal_follow_up_source_verification(
        _report(_lead(url, lead_id="venta-fail", title="Adenauer Warenbestand")),
        observed_at=NOW,
        venta_fetcher=failing_fetcher,
    )

    assert report["status"] == "FAILED"
    assert report["source_page_failed_count"] == 1
    row = report["verifications"][0]
    assert row["source_page_verified"] is False
    assert row["source_page_verification_status"] == "SOURCE_PAGE_VERIFICATION_FAILED"
    assert row["commercial_facts_confirmed"] is False
    assert row["promotion_to_opportunity_allowed"] is False
    assert "no bypass" in row["error"]


def test_duplicate_urls_are_verified_once_and_page_budget_is_enforced() -> None:
    first = "https://auction.venta24.de/item/id/100_7_Adenauer_9001.html"
    second = "https://auction.venta24.de/item/id/101_8_Adenauer_9002.html"
    calls: list[str] = []

    def venta_fetcher(requested: str) -> VentaPublicPage:
        calls.append(requested)
        html = "<html><body><h1>Adenauer &amp; Co Bekleidung</h1><div>Gewicht: 20 kg</div></body></html>"
        return VentaPublicPage(
            requested_url=requested,
            final_url=requested,
            status_code=200,
            content_type="text/html",
            response_bytes=len(html.encode()),
            sha256="sha",
            html=html,
        )

    report = run_signal_follow_up_source_verification(
        _report(
            _lead(first, lead_id="one", title="Adenauer Warenbestand", rank=1),
            _lead(first + "?utm_source=test", lead_id="duplicate", title="Adenauer Warenbestand", rank=2),
            _lead(second, lead_id="two", title="Adenauer Auktion", rank=3),
        ),
        observed_at=NOW,
        max_verification_pages=1,
        venta_fetcher=venta_fetcher,
    )

    assert calls == [first]
    assert report["deduplicated_lead_count"] == 2
    assert report["verification_request_count"] == 1
    assert report["source_page_verified_count"] == 1
    assert report["budget_skipped_count"] == 1
    assert any(
        row["source_page_verification_status"] == "SKIPPED_BOUNDED_VERIFICATION_BUDGET"
        for row in report["verifications"]
    )
