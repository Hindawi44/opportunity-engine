from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from opportunity_engine.discovery.jobalots_official_page_enrichment import (
    APPROVED_DOMAINS,
    APPROVED_PAGE_HOSTS,
    DISCOVERY_QUERY,
    FEED_FAMILY,
    ROBOTS_URL,
    FetchedPage,
    collect_jobalots_official_page_enrichment,
    jobalots_page_candidate_from_html,
)
from opportunity_engine.discovery.search_provider import SearchHit

NOW = datetime(2026, 8, 6, 7, 15, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts/build_domain_market_intelligence_feed.py"


def _html(*, ended: bool = True, clothing: bool = True, sku: str = "NP-YELLOW7944") -> str:
    title = (
        "Pallet of Clothing Including Mens T-Shirts, Womens Shoes & More"
        if clothing
        else "Pallet of Garden Tools and Home Accessories"
    )
    end_text = "Ended at 08:15:59 19 Jun" if ended else "Ends at 18:00:00 30 Aug"
    return f"""
    <html><head><meta property="og:title" content="{title}" />
    <meta name="description" content="Wholesale auction pallet" /></head><body>
    <h1>{title}</h1><div>{end_text}</div><div>Current bid £ 355.00</div>
    <section><h3>Details</h3><div>Reference price £ 5093.24</div>
    <div>Reserve price £ 203.73</div><div>Type Pallets</div>
    <div>Condition Customer Returns</div><div>Lot Qty 90</div>
    <div>Weight 500.00 (KG)</div><div>Shipping See shipping details here</div>
    <div>Vendor Jobalots UK</div><div>Location United Kingdom</div>
    <div>SKU {sku}</div></section><h3>Manifest Details</h3>
    <a href="/manifests/{sku}.csv">Download manifest</a>
    <div>Summary Total quantity 90 Total value £ 5093.24</div></body></html>
    """


def _hit(index: int) -> SearchHit:
    return SearchHit(
        title=f"Clothing pallet customer returns lot {index}",
        url=f"https://jobalots.com/en/products/CLOTHING-{index}?currency=gbp&utm_source=test",
        description="Wholesale auction pallet of clothing and footwear with manifest.",
        provider="Brave Search",
    )


def test_scope_is_one_query_and_three_current_product_pages() -> None:
    assert APPROVED_DOMAINS == ("jobalots.com",)
    assert APPROVED_PAGE_HOSTS == ("jobalots.com", "www.jobalots.com")
    assert "site:jobalots.com/en/products/" in DISCOVERY_QUERY


def test_extracts_source_backed_fields_from_official_ended_page() -> None:
    candidate = jobalots_page_candidate_from_html(
        source_url="https://jobalots.com/en/products/NP-YELLOW794445819.7516804398?currency=gbp",
        html_text=_html(ended=True),
        observed_at=NOW,
    )
    assert candidate is not None
    assert candidate["feed_family"] == FEED_FAMILY
    assert candidate["listing_status"] == "ENDED"
    assert candidate["quantity"] == 90
    assert candidate["quantity_unit"] == "items"
    assert candidate["lot_units"] == 1
    assert candidate["lot_unit_type"] == "pallets"
    assert candidate["current_bid"] == 355
    assert candidate["currency"] == "GBP"
    assert candidate["estimated_retail_value"] == 5093.24
    assert candidate["reserve_price"] == 203.73
    assert candidate["weight_kg"] == 500
    assert candidate["manifest_available"] is True
    assert candidate["stock_location"] == "United Kingdom"
    assert candidate["source_country"] == "GB"
    assert candidate["source_reference"] == "NP-YELLOW7944"
    assert candidate["seller_name"] == "Jobalots UK"
    assert candidate["page_sha256"]
    assert candidate["source_evidence"]
    assert candidate["opportunity_state"] == "EARLY_B2B_SIGNAL_REQUIRES_VERIFICATION"
    assert candidate["decision_owner"] == "HUMAN_OPERATOR"
    assert candidate["automatic_bid"] is False
    assert candidate["automatic_purchase"] is False


def test_active_page_remains_human_decision_only() -> None:
    candidate = jobalots_page_candidate_from_html(
        source_url="https://www.jobalots.com/en/products/ACTIVE-CLOTHING-LOT",
        html_text=_html(ended=False, sku="ACTIVE-1"),
        observed_at=NOW,
    )
    assert candidate is not None
    assert candidate["listing_status"] == "ACTIVE_REQUIRES_VERIFICATION"
    assert candidate["auction_end_text"].startswith("18:00:00")
    assert candidate["opportunity_state"] == "B2B_LEAD_REQUIRES_VERIFICATION"
    assert candidate["top5_eligible"] is False
    assert candidate["analysis_eligible"] is False
    assert candidate["automatic_bid"] is False
    assert candidate["automatic_payment"] is False


def test_rejects_non_clothing_and_unapproved_urls() -> None:
    assert jobalots_page_candidate_from_html(
        source_url="https://jobalots.com/en/products/GARDEN-1",
        html_text=_html(clothing=False),
        observed_at=NOW,
    ) is None
    assert jobalots_page_candidate_from_html(
        source_url="https://jobalots-fake.example/en/products/CLOTHING-1",
        html_text=_html(),
        observed_at=NOW,
    ) is None
    assert jobalots_page_candidate_from_html(
        source_url="https://jobalots.com/en/pages/help-center",
        html_text=_html(),
        observed_at=NOW,
    ) is None


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    @property
    def name(self) -> str:
        return "Fake Brave"

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        self.calls.append((query, count))
        return [*[_hit(index) for index in range(5)], SearchHit(
            title="Impostor clothing lot",
            url="https://fake.example/en/products/CLOTHING",
            description="pallet auction clothing",
        )]


class FakeFetcher:
    def __init__(self, *, robots: str = "User-agent: *\nAllow: /en/products/\nCrawl-delay: 0\n") -> None:
        self.calls: list[str] = []
        self.robots = robots

    def __call__(self, url: str) -> FetchedPage:
        self.calls.append(url)
        if url == ROBOTS_URL:
            return FetchedPage(url, url, 200, "text/plain", self.robots, len(self.robots))
        sku = url.rstrip("/").rsplit("/", 1)[-1]
        text = _html(ended=False, sku=sku)
        return FetchedPage(url, url, 200, "text/html; charset=utf-8", text, len(text.encode()))


def test_collection_uses_one_search_one_robots_and_at_most_three_pages() -> None:
    providers: list[FakeProvider] = []
    fetcher = FakeFetcher()

    def factory(country: str, api_key: str, freshness: str | None) -> FakeProvider:
        assert country == "GB"
        assert api_key == "secret"
        assert freshness == "pm"
        provider = FakeProvider()
        providers.append(provider)
        return provider

    report = collect_jobalots_official_page_enrichment(
        observed_at=NOW,
        environment={"BRAVE_SEARCH_API_KEY": "secret"},
        provider_factory=factory,
        page_fetcher=fetcher,
        sleep_fn=lambda _: None,
        results_per_query=8,
        max_pages=3,
    )
    assert report["status_counts"] == {"SUCCESS": 1}
    assert report["query_budget_total"] == 1
    assert report["brave_requests_made"] == 1
    assert report["robots_requests_made"] == 1
    assert report["page_requests_made"] == 3
    assert report["requests_made"] == 5
    assert report["candidate_count"] == 3
    assert report["discovered_official_url_count"] == 5
    assert len(providers[0].calls) == 1
    assert fetcher.calls[0] == ROBOTS_URL
    assert len(fetcher.calls) == 4
    assert report["quantity_size_rejection_enabled"] is False
    assert report["human_decision_required"] is True
    assert report["automatic_bid"] is False
    assert report["automatic_purchase"] is False


def test_robots_disallow_blocks_all_product_page_requests() -> None:
    fetcher = FakeFetcher(robots="User-agent: *\nDisallow: /en/products/\n")
    report = collect_jobalots_official_page_enrichment(
        observed_at=NOW,
        environment={"BRAVE_SEARCH_API_KEY": "secret"},
        provider_factory=lambda *_: FakeProvider(),
        page_fetcher=fetcher,
        sleep_fn=lambda _: None,
    )
    assert report["status_counts"] == {"BLOCKED_ROBOTS": 1}
    assert report["block_reason"] == "ROBOTS_DISALLOWS_PRODUCT_PAGES"
    assert report["page_requests_made"] == 0
    assert fetcher.calls == [ROBOTS_URL]


def test_missing_key_is_explicit_and_makes_no_request() -> None:
    def forbidden_factory(*args, **kwargs):
        raise AssertionError("provider must not be initialized")

    def forbidden_fetcher(url: str) -> FetchedPage:
        raise AssertionError(f"page must not be fetched: {url}")

    report = collect_jobalots_official_page_enrichment(
        observed_at=NOW,
        environment={},
        provider_factory=forbidden_factory,
        page_fetcher=forbidden_fetcher,
    )
    assert report["status_counts"] == {"BLOCKED_CONFIGURATION": 1}
    assert report["requests_made"] == 0
    assert report["candidate_count"] == 0


def test_daily_builder_writes_and_attaches_page_enrichment() -> None:
    text = BUILD_SCRIPT.read_text(encoding="utf-8")
    assert "collect_jobalots_official_page_enrichment" in text
    assert 'jobalots-official-page-enrichment.json' in text
    assert 'brief["jobalots_official_page_enrichment"]' in text
    assert '"HUMAN_OPERATOR"' in text
    assert '"automatic_bid": False' in text
    assert '"automatic_purchase": False' in text
