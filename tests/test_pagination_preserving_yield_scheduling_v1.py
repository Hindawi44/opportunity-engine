from __future__ import annotations

from opportunity_engine.discovery.exact_lot_child_link_resolution import AggregateHtmlFetchResult
from opportunity_engine.discovery.exact_lot_multihop_resolution import (
    _extract_navigation_links,
    resolve_exact_lot_multihop,
)
from opportunity_engine.discovery.exa_shadow_page_verification import ACTIVE_STOCK_SIGNAL
from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult

SALZMANN_PAGE_4 = "https://salzmann-restwaren.de/products/bekleidung/page/4/"
SALZMANN_PAGE_3 = "https://salzmann-restwaren.de/products/bekleidung/page/3/"
SALZMANN_PAGE_5 = "https://salzmann-restwaren.de/products/bekleidung/page/5/"

ROOT_YIELD = "https://yield.example/"
ROOT_ZERO = "https://zero.example/"
YIELD_PRODUCTS = [f"https://yield.example/product/jacke-{index}" for index in range(1, 11)]
ZERO_PRODUCTS = [f"https://zero.example/product/jacke-{index}" for index in range(1, 11)]


def _root(url: str) -> dict:
    return {
        "market_code": "DE",
        "query": "Deutschland Bekleidung Restposten",
        "url": url,
        "final_url": url,
        "fetch_ok": True,
        "classification": ACTIVE_STOCK_SIGNAL,
        "tool_learning_useful": False,
        "evidence": {
            "project_domain": "CLOTHING_INVENTORY",
            "inventory_evidence": True,
            "direct_sale_evidence": True,
            "price_evidence": True,
            "item_specific_url_evidence": False,
        },
    }


def _verification(*roots: str) -> dict:
    return {
        "status": "SUCCESS",
        "provider": "exa",
        "shadow_only": True,
        "symmetric_provider_verification": True,
        "commercial_specificity_gate_enforced": True,
        "project_domain_gate_enforced": True,
        "required_project_domain": "CLOTHING_INVENTORY",
        "verified_pages": [_root(url) for url in roots],
    }


def _many_product_links(prefix: str, count: int = 12) -> str:
    return "".join(
        f'<a href="/product/{prefix}-{index}">{prefix}-{index}</a>'
        for index in range(1, count + 1)
    )


def test_catalog_pagination_survives_product_detail_saturation_without_more_links() -> None:
    html = (
        _many_product_links("bekleidung", 12)
        + '<a href="/products/bekleidung/page/3/">Previous</a>'
        + '<a href="/products/bekleidung/page/5/">Next</a>'
    )

    links = _extract_navigation_links(
        page_url=SALZMANN_PAGE_4,
        root_host="salzmann-restwaren.de",
        html_text=html,
        max_links=12,
    )

    assert len(links) == 12
    assert SALZMANN_PAGE_3 in links
    assert SALZMANN_PAGE_5 in links
    assert sum("/product/" in url for url in links) == 10


def _html_fetcher(url: str) -> AggregateHtmlFetchResult:
    if url == ROOT_YIELD:
        html = "".join(
            f'<a href="{product}">Yield product</a>' for product in YIELD_PRODUCTS
        )
        return AggregateHtmlFetchResult(url, url, True, 200, html)
    if url == ROOT_ZERO:
        html = "".join(
            f'<a href="{product}">Zero product</a>' for product in ZERO_PRODUCTS
        )
        return AggregateHtmlFetchResult(url, url, True, 200, html)
    return AggregateHtmlFetchResult(url, url, False, 404, "", "HTTP_404")


def _page_fetcher(url: str) -> PageFetchResult:
    if url in YIELD_PRODUCTS:
        return PageFetchResult(
            url,
            url,
            True,
            200,
            "Bekleidung Jacken Restposten",
            "Bekleidung Lagerbestand. 50 Stück. Preis 100 €. Jetzt kaufen. Auf Lager.",
        )
    if url in ZERO_PRODUCTS:
        return PageFetchResult(
            url,
            url,
            True,
            200,
            "Bekleidung Jacken Lagerbestand",
            "Bekleidung Lagerbestand verfügbar. Kontaktieren Sie uns für Details.",
        )
    return PageFetchResult(url, url, False, 404, "", "", "HTTP_404")


def test_zero_yield_root_is_deferred_only_after_fair_probe_when_another_root_proves_yield() -> None:
    report = resolve_exact_lot_multihop(
        _verification(ROOT_YIELD, ROOT_ZERO),
        aggregate_fetcher=_html_fetcher,
        page_fetcher=_page_fetcher,
        max_root_parents=2,
        max_navigation_depth=2,
        max_links_per_page=10,
        max_navigation_page_fetches=10,
    )

    assert report["status"] == "SUCCESS"
    assert report["root_fair_navigation"] is True
    assert report["navigation_scheduling"] == "ROUND_ROBIN_ROOT_FAIR_V1"
    assert report["post_probe_scheduling"] == "PROVEN_YIELD_PRESERVATION_V1"
    assert report["fair_probe_fetches_per_root"] == 3
    assert report["yield_stall_requires_proven_alternative"] is True
    assert report["yield_stall_is_qualification_evidence"] is False
    assert report["max_navigation_page_fetches"] == 10
    assert report["navigation_page_fetches_attempted"] == 10
    assert report["root_navigation_fetch_counts"][ROOT_ZERO] == 3
    assert report["root_navigation_fetch_counts"][ROOT_YIELD] == 7
    assert report["root_exact_lot_counts"][ROOT_ZERO] == 0
    assert report["root_exact_lot_counts"][ROOT_YIELD] == 7
    assert report["yield_stalled_root_count"] == 1
    assert report["exact_lot_candidate_count"] == 7


def test_zero_yield_roots_remain_root_fair_when_no_proven_alternative_exists() -> None:
    report = resolve_exact_lot_multihop(
        _verification(ROOT_ZERO, "https://zero-two.example/"),
        aggregate_fetcher=lambda url: (
            _html_fetcher(ROOT_ZERO)
            if url == ROOT_ZERO
            else AggregateHtmlFetchResult(
                url,
                url,
                True,
                200,
                "".join(
                    f'<a href="/product/jacke-{index}">Zero two</a>'
                    for index in range(1, 11)
                ),
            )
        ),
        page_fetcher=lambda url: PageFetchResult(
            url,
            url,
            True,
            200,
            "Bekleidung Jacken Lagerbestand",
            "Bekleidung Lagerbestand verfügbar. Kontaktieren Sie uns für Details.",
        ),
        max_root_parents=2,
        max_navigation_depth=2,
        max_links_per_page=10,
        max_navigation_page_fetches=8,
    )

    assert report["status"] == "SUCCESS"
    assert report["navigation_page_fetches_attempted"] == 8
    assert report["exact_lot_candidate_count"] == 0
    assert report["yield_stalled_root_count"] == 0
    assert sorted(report["root_navigation_fetch_counts"].values()) == [4, 4]
