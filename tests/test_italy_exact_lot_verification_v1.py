from __future__ import annotations

from datetime import datetime, timezone

from opportunity_engine.discovery.italy_exact_lot_verification import (
    ItalyPublicPage,
    run_italy_exact_lot_verification,
)


NOW = datetime(2026, 8, 16, 13, 20, tzinfo=timezone.utc)


def _lead(url: str, *, lead_id: str = "lead-1", rank: int = 1) -> dict:
    return {
        "lead_id": lead_id,
        "lead_kind": "INVENTORY_OR_LIQUIDATION_SALE_LEAD",
        "title": "Aurora Moda S.r.l. - asta lotto abbigliamento",
        "source_url": url,
        "provider": "Brave Search",
        "search_rank": rank,
        "follow_up_relevance_score": 95,
        "verification_status": "UNVERIFIED_PUBLIC_WEB_SEARCH_HIT",
        "source_page_verification_required": True,
        "commercial_facts_confirmed": False,
        "promotion_to_opportunity_allowed": False,
    }


def _report(*leads: dict, target: str = "Aurora Moda S.r.l") -> dict:
    return {
        "cases": [
            {
                "case_id": "persistent-entity-case:it:aurora-moda",
                "case_title": target,
                "country": "IT",
                "target_label": target,
                "follow_up_stage": "LOTTI_CONCRETI",
                "leads": list(leads),
            }
        ]
    }


def _page(url: str, html: str) -> ItalyPublicPage:
    return ItalyPublicPage(
        requested_url=url,
        final_url=url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        response_bytes=len(html.encode("utf-8")),
        sha256="fixture-sha",
        html=html,
    )


def test_original_page_can_verify_active_exact_clothing_lot_and_extract_facts() -> None:
    url = "https://aste.example.it/aurora-lotto-800-capi"
    html = """
    <html>
      <head><title>Aurora Moda S.r.l. - Lotto abbigliamento</title></head>
      <body>
        <h1>Aurora Moda S.r.l.</h1>
        <p>Lotto di 800 capi di abbigliamento in vendita.</p>
        <p>Prezzo base: € 3.500,00 EUR</p>
        <p>Scadenza: 20/08/2026 alle 15:00</p>
        <p>Luogo: Milano</p>
      </body>
    </html>
    """
    calls: list[str] = []

    def fetcher(requested: str) -> ItalyPublicPage:
        calls.append(requested)
        return _page(requested, html)

    report = run_italy_exact_lot_verification(
        _report(_lead(url)),
        observed_at=NOW,
        page_fetcher=fetcher,
    )

    assert calls == [url]
    assert report["status"] == "SUCCESS"
    assert report["verified_active_exact_lot_lead_count"] == 1
    assert report["verified_with_quantity_count"] == 1
    assert report["verified_with_price_count"] == 1
    assert report["verified_with_deadline_count"] == 1
    assert report["verified_with_location_count"] == 1

    row = report["verifications"][0]
    assert row["source_page_verified"] is True
    assert row["entity_link_verified"] is True
    assert row["exact_lot_evidence"] is True
    assert row["sale_status"] == "ACTIVE"
    assert row["source_page_verification_status"] == "VERIFIED_ACTIVE_EXACT_LOT_LEAD"
    assert row["commercial_lead_verified"] is True
    assert row["commercial_facts_confirmed"] is True
    assert row["quantity"] == 800
    assert row["source_price_eur"] == 3500.0
    assert row["currency"] == "EUR"
    assert row["sale_deadline_text"] == "20/08/2026 alle 15:00"
    assert row["location"] == "Milano"
    assert row["promotion_to_opportunity_allowed"] is False
    assert row["top5_eligible"] is False
    assert row["analysis_eligible"] is False
    assert row["automatic_contact"] is False
    assert row["automatic_bid"] is False
    assert row["automatic_reservation"] is False
    assert row["automatic_purchase"] is False
    assert row["automatic_payment"] is False


def test_generic_article_is_not_verified_as_exact_lot() -> None:
    url = "https://news.example.it/aurora-liquidazione"
    html = """
    <html><head><title>Aurora Moda S.r.l. in liquidazione</title></head>
    <body>
      <p>Aurora Moda S.r.l. opera nel settore abbigliamento.</p>
      <p>La società è in liquidazione giudiziale secondo fonti pubbliche.</p>
    </body></html>
    """

    report = run_italy_exact_lot_verification(
        _report(_lead(url)),
        observed_at=NOW,
        page_fetcher=lambda requested: _page(requested, html),
    )

    row = report["verifications"][0]
    assert row["source_page_verified"] is True
    assert row["entity_link_verified"] is True
    assert row["exact_lot_evidence"] is False
    assert row["commercial_lead_verified"] is False
    assert row["source_page_verification_status"] == "SOURCE_PAGE_VERIFIED_NOT_EXACT_CLOTHING_LOT"


def test_entity_mismatch_cannot_verify_other_company_lot() -> None:
    url = "https://aste.example.it/boreale-lotto"
    html = """
    <html><body>
      <h1>Boreale Tessile S.p.A.</h1>
      <p>Lotto di 500 capi di abbigliamento in vendita.</p>
      <p>Prezzo base: 2.000 EUR</p>
    </body></html>
    """

    report = run_italy_exact_lot_verification(
        _report(_lead(url)),
        observed_at=NOW,
        page_fetcher=lambda requested: _page(requested, html),
    )

    row = report["verifications"][0]
    assert row["exact_lot_evidence"] is True
    assert row["entity_link_verified"] is False
    assert row["commercial_lead_verified"] is False
    assert row["source_page_verification_status"] == "SOURCE_PAGE_VERIFIED_ENTITY_NOT_CONFIRMED"


def test_ended_exact_lot_is_retained_but_not_commercially_verified() -> None:
    url = "https://aste.example.it/aurora-lotto-concluso"
    html = """
    <html><body>
      <h1>Aurora Moda S.r.l. - lotto abbigliamento</h1>
      <p>Lotto di 800 capi di abbigliamento. Asta conclusa e lotto aggiudicato.</p>
      <p>Prezzo base: 3.500 EUR</p>
    </body></html>
    """

    report = run_italy_exact_lot_verification(
        _report(_lead(url)),
        observed_at=NOW,
        page_fetcher=lambda requested: _page(requested, html),
    )

    assert report["ended_lot_count"] == 1
    row = report["verifications"][0]
    assert row["entity_link_verified"] is True
    assert row["exact_lot_evidence"] is True
    assert row["sale_status"] == "ENDED"
    assert row["commercial_lead_verified"] is False
    assert row["source_page_verification_status"] == "SOURCE_PAGE_VERIFIED_ENDED_LOT"


def test_unknown_sale_status_never_becomes_verified_active_lead() -> None:
    url = "https://aste.example.it/aurora-lotto-informazioni"
    html = """
    <html><body>
      <h1>Aurora Moda S.r.l. - lotto abbigliamento</h1>
      <p>Informazioni relative al lotto di 800 capi e alla vendita giudiziaria.</p>
    </body></html>
    """

    report = run_italy_exact_lot_verification(
        _report(_lead(url)),
        observed_at=NOW,
        page_fetcher=lambda requested: _page(requested, html),
    )

    row = report["verifications"][0]
    assert row["exact_lot_evidence"] is True
    assert row["sale_status"] == "UNKNOWN"
    assert row["commercial_lead_verified"] is False
    assert row["source_page_verification_status"] == "SOURCE_PAGE_VERIFIED_SALE_STATUS_UNCONFIRMED"


def test_non_public_url_is_never_fetched() -> None:
    calls: list[str] = []

    def forbidden(url: str) -> ItalyPublicPage:
        calls.append(url)
        raise AssertionError("non-public URL must not be fetched")

    report = run_italy_exact_lot_verification(
        _report(_lead("https://127.0.0.1/internal-lot")),
        observed_at=NOW,
        page_fetcher=forbidden,
    )

    assert calls == []
    assert report["status"] == "VALID_ZERO_NO_FETCHABLE_PUBLIC_URLS"
    row = report["verifications"][0]
    assert row["source_page_verification_status"] == "UNSUPPORTED_OR_NON_PUBLIC_HTTPS_URL"
    assert row["commercial_lead_verified"] is False


def test_duplicate_urls_are_fetched_once_and_page_budget_is_enforced() -> None:
    first = "https://aste.example.it/aurora-lotto-1"
    second = "https://aste.example.it/aurora-lotto-2"
    calls: list[str] = []
    html = """
    <html><body>
      <h1>Aurora Moda S.r.l.</h1>
      <p>Lotto di 20 capi di abbigliamento in vendita.</p>
    </body></html>
    """

    def fetcher(url: str) -> ItalyPublicPage:
        calls.append(url)
        return _page(url, html)

    report = run_italy_exact_lot_verification(
        _report(
            _lead(first, lead_id="one", rank=1),
            _lead(first + "?utm_source=test", lead_id="duplicate", rank=2),
            _lead(second, lead_id="two", rank=3),
        ),
        observed_at=NOW,
        max_verification_pages=1,
        page_fetcher=fetcher,
    )

    assert calls == [first]
    assert report["deduplicated_lead_count"] == 2
    assert report["verification_request_count"] == 1
    assert report["budget_skipped_count"] == 1
    assert any(
        row["source_page_verification_status"] == "SKIPPED_BOUNDED_VERIFICATION_BUDGET"
        for row in report["verifications"]
    )


def test_valid_zero_when_follow_up_has_no_italy_leads() -> None:
    report = run_italy_exact_lot_verification(
        {"cases": []},
        observed_at=NOW,
        page_fetcher=lambda requested: (_ for _ in ()).throw(AssertionError(requested)),
    )

    assert report["status"] == "VALID_ZERO_NO_ITALY_FOLLOW_UP_LEADS"
    assert report["verification_request_count"] == 0
    assert report["verified_active_exact_lot_lead_count"] == 0
    assert report["promotion_to_opportunity_allowed"] is False
