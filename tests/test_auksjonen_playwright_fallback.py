import pytest

from opportunity_engine.discovery.auksjonen_playwright_fallback import (
    AuksjonenPlaywrightFallbackConfig,
    AuksjonenPlaywrightFallbackVerifier,
    is_specific_auksjonen_item_url,
)
from opportunity_engine.discovery.clothing_inventory_search import (
    ACTIVE,
    CATEGORY_INDEX,
    ITEM_LISTING,
    UNRESOLVED_SOURCE,
    PageVerification,
)


AUKSJONEN_ITEM = (
    "https://auksjonen.no/auksjon/torget/"
    "Wenaas_Arbeidstoy_vinterklaer_bukser_shorts/450595"
)


def _unresolved(url=AUKSJONEN_ITEM):
    return PageVerification(
        url=url,
        page_role=UNRESOLVED_SOURCE,
        opportunity_identity="url-id:450595",
        identity_stable=True,
        verified=False,
        error="insufficient public listing content",
    )


def _verified(url=AUKSJONEN_ITEM):
    return PageVerification(
        url=url,
        title="Wenaas arbeidstøy, nye klær",
        inventory_type="arbeidstøy",
        listing_status=ACTIVE,
        page_role=ITEM_LISTING,
        opportunity_identity="url-id:450595",
        identity_stable=True,
        clothing_inventory_evidence=True,
        sale_evidence=True,
        event_scenario="AUCTION",
        verified=True,
    )


def test_specific_auksjonen_item_shape_is_bounded():
    assert is_specific_auksjonen_item_url(AUKSJONEN_ITEM) is True
    assert is_specific_auksjonen_item_url(
        "https://auksjonen.no/auksjoner/varelager"
    ) is False
    assert is_specific_auksjonen_item_url(
        "https://auksjonen.no/auksjon/torget/no-stable-id"
    ) is False
    assert is_specific_auksjonen_item_url(
        "https://example.com/auksjon/torget/test/450595"
    ) is False


def test_config_enforces_small_volume_and_delay():
    with pytest.raises(ValueError, match="max_pages"):
        AuksjonenPlaywrightFallbackConfig(max_pages=4)
    with pytest.raises(ValueError, match="delay_seconds"):
        AuksjonenPlaywrightFallbackConfig(delay_seconds=1.5)


def test_verified_primary_result_never_opens_browser():
    calls = []
    verifier = AuksjonenPlaywrightFallbackVerifier(
        lambda url: _verified(url),
        rendered_page_loader=lambda url: calls.append(url),
    )

    result = verifier(AUKSJONEN_ITEM)

    assert result.verified is True
    assert calls == []
    assert verifier.diagnostics()["attempted"] == 0


def test_rendered_fallback_reuses_existing_html_verifier(monkeypatch):
    rendered_calls = []

    def rendered_loader(url):
        rendered_calls.append(url)
        return url, "<html><body>rendered item</body></html>"

    monkeypatch.setattr(
        "opportunity_engine.discovery.auksjonen_playwright_fallback.verify_public_html",
        lambda url, html: _verified(url),
    )
    verifier = AuksjonenPlaywrightFallbackVerifier(
        lambda url: _unresolved(url),
        rendered_page_loader=rendered_loader,
    )

    result = verifier(AUKSJONEN_ITEM)
    diagnostics = verifier.diagnostics()

    assert result.verified is True
    assert result.page_role == ITEM_LISTING
    assert rendered_calls == [AUKSJONEN_ITEM]
    assert diagnostics["attempted"] == 1
    assert diagnostics["succeeded"] == 1
    assert diagnostics["failed"] == 0
    assert diagnostics["used"] is True


def test_rendered_active_clothing_item_recovers_bounded_auction_evidence(monkeypatch):
    rendered = PageVerification(
        url=AUKSJONEN_ITEM,
        title="8 stk Blåkläder T-skjorter i størrelse XL",
        text="Antall: 8 stk T-skjorter. Modell 3325. Egnet til arbeid.",
        listing_status=ACTIVE,
        page_role=ITEM_LISTING,
        opportunity_identity="url-id:450595",
        identity_stable=True,
        clothing_inventory_evidence=False,
        sale_evidence=False,
        verified=True,
    )
    monkeypatch.setattr(
        "opportunity_engine.discovery.auksjonen_playwright_fallback.verify_public_html",
        lambda url, html: rendered,
    )
    verifier = AuksjonenPlaywrightFallbackVerifier(
        lambda url: _unresolved(url),
        rendered_page_loader=lambda url: (url, "<html/>"),
    )

    result = verifier(AUKSJONEN_ITEM)

    assert result.clothing_inventory_evidence is True
    assert result.sale_evidence is True
    assert result.event_scenario == "AUCTION"
    assert result.bounded_context == rendered.text


def test_rendered_non_clothing_item_is_not_enriched(monkeypatch):
    rendered = PageVerification(
        url=AUKSJONEN_ITEM,
        title="Parti med håndverktøy",
        text="Antall: 8 stk skiftenøkler.",
        listing_status=ACTIVE,
        page_role=ITEM_LISTING,
        opportunity_identity="url-id:450595",
        identity_stable=True,
        verified=True,
    )
    monkeypatch.setattr(
        "opportunity_engine.discovery.auksjonen_playwright_fallback.verify_public_html",
        lambda url, html: rendered,
    )
    verifier = AuksjonenPlaywrightFallbackVerifier(
        lambda url: _unresolved(url),
        rendered_page_loader=lambda url: (url, "<html/>"),
    )

    result = verifier(AUKSJONEN_ITEM)

    assert result.clothing_inventory_evidence is False
    assert result.sale_evidence is False
    assert result.event_scenario == "UNVERIFIED_EVENT"


def test_rendered_category_page_remains_rejected(monkeypatch):
    rendered = PageVerification(
        url=AUKSJONEN_ITEM,
        title="Arbeidshansker - 570 par - stort parti",
        text="Samtykke Detaljer. Denne nettsiden bruker informasjonskapsler.",
        listing_status=ACTIVE,
        page_role=CATEGORY_INDEX,
        opportunity_identity="url-id:450595",
        identity_stable=True,
        verified=True,
    )
    monkeypatch.setattr(
        "opportunity_engine.discovery.auksjonen_playwright_fallback.verify_public_html",
        lambda url, html: rendered,
    )
    verifier = AuksjonenPlaywrightFallbackVerifier(
        lambda url: _unresolved(url),
        rendered_page_loader=lambda url: (url, "<html/>"),
    )

    result = verifier(AUKSJONEN_ITEM)

    assert result.page_role == CATEGORY_INDEX
    assert result.clothing_inventory_evidence is False
    assert result.sale_evidence is False


def test_fallback_does_not_run_for_other_hosts():
    calls = []
    url = "https://stadssalg.no/items/52548"
    verifier = AuksjonenPlaywrightFallbackVerifier(
        lambda value: _unresolved(value),
        rendered_page_loader=lambda value: calls.append(value),
    )

    result = verifier(url)

    assert result.verified is False
    assert calls == []
    assert verifier.diagnostics()["attempted"] == 0


def test_fallback_budget_is_fail_closed(monkeypatch):
    monkeypatch.setattr(
        "opportunity_engine.discovery.auksjonen_playwright_fallback.verify_public_html",
        lambda url, html: _verified(url),
    )
    calls = []
    verifier = AuksjonenPlaywrightFallbackVerifier(
        lambda url: _unresolved(url),
        config=AuksjonenPlaywrightFallbackConfig(max_pages=1),
        rendered_page_loader=lambda url: (calls.append(url) or (url, "<html/>")),
    )
    second_url = AUKSJONEN_ITEM.replace("450595", "445743")

    first = verifier(AUKSJONEN_ITEM)
    second = verifier(second_url)
    diagnostics = verifier.diagnostics()

    assert first.verified is True
    assert second.verified is False
    assert calls == [AUKSJONEN_ITEM]
    assert diagnostics["attempted"] == 1
    assert diagnostics["budget_exhausted"] == 1


def test_browser_error_is_reported_without_weakening_primary_result():
    def fail(_url):
        raise RuntimeError("chromium navigation failed")

    verifier = AuksjonenPlaywrightFallbackVerifier(
        lambda url: _unresolved(url),
        rendered_page_loader=fail,
    )

    result = verifier(AUKSJONEN_ITEM)
    diagnostics = verifier.diagnostics()

    assert result.verified is False
    assert "Playwright fallback failed" in result.error
    assert diagnostics["attempted"] == 1
    assert diagnostics["failed"] == 1
    assert diagnostics["errors"][0]["error"] == "chromium navigation failed"
