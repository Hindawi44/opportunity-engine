from __future__ import annotations

from opportunity_engine.discovery.exact_lot_child_link_resolution import AggregateHtmlFetchResult
from opportunity_engine.discovery.exact_lot_multihop_resolution import resolve_exact_lot_multihop
from opportunity_engine.discovery.exa_shadow_page_verification import ACTIVE_STOCK_SIGNAL
from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult

ROOT = "https://example.de/products/bekleidung/"
CATEGORY = "https://example.de/products/bekleidung/herrenbekleidung/"
PRODUCT = "https://example.de/product/herbol-herren-fleece-und-sweatjacken-a-ware/"


def _verification() -> dict:
    return {
        "status": "SUCCESS",
        "provider": "exa",
        "shadow_only": True,
        "symmetric_provider_verification": True,
        "commercial_specificity_gate_enforced": True,
        "project_domain_gate_enforced": True,
        "required_project_domain": "CLOTHING_INVENTORY",
        "verified_pages": [
            {
                "market_code": "DE",
                "query": "Deutschland Restposten Bekleidung Großhandel Lager",
                "url": ROOT,
                "final_url": ROOT,
                "fetch_ok": True,
                "classification": ACTIVE_STOCK_SIGNAL,
                "tool_learning_useful": False,
                "evidence": {
                    "project_domain": "CLOTHING_INVENTORY",
                    "inventory_evidence": True,
                    "direct_sale_evidence": True,
                    "item_specific_url_evidence": False,
                },
            }
        ],
    }


def _html_fetcher(url: str) -> AggregateHtmlFetchResult:
    html = {
        ROOT: (
            '<a href="/products/schuhe/">Schuhe</a>'
            '<a href="/products/haus-garten-buero/">Haus Garten Büro</a>'
            '<a href="/products/elektro-multimedia/">Elektro</a>'
            '<a href="/products/bekleidung/herrenbekleidung/">Herrenbekleidung</a>'
        ),
        CATEGORY: (
            '<a href="/products/schuhe/">Schuhe</a>'
            '<a href="/product/herbol-herren-fleece-und-sweatjacken-a-ware/">'
            "Herbol Herren Fleece- und Sweatjacken A-Ware</a>"
        ),
    }.get(url, "")
    if not html:
        return AggregateHtmlFetchResult(url, url, False, 404, "", "HTTP_404")
    return AggregateHtmlFetchResult(url, url, True, 200, html)


def _page_fetcher(url: str) -> PageFetchResult:
    if url == CATEGORY:
        return PageFetchResult(
            url,
            url,
            True,
            200,
            "Herrenbekleidung Restposten",
            "Herrenbekleidung Lager. Verfügbare Menge 1124 Stk. Preis 2,88€.",
        )
    if url == PRODUCT:
        return PageFetchResult(
            url,
            url,
            True,
            200,
            "Herbol Herren Fleece- und Sweatjacken A-Ware",
            (
                "Restposten A-Ware. Verfügbare Menge 1124 Stk. Preis 2,88€. "
                "In den Warenkorb."
            ),
        )
    return PageFetchResult(url, url, False, 404, "", "", "HTTP_404")


def test_german_category_with_stock_cards_is_navigation_only_then_reaches_product() -> None:
    report = resolve_exact_lot_multihop(
        _verification(),
        aggregate_fetcher=_html_fetcher,
        page_fetcher=_page_fetcher,
        max_root_parents=1,
        max_navigation_depth=2,
        max_links_per_page=1,
        max_navigation_page_fetches=8,
    )

    assert report["status"] == "SUCCESS"
    assert report["root_results"][0]["navigation_links"] == [CATEGORY]
    assert report["gateway_page_count"] == 1
    assert report["exact_lot_candidate_count"] == 1

    gateway = report["gateway_pages"][0]
    assert gateway["url"] == CATEGORY
    assert gateway["navigation_role"] == "CATEGORY"
    assert gateway["evidence"]["direct_sale_evidence"] is False
    assert gateway["exact_lot_accepted"] is False

    exact = report["exact_lots"][0]
    assert exact["url"] == PRODUCT
    assert exact["navigation_role"] == "PRODUCT_DETAIL"
    assert exact["navigation_depth"] == 2
    assert exact["evidence"]["project_domain"] == "CLOTHING_INVENTORY"
    assert exact["evidence"]["direct_sale_evidence"] is True
    assert exact["evidence"]["price_evidence"] is True
    assert exact["evidence"]["quantity_evidence"] is True
    assert exact["evidence"]["explicit_purchase_evidence"] is True
