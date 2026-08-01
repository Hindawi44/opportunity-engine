import pytest

from opportunity_engine.discovery.clothing_inventory_search import (
    ACTIVE,
    ITEM_LISTING,
    UNRESOLVED_SOURCE,
    PageVerification,
)
from opportunity_engine.discovery.sweden_psauction_playwright import (
    PSAuctionPlaywrightConfig,
    PSAuctionPlaywrightFallbackVerifier,
)


PS_ITEM = (
    "https://psauction.se/item/view/1560018/"
    "ca-100-st-laderbalten-strl-90-105"
)


def _blocked(url=PS_ITEM):
    return PageVerification(
        url=url,
        page_role=UNRESOLVED_SOURCE,
        opportunity_identity="url-id:1560018",
        identity_stable=True,
        verified=False,
        error="HTTP Error 403: Forbidden",
    )


def _verified(url=PS_ITEM):
    return PageVerification(
        url=url,
        title="Ca 100 st Läderbälten, Strl 90-105",
        text=(
            "Auktionen avslutas Tisdag, 2026-08-04. Nuvarande bud 800 SEK. "
            "Parti med 100 st bälten."
        ),
        listing_status=ACTIVE,
        page_role=ITEM_LISTING,
        opportunity_identity="url-id:1560018",
        identity_stable=True,
        clothing_inventory_evidence=True,
        sale_evidence=True,
        event_scenario="AUCTION",
        verified=True,
    )


def test_config_enforces_small_volume_and_delay():
    with pytest.raises(ValueError, match="max_pages"):
        PSAuctionPlaywrightConfig(max_pages=4)
    with pytest.raises(ValueError, match="delay_seconds"):
        PSAuctionPlaywrightConfig(delay_seconds=1.5)


def test_verified_primary_result_never_opens_browser():
    calls = []
    verifier = PSAuctionPlaywrightFallbackVerifier(
        lambda url: _verified(url),
        rendered_page_loader=lambda url: calls.append(url),
    )

    result = verifier(PS_ITEM)

    assert result.verified is True
    assert calls == []
    assert verifier.diagnostics()["attempted"] == 0


def test_403_on_specific_item_uses_rendered_page(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "opportunity_engine.discovery.sweden_psauction_playwright.verify_public_html",
        lambda url, html: _verified(url),
    )
    verifier = PSAuctionPlaywrightFallbackVerifier(
        lambda url: _blocked(url),
        rendered_page_loader=lambda url: (calls.append(url) or (url, "<html/>")),
    )

    result = verifier(PS_ITEM)
    diagnostics = verifier.diagnostics()

    assert result.verified is True
    assert result.listing_status == ACTIVE
    assert calls == [PS_ITEM]
    assert diagnostics["attempted"] == 1
    assert diagnostics["succeeded"] == 1
    assert diagnostics["failed"] == 0


def test_fallback_does_not_run_for_other_hosts():
    calls = []
    other = "https://example.com/item/view/1560018/test"
    verifier = PSAuctionPlaywrightFallbackVerifier(
        lambda url: _blocked(url),
        rendered_page_loader=lambda url: calls.append(url),
    )

    result = verifier(other)

    assert result.verified is False
    assert calls == []
    assert verifier.diagnostics()["attempted"] == 0


def test_fallback_budget_is_fail_closed(monkeypatch):
    monkeypatch.setattr(
        "opportunity_engine.discovery.sweden_psauction_playwright.verify_public_html",
        lambda url, html: _verified(url),
    )
    calls = []
    verifier = PSAuctionPlaywrightFallbackVerifier(
        lambda url: _blocked(url),
        config=PSAuctionPlaywrightConfig(max_pages=1),
        rendered_page_loader=lambda url: (calls.append(url) or (url, "<html/>")),
    )
    second = PS_ITEM.replace("1560018", "1560019")

    first_result = verifier(PS_ITEM)
    second_result = verifier(second)
    diagnostics = verifier.diagnostics()

    assert first_result.verified is True
    assert second_result.verified is False
    assert calls == [PS_ITEM]
    assert diagnostics["budget_exhausted"] == 1


def test_browser_error_preserves_primary_failure():
    def fail(_url):
        raise RuntimeError("chromium navigation failed")

    verifier = PSAuctionPlaywrightFallbackVerifier(
        lambda url: _blocked(url),
        rendered_page_loader=fail,
    )

    result = verifier(PS_ITEM)
    diagnostics = verifier.diagnostics()

    assert result.verified is False
    assert "Chromium fallback failed" in result.error
    assert diagnostics["attempted"] == 1
    assert diagnostics["failed"] == 1
    assert diagnostics["errors"][0]["error"] == "chromium navigation failed"
