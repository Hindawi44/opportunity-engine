from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from opportunity_engine.discovery.stockhurt_official_catalog_enrichment import (
    APPROVED_DOMAINS,
    AUCTION_URL,
    CATALOG_URLS,
    FEED_FAMILY,
    ROBOTS_URL,
    SHOP_URL,
    CatalogLink,
    FetchedPage,
    collect_stockhurt_official_catalog_enrichment,
    discover_stockhurt_product_links,
    is_source_protection_challenge,
    stockhurt_candidate_from_product_html,
)

NOW = datetime(2026, 8, 6, 9, 40, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts/build_domain_market_intelligence_feed.py"


def _product_html(
    *,
    title: str = "Warehouse women's clothing grade B (kg)",
    out_of_stock: bool = False,
    auction: bool = False,
    code: str = "WH-001",
) -> str:
    availability = "Out of stock" if out_of_stock else "Available for wholesale order"
    commercial = (
        "Pallet auction. Current bid 100 PLN. Auction ends: 30 August 2026 18:00."
        if auction
        else "Wholesale outlet clothing for pallets and packages. €4.50 per kg."
    )
    return f"""
    <html><head>
      <meta property="og:title" content="{title}" />
      <meta name="description" content="Branded wholesale clothing stock" />
      <script type="application/ld+json">
        {{"name": "{title}", "availability": "{availability}", "priceCurrency": "EUR"}}
      </script>
    </head><body>
      <h1>{title}</h1>
      <div>{availability}</div>
      <div>{commercial}</div>
      <div>Available quantity: 25000 kg.</div>
      <div>Minimum weight of 20 kg.</div>
      <div>Brand: Warehouse.</div>
      <div>Grade B. Original stock with tags.</div>
      <div>Condition: outlet customer returns.</div>
      <div>Delivery in Europe and international shipping information available.</div>
      <div>Product code: {code}</div>
      <a href="/wp-content/uploads/packing-list-{code}.xlsx">Packing list</a>
    </body></html>
    """


def _catalog_html() -> str:
    return """
    <html><body>
      <a href="/en/product/warehouse-womens-clothing-grade-b/">
        <img alt="Warehouse women's clothing grade B wholesale 20 kg" />
      </a>
      <a href="https://www.stockhurt.com/en/product/nike-womens-clothing-grade-a/?utm_source=x">
        Nike clothing grade A wholesale package
      </a>
      <script>window.products=["\/en\/product\/embedded-clothing-lot\/"];</script>
    </body></html>
    """


def test_scope_is_fixed_to_two_catalogs_and_official_domain() -> None:
    assert APPROVED_DOMAINS == ("stockhurt.com",)
    assert CATALOG_URLS == (SHOP_URL, AUCTION_URL)


def test_discovers_anchor_and_embedded_product_links() -> None:
    links = discover_stockhurt_product_links(
        catalog_url=SHOP_URL,
        html_text=_catalog_html(),
    )
    urls = [item.url for item in links]
    assert "https://stockhurt.com/en/product/warehouse-womens-clothing-grade-b/" in urls
    assert "https://stockhurt.com/en/product/nike-womens-clothing-grade-a/" in urls
    assert "https://stockhurt.com/en/product/embedded-clothing-lot/" in urls
    assert all(item.catalog_scope == "WHOLESALE_SHOP" for item in links)


def test_extracts_official_product_fields_for_human_decision() -> None:
    link = CatalogLink(
        url="https://stockhurt.com/en/product/warehouse-womens-clothing-grade-b/",
        catalog_url=SHOP_URL,
        catalog_scope="WHOLESALE_SHOP",
        context="Warehouse women's clothing grade B wholesale package",
        clothing_terms=("clothing",),
        commercial_terms=("wholesale", "package"),
        discovery_rank=88,
    )
    candidate = stockhurt_candidate_from_product_html(
        source_url=link.url,
        html_text=_product_html(),
        observed_at=NOW,
        catalog_link=link,
    )
    assert candidate is not None
    assert candidate["feed_family"] == FEED_FAMILY
    assert candidate["page_role"] == "SPECIFIC_STOCK_OFFER"
    assert candidate["listing_status"] == "ACTIVE_REQUIRES_VERIFICATION"
    assert candidate["minimum_order"] == 20
    assert candidate["minimum_order_unit"] == "kg"
    assert candidate["unit_price"] == 4.5
    assert candidate["currency"] == "EUR"
    assert candidate["grade"] == "B"
    assert "Warehouse" in candidate["brands"]
    assert candidate["manifest_available"] is True
    assert candidate["manifest_urls"]
    assert candidate["source_reference"] == "WH-001"
    assert candidate["page_sha256"]
    assert len(candidate["source_evidence"]) == 2
    assert candidate["decision_owner"] == "HUMAN_OPERATOR"
    assert candidate["quantity_size_rejection_applied"] is False
    assert candidate["automatic_purchase"] is False


def test_preserves_auction_and_out_of_stock_history() -> None:
    auction_link = CatalogLink(
        url="https://stockhurt.com/en/product/nike-auction-box/",
        catalog_url=AUCTION_URL,
        catalog_scope="PALLET_AUCTIONS",
        context="Nike clothing pallet auction",
        clothing_terms=("clothing",),
        commercial_terms=("pallet", "auction"),
        discovery_rank=120,
    )
    auction = stockhurt_candidate_from_product_html(
        source_url=auction_link.url,
        html_text=_product_html(auction=True, code="AUC-1"),
        observed_at=NOW,
        catalog_link=auction_link,
    )
    assert auction is not None
    assert auction["page_role"] == "PALLET_AUCTION_OFFER"
    assert auction["sale_mode"] == "AUCTION"
    assert auction["current_bid"] == 100
    assert auction["currency"] == "PLN"
    assert auction["auction_end_text"]
    assert auction["automatic_bid"] is False

    ended = stockhurt_candidate_from_product_html(
        source_url="https://stockhurt.com/en/product/veepee-clothing-grade-a/",
        html_text=_product_html(out_of_stock=True, code="OLD-1"),
        observed_at=NOW,
    )
    assert ended is not None
    assert ended["listing_status"] == "OUT_OF_STOCK"
    assert ended["opportunity_state"] == "EARLY_B2B_SIGNAL_REQUIRES_VERIFICATION"


def test_challenge_and_unapproved_pages_are_not_treated_as_valid_products() -> None:
    challenge = "<html><title>One moment, please...</title>Please wait while your request is being verified</html>"
    assert is_source_protection_challenge(challenge) is True
    assert stockhurt_candidate_from_product_html(
        source_url="https://stockhurt.com/en/product/test/",
        html_text=challenge,
        observed_at=NOW,
    ) is None
    assert stockhurt_candidate_from_product_html(
        source_url="https://stockhurt-fake.example/en/product/test/",
        html_text=_product_html(),
        observed_at=NOW,
    ) is None


class FakeFetcher:
    def __init__(self, *, challenge_catalogs: bool = False, robots_disallow: bool = False) -> None:
        self.calls: list[str] = []
        self.challenge_catalogs = challenge_catalogs
        self.robots_disallow = robots_disallow

    def __call__(self, url: str) -> FetchedPage:
        self.calls.append(url)
        if url == ROBOTS_URL:
            robots = (
                "User-agent: *\nDisallow: /en/product/\n"
                if self.robots_disallow
                else "User-agent: *\nAllow: /en/\nCrawl-delay: 0\n"
            )
            return FetchedPage(url, url, 200, "text/plain", robots, len(robots))
        if url in CATALOG_URLS:
            if self.challenge_catalogs:
                text = "Please wait while your request is being verified"
            elif url == SHOP_URL:
                text = _catalog_html()
            else:
                text = """
                <a href="/en/product/nike-auction-box/">Nike clothing pallet auction</a>
                <a href="/en/product/warehouse-womens-clothing-grade-b/">Duplicate clothing lot</a>
                """
            return FetchedPage(url, url, 200, "text/html", text, len(text.encode()))
        code = url.rstrip("/").rsplit("/", 1)[-1].upper()[:20]
        text = _product_html(auction="auction" in url, code=code)
        return FetchedPage(url, url, 200, "text/html", text, len(text.encode()))


def test_collection_is_bounded_and_deduplicates_before_enrichment() -> None:
    fetcher = FakeFetcher()
    report = collect_stockhurt_official_catalog_enrichment(
        observed_at=NOW,
        environment={},
        page_fetcher=fetcher,
        sleep_fn=lambda _: None,
        max_catalog_pages=2,
        max_product_pages=3,
    )
    assert report["status_counts"] == {"SUCCESS": 1}
    assert report["robots_requests_made"] == 1
    assert report["catalog_requests_made"] == 2
    assert report["product_requests_made"] == 3
    assert report["requests_made"] == 6
    assert report["discovered_product_url_count"] == 4
    assert report["selected_product_url_count"] == 3
    assert report["candidate_count"] == 3
    assert report["api_key_required"] is False
    assert report["quantity_size_rejection_enabled"] is False
    assert report["decision_owner"] == "HUMAN_OPERATOR"
    assert report["automatic_bid"] is False
    assert report["automatic_purchase"] is False
    assert len(fetcher.calls) == 6


def test_source_challenge_and_robots_are_reported_explicitly() -> None:
    challenged = collect_stockhurt_official_catalog_enrichment(
        observed_at=NOW,
        page_fetcher=FakeFetcher(challenge_catalogs=True),
        sleep_fn=lambda _: None,
    )
    assert challenged["status_counts"] == {"BLOCKED_SOURCE_PROTECTION": 1}
    assert challenged["source_protection_challenge_count"] == 2
    assert challenged["candidate_count"] == 0

    blocked_fetcher = FakeFetcher(robots_disallow=True)
    blocked = collect_stockhurt_official_catalog_enrichment(
        observed_at=NOW,
        page_fetcher=blocked_fetcher,
        sleep_fn=lambda _: None,
    )
    assert blocked["status_counts"] == {"BLOCKED_ROBOTS": 1}
    assert blocked["requests_made"] == 1
    assert blocked_fetcher.calls == [ROBOTS_URL]


def test_builder_writes_and_attaches_stockhurt_official_enrichment() -> None:
    text = BUILD_SCRIPT.read_text(encoding="utf-8")
    assert "collect_stockhurt_official_catalog_enrichment" in text
    assert 'stockhurt-official-catalog-enrichment.json' in text
    assert 'brief["stockhurt_official_catalog_enrichment"]' in text
    assert '"HUMAN_OPERATOR"' in text
    assert '"automatic_bid": False' in text
    assert '"automatic_purchase": False' in text
