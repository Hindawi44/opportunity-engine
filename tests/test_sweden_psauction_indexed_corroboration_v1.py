from __future__ import annotations

from datetime import datetime, timezone

from opportunity_engine.discovery.clothing_inventory_search import (
    ACTIVE,
    ENDED,
    UNRESOLVED_SOURCE,
    PageVerification,
)
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.sweden_psauction_playwright import (
    PSAuctionPlaywrightConfig,
    PSAuctionPlaywrightFallbackVerifier,
)


ITEM = (
    "https://psauction.se/item/view/1560018/"
    "parti-med-klader-och-accessoarer-ca-600-artiklar"
)
OTHER_ITEM = "https://psauction.se/item/view/1560019/annat-parti"
NOW = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)


class FakeIndexedSearch:
    name = "fake-indexed-search"

    def __init__(self, hits):
        self.hits = list(hits)
        self.queries = []

    def search(self, query: str, *, count: int = 10):
        self.queries.append((query, count))
        return self.hits[:count]


def _unresolved(url: str = ITEM) -> PageVerification:
    return PageVerification(
        url=url,
        page_role=UNRESOLVED_SOURCE,
        verified=False,
        error="insufficient public listing content",
    )


def _shell(url: str):
    return url, "<html><body>Enable JavaScript</body></html>"


def _hit(description: str, *, url: str = ITEM) -> SearchHit:
    return SearchHit(
        title="Parti med kläder och accessoarer, ca 600 artiklar",
        url=url,
        description=description,
        provider="Brave Search",
    )


def _verifier(hits):
    return PSAuctionPlaywrightFallbackVerifier(
        lambda url: _unresolved(url),
        config=PSAuctionPlaywrightConfig(max_pages=6, delay_seconds=2.0),
        rendered_page_loader=_shell,
        indexed_search_provider=FakeIndexedSearch(hits),
        clock=lambda: NOW,
    )


def test_future_exact_auction_deadline_confirms_active_listing():
    verifier = _verifier(
        [
            _hit(
                "Konkursbo. Lager med cirka 600 plagg. "
                "Auktionen avslutas Måndag, 2026-08-17 18:00."
            )
        ]
    )

    result = verifier(ITEM)
    diagnostics = verifier.diagnostics()

    assert result.verified is True
    assert result.listing_status == ACTIVE
    assert result.identity_stable is True
    assert result.opportunity_identity == "url-id:1560018"
    assert result.clothing_inventory_evidence is True
    assert result.sale_evidence is True
    assert result.event_scenario == "COMPANY_BANKRUPTCY"
    assert diagnostics["indexed_attempted"] == 1
    assert diagnostics["indexed_resolved_active"] == 1
    assert diagnostics["overall_resolved"] == 1


def test_explicit_ended_marker_confirms_historical_listing():
    verifier = _verifier(
        [
            _hit(
                "Stort parti med kläder och skor, ca 10 pall. "
                "Auktionen avslutas Torsdag, 2019-01-03 15:30 | "
                "Auktionen avslutad | Såld"
            )
        ]
    )

    result = verifier(ITEM)
    diagnostics = verifier.diagnostics()

    assert result.verified is True
    assert result.listing_status == ENDED
    assert result.sale_evidence is False
    assert diagnostics["indexed_resolved_ended"] == 1


def test_past_exact_auction_deadline_confirms_ended_without_sold_word():
    verifier = _verifier(
        [
            _hit(
                "Parti med kläder och accessoarer, ca 600 artiklar. "
                "Auktionen avslutas Fredag, 2026-08-14 17:30."
            )
        ]
    )

    result = verifier(ITEM)

    assert result.verified is True
    assert result.listing_status == ENDED


def test_same_day_deadline_without_clock_remains_unresolved():
    verifier = _verifier(
        [
            _hit(
                "Parti med kläder och accessoarer, ca 600 artiklar. "
                "Auktionen slutar Söndag, 2026-08-16."
            )
        ]
    )

    result = verifier(ITEM)
    diagnostics = verifier.diagnostics()

    assert result.verified is False
    assert diagnostics["indexed_unresolved"] == 1


def test_wrong_item_search_result_cannot_corroborate_candidate():
    verifier = _verifier(
        [
            _hit(
                "Auktionen avslutas Måndag, 2026-08-17 18:00.",
                url=OTHER_ITEM,
            )
        ]
    )

    result = verifier(ITEM)

    assert result.verified is False
    assert "lacked exact clothing/bulk evidence" in str(result.error)


def test_generic_binding_bid_text_without_deadline_does_not_confirm_active():
    verifier = _verifier(
        [
            _hit(
                "Buden är bindande och serviceavgiften debiteras på alla objekt. "
                "Parti med kläder och accessoarer, ca 600 artiklar."
            )
        ]
    )

    result = verifier(ITEM)

    assert result.verified is False
    assert result.listing_status != ACTIVE


def test_indexed_search_is_bounded_to_exact_item_query():
    search = FakeIndexedSearch(
        [
            _hit(
                "Parti med kläder och accessoarer, ca 600 artiklar. "
                "Auktionen avslutas Måndag, 2026-08-17 18:00."
            )
        ]
    )
    verifier = PSAuctionPlaywrightFallbackVerifier(
        lambda url: _unresolved(url),
        rendered_page_loader=_shell,
        indexed_search_provider=search,
        clock=lambda: NOW,
    )

    verifier(ITEM)

    assert search.queries == [('site:psauction.se/item/view "1560018"', 5)]
    diagnostics = verifier.diagnostics()
    assert diagnostics["automatic_contact"] is False
    assert diagnostics["automatic_bid"] is False
    assert diagnostics["automatic_purchase_decision"] is False
    assert diagnostics["automatic_payment"] is False
