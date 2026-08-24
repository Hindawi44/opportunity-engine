from __future__ import annotations

from opportunity_engine.discovery.exact_lot_child_link_resolution import AggregateHtmlFetchResult
from opportunity_engine.discovery.exact_lot_multihop_resolution import resolve_exact_lot_multihop
from opportunity_engine.discovery.exa_shadow_page_verification import ACTIVE_STOCK_SIGNAL
from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult

ROOT_A = "https://catalog-a.example/"
ROOT_B = "https://catalog-b.example/"
A1 = "https://catalog-a.example/product/a1"
A2 = "https://catalog-a.example/product/a2"
A3 = "https://catalog-a.example/product/a3"
WINNER = "https://catalog-b.example/product/winner"


def _root(url: str) -> dict:
    return {
        "market_code": "FR",
        "query": "France vêtements stock lot grossiste",
        "url": url,
        "final_url": url,
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


def _verification() -> dict:
    return {
        "status": "SUCCESS",
        "provider": "exa",
        "shadow_only": True,
        "symmetric_provider_verification": True,
        "commercial_specificity_gate_enforced": True,
        "project_domain_gate_enforced": True,
        "required_project_domain": "CLOTHING_INVENTORY",
        "verified_pages": [_root(ROOT_A), _root(ROOT_B)],
    }


def _html_fetcher(url: str) -> AggregateHtmlFetchResult:
    html = {
        ROOT_A: (
            '<a href="/product/a1">A1</a>'
            '<a href="/product/a2">A2</a>'
            '<a href="/product/a3">A3</a>'
        ),
        ROOT_B: '<a href="/product/winner">Winner</a>',
    }.get(url, "")
    if not html:
        return AggregateHtmlFetchResult(url, url, False, 404, "", "HTTP_404")
    return AggregateHtmlFetchResult(url, url, True, 200, html)


def _page_fetcher(url: str) -> PageFetchResult:
    if url == WINNER:
        return PageFetchResult(
            url,
            url,
            True,
            200,
            "Lot de vêtements en stock",
            "Stock de vêtements Grade A. 50 pièces. Prix 100 €. Ajouter au panier. Paiement sécurisé.",
        )
    if url in {A1, A2, A3}:
        return PageFetchResult(
            url,
            url,
            True,
            200,
            "Vêtements en stock",
            "Stock de vêtements disponible. Contactez-nous pour les détails.",
        )
    return PageFetchResult(url, url, False, 404, "", "", "HTTP_404")


def test_root_fair_scheduler_prevents_first_catalogue_from_starving_second_root() -> None:
    report = resolve_exact_lot_multihop(
        _verification(),
        aggregate_fetcher=_html_fetcher,
        page_fetcher=_page_fetcher,
        max_root_parents=2,
        max_navigation_depth=2,
        max_links_per_page=8,
        max_navigation_page_fetches=2,
    )

    assert report["status"] == "SUCCESS"
    assert report["root_fair_navigation"] is True
    assert report["navigation_scheduling"] == "ROUND_ROBIN_ROOT_FAIR_V1"
    assert report["navigation_page_fetches_attempted"] == 2
    assert report["root_navigation_fetch_counts"] == {ROOT_A: 1, ROOT_B: 1}
    assert report["exact_lot_candidate_count"] == 1
    assert report["exact_lots"][0]["url"] == WINNER
    assert report["page_budget_exhausted_count"] >= 2
