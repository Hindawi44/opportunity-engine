from __future__ import annotations

from opportunity_engine.discovery.exact_lot_child_link_resolution import AggregateHtmlFetchResult
from opportunity_engine.discovery.exact_lot_multihop_resolution import resolve_exact_lot_multihop
from opportunity_engine.discovery.exa_shadow_page_verification import INFO_OR_LEGAL_ONLY
from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult

HUB = "https://friptadium.com/pages/lot-de-vetements-revendeur"
PRODUCT = "https://friptadium.com/products/hauts-femme-au-kilo"
ABOUT = "https://friptadium.com/pages/about"
QUERY = "France vêtements mode lot de marchandises à vendre prix quantité stock déstockage disponible"


def _hub_verification(url: str = HUB) -> dict:
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
                "query": QUERY,
                "title": "Lot de vêtements pour revendeur : fripe Grade A | Friptadium",
                "url": url,
                "final_url": url,
                "fetch_ok": True,
                "classification": INFO_OR_LEGAL_ONLY,
                "tool_learning_useful": False,
                "evidence": {
                    "project_domain": "CLOTHING_INVENTORY",
                    "inventory_evidence": True,
                    "direct_sale_evidence": True,
                    "quantity_evidence": True,
                    "price_evidence": False,
                    "item_specific_url_evidence": True,
                    "info_or_legal_evidence": True,
                },
            }
        ],
    }


def _aggregate_fetcher(url: str) -> AggregateHtmlFetchResult:
    if url != HUB:
        return AggregateHtmlFetchResult(url, url, False, 404, "", "HTTP_404")
    html = (
        '<a href="/products/hauts-femme-au-kilo">Hauts femme au kilo</a>'
        '<a href="/blogs/news">Blog</a>'
        '<a href="/pages/contact">Contact</a>'
        '<a href="https://evil.example/products/fake">Off domain</a>'
    )
    return AggregateHtmlFetchResult(url, url, True, 200, html)


def _page_fetcher(url: str) -> PageFetchResult:
    if url == PRODUCT:
        return PageFetchResult(
            url,
            url,
            True,
            200,
            "Hauts femme au kilo à revendre",
            (
                "Stock de vêtements Grade A. Choisissez 3 kg à 24,99 €. "
                "Environ 12 à 18 pièces. Ajouter au panier. Paiement sécurisé."
            ),
        )
    return PageFetchResult(url, url, False, 404, "", "", "HTTP_404")


def test_verified_commercial_clothing_hub_is_navigation_only_root_to_exact_product() -> None:
    report = resolve_exact_lot_multihop(
        _hub_verification(),
        aggregate_fetcher=_aggregate_fetcher,
        page_fetcher=_page_fetcher,
        max_root_parents=1,
        max_navigation_depth=2,
        max_links_per_page=8,
        max_navigation_page_fetches=8,
    )

    assert report["status"] == "SUCCESS"
    assert report["commercial_hub_navigation_only"] is True
    assert report["eligible_root_parent_count"] == 1
    assert report["gateway_page_count"] == 0
    assert report["exact_lot_candidate_count"] == 1

    root = report["root_results"][0]
    assert root["root_url"] == HUB
    assert root["root_navigation_role"] == "COMMERCIAL_HUB"
    assert root["root_exact_lot_accepted"] is False

    exact = report["exact_lots"][0]
    assert exact["url"] == PRODUCT
    assert exact["parent_url"] == HUB
    assert exact["navigation_chain"] == [HUB, PRODUCT]
    assert exact["exact_lot_accepted"] is True
    assert HUB not in {row["url"] for row in report["exact_lots"]}


def test_info_page_outside_commercial_hub_role_cannot_be_navigation_root() -> None:
    report = resolve_exact_lot_multihop(
        _hub_verification(ABOUT),
        aggregate_fetcher=_aggregate_fetcher,
        page_fetcher=_page_fetcher,
        max_root_parents=1,
        max_navigation_depth=2,
        max_links_per_page=8,
        max_navigation_page_fetches=8,
    )

    assert report["status"] == "SUCCESS"
    assert report["eligible_root_parent_count"] == 0
    assert report["root_results"] == []
    assert report["exact_lot_candidate_count"] == 0
