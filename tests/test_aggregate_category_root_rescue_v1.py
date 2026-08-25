from __future__ import annotations

from opportunity_engine.discovery.exact_lot_child_link_resolution import AggregateHtmlFetchResult
from opportunity_engine.discovery.exact_lot_multihop_resolution import resolve_exact_lot_multihop
from opportunity_engine.discovery.exa_shadow_page_verification import ACTIVE_STOCK_SIGNAL
from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult

ROOT = "https://salzmann-restwaren.de/products/bekleidung/page/4/"
CHILD = "https://salzmann-restwaren.de/product/damenbekleidung-restposten-a-ware"


def _verification(*, direct_sale: bool = True) -> dict:
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
                "query": "Deutschland Bekleidung Salzmann Restwaren Restposten Großhandel",
                "url": ROOT,
                "final_url": ROOT,
                "title": "Kleidung im Großhandel kaufen | Günstige Angebote",
                "fetch_ok": True,
                "classification": ACTIVE_STOCK_SIGNAL,
                # Mirrors the live false-negative: Tool Learning may call the
                # aggregate category useful because the generic item URL guard
                # sees /products/, but Multi-Hop must still treat the URL role
                # itself as aggregate navigation only.
                "tool_learning_useful": True,
                "evidence": {
                    "project_domain": "CLOTHING_INVENTORY",
                    "inventory_evidence": True,
                    "direct_sale_evidence": direct_sale,
                    "item_specific_url_evidence": True,
                    "price_evidence": False,
                    "quantity_evidence": True,
                },
            }
        ],
    }


def _html_fetcher(url: str) -> AggregateHtmlFetchResult:
    if url == ROOT:
        return AggregateHtmlFetchResult(
            url,
            url,
            True,
            200,
            '<a href="/product/damenbekleidung-restposten-a-ware">Damenbekleidung</a>',
        )
    return AggregateHtmlFetchResult(url, url, False, 404, "", "HTTP_404")


def _page_fetcher(url: str) -> PageFetchResult:
    if url == CHILD:
        return PageFetchResult(
            url,
            url,
            True,
            200,
            "Lot de vêtements en stock",
            "Stock de vêtements Grade A. 50 pièces. Prix 100 €. Ajouter au panier. Paiement sécurisé.",
        )
    return PageFetchResult(url, url, False, 404, "", "", "HTTP_404")


def test_live_shape_aggregate_category_can_navigate_to_strict_child_without_root_credit() -> None:
    report = resolve_exact_lot_multihop(
        _verification(),
        aggregate_fetcher=_html_fetcher,
        page_fetcher=_page_fetcher,
        max_root_parents=1,
        max_navigation_depth=2,
        max_links_per_page=4,
        max_navigation_page_fetches=1,
    )

    assert report["schema_version"] == "exact-lot-multihop-resolution-1.4"
    assert report["aggregate_role_root_navigation_only"] is True
    assert report["aggregate_role_root_is_qualification_evidence"] is False
    assert report["eligible_root_parent_count"] == 1
    assert report["root_results"][0]["root_navigation_role"] == "CATEGORY"
    assert report["root_results"][0]["root_exact_lot_accepted"] is False
    assert report["navigation_page_fetches_attempted"] == 1
    assert report["exact_lot_candidate_count"] == 1
    assert report["exact_lots"][0]["url"] == CHILD
    assert report["exact_lots"][0]["parent_url"] == ROOT


def test_aggregate_category_without_direct_sale_proof_is_not_rescued_as_root() -> None:
    report = resolve_exact_lot_multihop(
        _verification(direct_sale=False),
        aggregate_fetcher=_html_fetcher,
        page_fetcher=_page_fetcher,
        max_root_parents=1,
        max_navigation_depth=2,
        max_links_per_page=4,
        max_navigation_page_fetches=1,
    )

    assert report["eligible_root_parent_count"] == 0
    assert report["navigation_page_fetches_attempted"] == 0
    assert report["exact_lot_candidate_count"] == 0
