from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from opportunity_engine.discovery.jobalots_official_catalog_discovery import (
    ALL_CATALOG_URL,
    APPROVED_DOMAINS,
    CATALOG_URLS,
    CLOTHING_CATALOG_URL,
    FEED_FAMILY,
    JobalotsCatalogFetcher,
    collect_jobalots_official_catalog_discovery,
    discover_product_links_from_catalog_html,
)
from opportunity_engine.discovery.jobalots_official_page_enrichment import (
    FetchedPage,
    ROBOTS_URL,
)

NOW = datetime(2026, 8, 6, 8, 45, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts/build_domain_market_intelligence_feed.py"


def _catalog_html(*handles: str, labelled: bool = False) -> str:
    links = []
    for index, handle in enumerate(handles):
        label = (
            f"Pallet of womens clothing and footwear customer returns {index}"
            if labelled
            else ""
        )
        links.append(
            f'<a href="/en/products/{handle}?currency=gbp">'
            f'<img alt="{label}" /></a>'
        )
    return "<html><body>" + "".join(links) + "</body></html>"


def _product_html(handle: str, *, clothing: bool = True) -> str:
    title = (
        f"Pallet of Womens Clothing and Footwear {handle}"
        if clothing
        else f"Pallet of Garden Tools {handle}"
    )
    return f"""
    <html><head><meta property="og:title" content="{title}" /></head><body>
    <h1>{title}</h1>
    <div>Ends at 18:00:00 30 Aug</div>
    <div>Current bid £ 355.00</div>
    <div>Reference price £ 5093.24</div>
    <div>Reserve price £ 203.73</div>
    <div>Type Pallets</div>
    <div>Condition Customer Returns</div>
    <div>Lot Qty 90</div>
    <div>Weight 500.00 (KG)</div>
    <div>Shipping See shipping details here</div>
    <div>Vendor Jobalots UK</div>
    <div>Location United Kingdom</div>
    <div>SKU {handle}</div>
    <h3>Manifest Details</h3>
    <a href="/manifests/{handle}.csv">Download manifest</a>
    <div>Wholesale liquidation auction job lot pallet.</div>
    </body></html>
    """


def test_scope_is_fixed_to_two_catalogs_and_three_product_pages() -> None:
    assert APPROVED_DOMAINS == ("jobalots.com",)
    assert CATALOG_URLS == (CLOTHING_CATALOG_URL, ALL_CATALOG_URL)
    assert "categories=clothing" in CLOTHING_CATALOG_URL


def test_clothing_catalog_accepts_unlabelled_official_product_links() -> None:
    links = discover_product_links_from_catalog_html(
        catalog_url=CLOTHING_CATALOG_URL,
        html_text=_catalog_html("CLOTHING-1", "CLOTHING-2"),
    )
    assert [link.url for link in links] == [
        "https://jobalots.com/en/products/CLOTHING-1",
        "https://jobalots.com/en/products/CLOTHING-2",
    ]
    assert all(link.catalog_scope == "CLOTHING_CATEGORY" for link in links)
    assert all(link.discovery_rank >= 100 for link in links)


def test_general_catalog_ranks_clothing_context_and_deduplicates_json_links() -> None:
    html = """
    <a href="/en/products/GARDEN-1">Pallet of garden tools</a>
    <a href="https://www.jobalots.com/en/products/CLOTHING-1?currency=gbp">
      Pallet of clothing and footwear customer returns
    </a>
    <script>{"url":"\\/en\\/products\\/CLOTHING-1"}</script>
    """
    links = discover_product_links_from_catalog_html(
        catalog_url=ALL_CATALOG_URL,
        html_text=html,
    )
    assert len(links) == 2
    assert links[0].url == "https://jobalots.com/en/products/CLOTHING-1"
    assert "clothing" in links[0].clothing_terms


class FakeFetcher:
    def __init__(
        self,
        *,
        robots: str = "User-agent: *\nAllow: /en/pages/products-on-auction\nAllow: /en/products/\nCrawl-delay: 0\n",
    ) -> None:
        self.calls: list[str] = []
        self.robots = robots

    def __call__(self, url: str) -> FetchedPage:
        self.calls.append(url)
        if url == ROBOTS_URL:
            text = self.robots
            return FetchedPage(url, url, 200, "text/plain", text, len(text))
        if url == CLOTHING_CATALOG_URL:
            text = _catalog_html("CLOTHING-1", "CLOTHING-2", "CLOTHING-3", "CLOTHING-4")
            return FetchedPage(url, url, 200, "text/html", text, len(text))
        if url == ALL_CATALOG_URL:
            text = _catalog_html("CLOTHING-2", labelled=True) + (
                '<a href="/en/products/GARDEN-1">Pallet of garden tools</a>'
            )
            return FetchedPage(url, url, 200, "text/html", text, len(text))
        handle = url.rstrip("/").rsplit("/", 1)[-1]
        text = _product_html(handle, clothing=not handle.startswith("GARDEN"))
        return FetchedPage(url, url, 200, "text/html", text, len(text.encode()))


def test_direct_collection_fetches_two_catalogs_and_at_most_three_products() -> None:
    fetcher = FakeFetcher()
    report = collect_jobalots_official_catalog_discovery(
        observed_at=NOW,
        environment={},
        page_fetcher=fetcher,
        sleep_fn=lambda _: None,
        max_catalog_pages=2,
        max_product_pages=3,
    )
    assert report["status_counts"] == {"SUCCESS": 1}
    assert report["search_provider_used"] is False
    assert report["api_key_required"] is False
    assert report["robots_requests_made"] == 1
    assert report["catalog_requests_made"] == 2
    assert report["product_requests_made"] == 3
    assert report["requests_made"] == 6
    assert report["discovered_product_url_count"] == 5
    assert report["selected_product_url_count"] == 3
    assert report["candidate_count"] == 3
    assert len(fetcher.calls) == 6
    assert report["quantity_size_rejection_enabled"] is False
    assert report["decision_owner"] == "HUMAN_OPERATOR"
    for candidate in report["candidates"]:
        assert candidate["feed_family"] == FEED_FAMILY
        assert candidate["discovery_method"] == "OFFICIAL_CATALOG_HTML"
        assert candidate["catalog_scope"] == "CLOTHING_CATEGORY"
        assert candidate["quantity"] == 90
        assert candidate["current_bid"] == 355
        assert candidate["manifest_available"] is True
        assert candidate["top5_eligible"] is False
        assert candidate["automatic_bid"] is False
        assert candidate["automatic_purchase"] is False


def test_robots_disallow_blocks_catalog_and_product_requests() -> None:
    fetcher = FakeFetcher(
        robots="User-agent: *\nDisallow: /en/pages/products-on-auction\n"
    )
    report = collect_jobalots_official_catalog_discovery(
        observed_at=NOW,
        environment={},
        page_fetcher=fetcher,
        sleep_fn=lambda _: None,
    )
    assert report["status_counts"] == {"BLOCKED_ROBOTS": 1}
    assert report["block_reason"] == (
        "ROBOTS_DISALLOWS_CATALOG_OR_PRODUCT_PAGES"
    )
    assert report["requests_made"] == 1
    assert fetcher.calls == [ROBOTS_URL]


def test_no_catalog_links_is_valid_zero_without_product_fetches() -> None:
    class EmptyCatalogFetcher(FakeFetcher):
        def __call__(self, url: str) -> FetchedPage:
            if url in CATALOG_URLS:
                self.calls.append(url)
                return FetchedPage(url, url, 200, "text/html", "<html></html>", 13)
            return super().__call__(url)

    fetcher = EmptyCatalogFetcher()
    report = collect_jobalots_official_catalog_discovery(
        observed_at=NOW,
        environment={},
        page_fetcher=fetcher,
        sleep_fn=lambda _: None,
    )
    assert report["status_counts"] == {"VALID_ZERO": 1}
    assert report["requests_made"] == 3
    assert report["product_requests_made"] == 0
    assert report["candidate_count"] == 0


def test_fetcher_rejects_unapproved_urls_before_network_access() -> None:
    fetcher = JobalotsCatalogFetcher()
    try:
        fetcher("https://jobalots-fake.example/en/products/CLOTHING-1")
    except ValueError as exc:
        assert "outside approved" in str(exc)
    else:
        raise AssertionError("unapproved URL was not rejected")


def test_daily_builder_writes_and_attaches_catalog_discovery() -> None:
    text = BUILD_SCRIPT.read_text(encoding="utf-8")
    assert "collect_jobalots_official_catalog_discovery" in text
    assert 'jobalots-official-catalog-discovery.json' in text
    assert 'brief["jobalots_official_catalog_discovery"]' in text
    assert '"HUMAN_OPERATOR"' in text
    assert '"automatic_bid": False' in text
    assert '"automatic_purchase": False' in text
