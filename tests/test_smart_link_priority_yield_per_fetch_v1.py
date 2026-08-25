from __future__ import annotations

from opportunity_engine.discovery.exact_lot_child_link_resolution import AggregateHtmlFetchResult
from opportunity_engine.discovery.exact_lot_multihop_resolution import (
    _extract_navigation_links,
    resolve_exact_lot_multihop,
)
from opportunity_engine.discovery.exa_shadow_page_verification import ACTIVE_STOCK_SIGNAL
from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult

ROOT = "https://catalog.example/"
PAPER = "https://catalog.example/product/lot-de-papeterie"
PAINT = "https://catalog.example/product/lot-de-peinture"
SHORTS = "https://catalog.example/product/box-shorts-de-marque"
JACKETS = "https://catalog.example/product/lot-de-vestes-et-costumes"


def _root_verification() -> dict:
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
                "market_code": "FR",
                "query": "France vêtements stock lot grossiste",
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
    if url != ROOT:
        return AggregateHtmlFetchResult(url, url, False, 404, "", "HTTP_404")
    html = (
        '<a href="/product/lot-de-papeterie">Paper</a>'
        '<a href="/product/lot-de-peinture">Paint</a>'
        '<a href="/product/box-shorts-de-marque">Shorts</a>'
        '<a href="/product/lot-de-vestes-et-costumes">Jackets</a>'
    )
    return AggregateHtmlFetchResult(url, url, True, 200, html)


def _page_fetcher(url: str) -> PageFetchResult:
    if url in {SHORTS, JACKETS}:
        return PageFetchResult(
            url,
            url,
            True,
            200,
            "Lot de vêtements en stock",
            "Stock de vêtements Grade A. 50 pièces. Prix 100 €. Ajouter au panier. Paiement sécurisé.",
        )
    if url in {PAPER, PAINT}:
        return PageFetchResult(
            url,
            url,
            True,
            200,
            "Lot commercial en stock",
            "Stock disponible. 50 pièces. Prix 100 €. Ajouter au panier.",
        )
    return PageFetchResult(url, url, False, 404, "", "", "HTTP_404")


def test_smart_link_priority_reorders_but_does_not_filter_neutral_links() -> None:
    links = _extract_navigation_links(
        page_url=ROOT,
        root_host="catalog.example",
        html_text=_html_fetcher(ROOT).html,
        max_links=4,
    )

    assert links == [SHORTS, JACKETS, PAPER, PAINT]
    assert set(links) == {PAPER, PAINT, SHORTS, JACKETS}


def test_smart_link_priority_improves_yield_without_increasing_fetch_budget() -> None:
    report = resolve_exact_lot_multihop(
        _root_verification(),
        aggregate_fetcher=_html_fetcher,
        page_fetcher=_page_fetcher,
        max_root_parents=1,
        max_navigation_depth=2,
        max_links_per_page=4,
        max_navigation_page_fetches=2,
    )

    assert report["status"] == "SUCCESS"
    assert report["navigation_scheduling"] == "ROUND_ROBIN_ROOT_FAIR_V1"
    assert report["within_root_link_priority"] == "ROLE_THEN_CLOTHING_SUBJECT_V1"
    assert report["link_priority_is_qualification_evidence"] is False
    assert report["navigation_page_fetches_attempted"] == 2
    assert [row["url"] for row in report["navigation_results"]] == [SHORTS, JACKETS]
    assert report["exact_lot_candidate_count"] == 2
    assert report["exact_lot_yield_per_fetch"] == 1.0
    assert report["page_budget_exhausted_count"] == 2
