from __future__ import annotations

from datetime import datetime, timezone

from opportunity_engine.discovery.stockhurt_official_catalog_enrichment import (
    AUCTION_URL,
    CATALOG_URLS,
    ROBOTS_URL,
    SHOP_URL,
    FetchedPage,
    collect_stockhurt_official_catalog_enrichment,
)
from opportunity_engine.discovery.stockhurt_redirect_partial_recovery import (
    PATCH_SCHEMA_VERSION,
    approved_stockhurt_redirect,
)

NOW = datetime(2026, 8, 6, 10, 40, tzinfo=timezone.utc)


def _catalog_html() -> str:
    return """
    <html><body>
      <a href="/en/product/warehouse-womens-clothing-grade-b/">
        Warehouse women's clothing grade B wholesale package
      </a>
      <a href="/en/product/nike-womens-clothing-grade-a/">
        Nike women's clothing grade A wholesale pallet
      </a>
      <a href="/en/product/veepee-clothing-grade-a/">
        Veepee clothing grade A stock lot
      </a>
    </body></html>
    """


def _product_html(code: str) -> str:
    return f"""
    <html><head><meta name="description" content="Branded wholesale clothing stock" /></head>
    <body>
      <h1>Women's clothing grade A wholesale stock</h1>
      <div>Available quantity: 500 pieces.</div>
      <div>Minimum order 50 pieces.</div>
      <div>€4.50 per piece.</div>
      <div>Brand: Warehouse.</div>
      <div>Grade A. Original stock with tags.</div>
      <div>Condition: outlet stock.</div>
      <div>Delivery in Europe and international shipping information available.</div>
      <div>Product code: {code}</div>
      <a href="/files/{code}-packing-list.xlsx">Packing list</a>
    </body></html>
    """


def _page(requested: str, final: str, text: str, content_type: str = "text/html") -> FetchedPage:
    return FetchedPage(
        requested_url=requested,
        final_url=final,
        status_code=200,
        content_type=content_type,
        text=text,
        bytes_read=len(text.encode()),
    )


class RedirectAndChallengeFetcher:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, url: str) -> FetchedPage:
        self.calls.append(url)
        if url == ROBOTS_URL:
            text = "User-agent: *\nAllow: /en/\nCrawl-delay: 0\n"
            return _page(url, url, text, "text/plain")
        if url == SHOP_URL:
            # Reproduces the live class of failure: the fixed catalogue request
            # finishes on another official same-domain landing path.
            return _page(url, "https://stockhurt.com/", _catalog_html())
        if url == AUCTION_URL:
            return _page(
                url,
                url,
                "Please wait while your request is being verified",
            )
        code = url.rstrip("/").rsplit("/", 1)[-1].upper()[:30]
        return _page(url, url, _product_html(code))


class OneCatalogErrorFetcher(RedirectAndChallengeFetcher):
    def __call__(self, url: str) -> FetchedPage:
        if url == AUCTION_URL:
            self.calls.append(url)
            raise RuntimeError("temporary catalogue timeout")
        if url == SHOP_URL:
            self.calls.append(url)
            return _page(url, url, _catalog_html())
        return super().__call__(url)


def test_redirect_policy_allows_only_official_https_targets() -> None:
    assert approved_stockhurt_redirect(SHOP_URL, "https://stockhurt.com/") is True
    assert approved_stockhurt_redirect(SHOP_URL, "https://www.stockhurt.com/en/shop/") is True
    assert approved_stockhurt_redirect(SHOP_URL, "http://stockhurt.com/en/shop/") is False
    assert approved_stockhurt_redirect(SHOP_URL, "https://stockhurt-fake.example/en/shop/") is False
    assert approved_stockhurt_redirect(
        "https://stockhurt.com/en/product/test/",
        "https://stockhurt.com/en/product/test/",
    ) is True
    assert approved_stockhurt_redirect(
        "https://stockhurt.com/en/product/test/",
        "https://stockhurt.com/my-account/",
    ) is False


def test_preserves_shop_candidates_when_auction_catalogue_is_protected() -> None:
    fetcher = RedirectAndChallengeFetcher()
    report = collect_stockhurt_official_catalog_enrichment(
        observed_at=NOW,
        environment={},
        page_fetcher=fetcher,
        sleep_fn=lambda _: None,
    )

    assert report["schema_version"] == PATCH_SCHEMA_VERSION
    assert report["status_counts"] == {
        "PARTIAL_SUCCESS_WITH_SOURCE_PROTECTION": 1
    }
    assert report["block_reason"] == (
        "SOURCE_PROTECTION_ON_SOME_PAGES_PARTIAL_RESULTS_PRESERVED"
    )
    assert report["catalog_requests_made"] == 2
    assert report["catalog_success_count"] == 1
    assert report["catalog_redirect_count"] == 1
    assert report["source_protection_challenge_count"] == 1
    assert report["product_requests_made"] == 3
    assert report["candidate_count"] == 3
    assert report["requests_made"] == 6
    assert report["errors"] == []
    assert report["catalog_fetches"][0]["requested_url"] == SHOP_URL
    assert report["catalog_fetches"][0]["final_url"] == "https://stockhurt.com/"
    assert report["catalog_fetches"][0]["redirected"] is True
    assert report["catalog_fetches"][1]["source_protection_challenge"] is True
    assert report["decision_owner"] == "HUMAN_OPERATOR"
    assert report["automatic_bid"] is False
    assert report["automatic_purchase"] is False


def test_preserves_candidates_when_other_catalogue_has_retrieval_error() -> None:
    report = collect_stockhurt_official_catalog_enrichment(
        observed_at=NOW,
        environment={},
        page_fetcher=OneCatalogErrorFetcher(),
        sleep_fn=lambda _: None,
    )

    assert report["status_counts"] == {
        "PARTIAL_SUCCESS_WITH_RETRIEVAL_ERRORS": 1
    }
    assert report["catalog_success_count"] == 1
    assert report["catalog_error_count"] == 1
    assert report["candidate_count"] == 3
    assert report["errors"]
    assert "temporary catalogue timeout" in report["errors"][0]
    assert report["catalog_fetches"][1]["error"]
    assert report["partial_results_preserved"] is True
    assert report["quantity_size_rejection_enabled"] is False


def test_fixed_request_budget_remains_unchanged() -> None:
    report = collect_stockhurt_official_catalog_enrichment(
        observed_at=NOW,
        page_fetcher=RedirectAndChallengeFetcher(),
        sleep_fn=lambda _: None,
    )
    assert CATALOG_URLS == (SHOP_URL, AUCTION_URL)
    assert report["robots_requests_made"] == 1
    assert report["catalog_requests_made"] <= 2
    assert report["product_requests_made"] <= 3
    assert report["requests_made"] <= 6
