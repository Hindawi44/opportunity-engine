from __future__ import annotations

from datetime import datetime, timezone

from opportunity_engine.discovery.clothing_inventory_search import (
    ACTIVE,
    CATEGORY_INDEX,
    ENDED,
    ITEM_LISTING,
    UNKNOWN,
    PageVerification,
)
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.sweden_clothing_inventory import (
    enrich_sweden_page_verification,
)
from opportunity_engine.discovery.sweden_psauction_playwright import (
    PSAuctionPlaywrightConfig,
    PSAuctionPlaywrightFallbackVerifier,
)


NOW = datetime(2026, 8, 16, 19, 43, tzinfo=timezone.utc)
ENDED_ITEM_URL = "https://psauction.se/item/view/826330/didrikssons-barnklader"
ACTIVE_FIXTURE_URL = "https://psauction.se/item/view/999999/arbetsklader-parti"
VAXJO_AUCTION_URL = (
    "https://psauction.se/auction/68986/"
    "vaxjo-inunder-ab-i-konkurs"
)


class _FixtureSearchProvider:
    name = "PS Auction targeted fixture"

    def __init__(self, hits: list[SearchHit]) -> None:
        self.hits = hits
        self.queries: list[str] = []

    def search(self, query: str, *, count: int = 10) -> tuple[SearchHit, ...]:
        self.queries.append(query)
        return tuple(self.hits[:count])


def _blocked_primary(url: str) -> PageVerification:
    return PageVerification(
        url=url,
        verified=False,
        error="HTTP 403 Forbidden",
    )


def _disabled_renderer(url: str) -> tuple[str, str]:
    raise RuntimeError(f"rendering deliberately disabled for targeted fixture: {url}")


def _verifier(hit: SearchHit) -> PSAuctionPlaywrightFallbackVerifier:
    return PSAuctionPlaywrightFallbackVerifier(
        _blocked_primary,
        config=PSAuctionPlaywrightConfig(
            max_pages=1,
            delay_seconds=2.0,
            navigation_timeout_seconds=1.0,
        ),
        rendered_page_loader=_disabled_renderer,
        indexed_search_provider=_FixtureSearchProvider([hit]),
        clock=lambda: NOW,
    )


def test_item_826330_resolves_ended_from_exact_official_status_markers() -> None:
    """Historical control: exact item 826330 must never re-enter the active lane."""
    verifier = _verifier(
        SearchHit(
            title="Didrikssons barnkläder",
            url=ENDED_ITEM_URL,
            description=(
                "Parti med kläder | Auktionen avslutad | Såld | "
                "Auktionen avslutades 2022-03-22 10:35"
            ),
            provider="fixture",
        )
    )

    result = verifier(ENDED_ITEM_URL)

    assert result.verified is True
    assert result.listing_status == ENDED
    assert result.page_role == ITEM_LISTING
    assert result.opportunity_identity == "url-id:826330"
    diagnostics = verifier.diagnostics()
    assert diagnostics["indexed_resolved_ended"] == 1
    assert diagnostics["indexed_resolved_active"] == 0


def test_active_fixture_resolves_active_only_from_future_exact_deadline() -> None:
    """Active control: exact item + clothing/bulk scope + future deadline => ACTIVE."""
    verifier = _verifier(
        SearchHit(
            title="Arbetskläder parti",
            url=ACTIVE_FIXTURE_URL,
            description=(
                "50 st arbetskläder i sortiment. "
                "Auktionen avslutas 2026-08-20 10:35. "
                "Nuvarande bud 250 SEK."
            ),
            provider="fixture",
        )
    )

    result = verifier(ACTIVE_FIXTURE_URL)

    assert result.verified is True
    assert result.listing_status == ACTIVE
    assert result.page_role == ITEM_LISTING
    assert result.opportunity_identity == "url-id:999999"
    diagnostics = verifier.diagnostics()
    assert diagnostics["indexed_resolved_active"] == 1
    assert diagnostics["indexed_resolved_ended"] == 0


def test_current_vaxjo_auction_route_resolves_active_from_exact_deadline() -> None:
    """Regression: current parent-auction route 68986 must reach verification."""
    verifier = _verifier(
        SearchHit(
            title="Växjö Inunder AB i konkurs",
            url=VAXJO_AUCTION_URL,
            description=(
                "Auktionen innehåller butiksinredning, möbler och kläder såsom "
                "underkläder och badkläder. 35 objekt. "
                "Auktionen slutar 2026-09-10 18:00."
            ),
            provider="fixture",
        )
    )

    result = verifier(VAXJO_AUCTION_URL)

    assert result.verified is True
    assert result.listing_status == ACTIVE
    assert result.page_role == ITEM_LISTING
    assert result.opportunity_identity == "url-id:68986"
    assert result.clothing_inventory_evidence is True
    assert result.event_scenario == "COMPANY_BANKRUPTCY"


def test_rendered_parent_auction_index_requires_exact_status_corroboration(
    monkeypatch,
) -> None:
    """A multi-object auction page must not pass as a verified exact lot."""
    indexed = _FixtureSearchProvider(
        [
            SearchHit(
                title="Växjö Inunder AB i konkurs",
                url=VAXJO_AUCTION_URL,
                description=(
                    "Kläder och butiksinredning. 35 objekt. "
                    "Auktionen slutar 2026-09-10 18:00."
                ),
                provider="fixture",
            )
        ]
    )
    category_result = PageVerification(
        url=VAXJO_AUCTION_URL,
        title="Växjö Inunder AB i konkurs",
        page_role=CATEGORY_INDEX,
        verified=True,
    )
    monkeypatch.setattr(
        "opportunity_engine.discovery.sweden_psauction_playwright.verify_public_html",
        lambda _url, _html: category_result,
    )
    verifier = PSAuctionPlaywrightFallbackVerifier(
        lambda _url: category_result,
        config=PSAuctionPlaywrightConfig(max_pages=1, delay_seconds=2.0),
        rendered_page_loader=lambda url: (url, "<html>rendered auction</html>"),
        indexed_search_provider=indexed,
        clock=lambda: NOW,
    )

    result = verifier(VAXJO_AUCTION_URL)

    assert result.verified is True
    assert result.page_role == ITEM_LISTING
    assert result.listing_status == ACTIVE
    assert indexed.queries == ['site:psauction.se/auction "68986"']
    assert verifier.diagnostics()["failed"] == 1


def test_rendered_swedish_status_markers_match_indexed_status_contract() -> None:
    """Browser-rendered Swedish markers must agree with indexed corroboration."""
    ended = enrich_sweden_page_verification(
        PageVerification(
            url=ENDED_ITEM_URL,
            title="Didrikssons barnkläder",
            text="Parti med kläder. Auktionen avslutad. Såld.",
            bounded_context="Parti med kläder. Auktionen avslutad. Såld.",
            listing_status=UNKNOWN,
            page_role=ITEM_LISTING,
            opportunity_identity="url-id:826330",
            identity_stable=True,
            verified=True,
        )
    )
    active = enrich_sweden_page_verification(
        PageVerification(
            url=ACTIVE_FIXTURE_URL,
            title="Arbetskläder parti",
            text=(
                "50 st arbetskläder. Auktionen avslutas 2026-08-20 10:35. "
                "Nuvarande bud 250 SEK."
            ),
            bounded_context=(
                "50 st arbetskläder. Auktionen avslutas 2026-08-20 10:35. "
                "Nuvarande bud 250 SEK."
            ),
            listing_status=UNKNOWN,
            page_role=ITEM_LISTING,
            opportunity_identity="url-id:999999",
            identity_stable=True,
            verified=True,
        )
    )

    assert ended.listing_status == ENDED
    assert active.listing_status == ACTIVE
