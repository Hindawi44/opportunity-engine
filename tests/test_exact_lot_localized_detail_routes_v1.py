from __future__ import annotations

from opportunity_engine.discovery.exact_lot_child_link_resolution import AggregateHtmlFetchResult
from opportunity_engine.discovery.exact_lot_multihop_resolution import (
    _commercial_url_role,
    resolve_exact_lot_multihop,
)
from opportunity_engine.discovery.exa_shadow_page_verification import ACTIVE_STOCK_SIGNAL
from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult


def test_singular_product_detail_is_navigable_without_shopify_plural_path() -> None:
    assert (
        _commercial_url_role(
            "https://example.nl/product/kledingpartij-herenkleding-1290-stuks/"
        )
        == "PRODUCT_DETAIL"
    )


def test_numeric_marketplace_listing_slug_is_navigable_but_search_root_is_not() -> None:
    assert (
        _commercial_url_role(
            "https://example.fr/acheter/c-547094-lot-vetements-multimarque-en-destockage.html"
        )
        == "PRODUCT_DETAIL"
    )
    assert (
        _commercial_url_role(
            "https://example.fr/acheter/recherche-fournisseur-0-vetements.html"
        )
        is None
    )


def test_singular_product_route_can_reach_strict_exact_lot() -> None:
    root = "https://example.nl/"
    product = "https://example.nl/product/kledingpartij-herenkleding-1290-stuks/"
    verification = {
        "status": "SUCCESS",
        "provider": "exa",
        "shadow_only": True,
        "symmetric_provider_verification": True,
        "commercial_specificity_gate_enforced": True,
        "project_domain_gate_enforced": True,
        "required_project_domain": "CLOTHING_INVENTORY",
        "verified_pages": [
            {
                "market_code": "NL",
                "query": "Nederland kledingvoorraad restpartij groothandel",
                "url": root,
                "final_url": root,
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

    def html_fetcher(url: str) -> AggregateHtmlFetchResult:
        if url == root:
            return AggregateHtmlFetchResult(
                url,
                url,
                True,
                200,
                '<a href="/product/kledingpartij-herenkleding-1290-stuks/">TE KOOP</a>',
            )
        return AggregateHtmlFetchResult(url, url, False, 404, "", "HTTP_404")

    def page_fetcher(url: str) -> PageFetchResult:
        assert url == product
        return PageFetchResult(
            url,
            url,
            True,
            200,
            "Kledingpartij herenkleding - 1290 stuks",
            (
                "Kledingpartij en voorraad merkkleding te koop. 1290 stuks. "
                "Prijs voor de partij 12 900 EUR."
            ),
        )

    report = resolve_exact_lot_multihop(
        verification,
        aggregate_fetcher=html_fetcher,
        page_fetcher=page_fetcher,
        max_root_parents=1,
        max_navigation_depth=1,
        max_links_per_page=5,
        max_navigation_page_fetches=5,
    )

    assert report["exact_lot_candidate_count"] == 1
    assert report["navigation_page_fetches_attempted"] == 1
    assert report["exact_lots"][0]["url"] == product
    assert report["exact_lots"][0]["evidence"]["item_specific_url_evidence"] is True
