from __future__ import annotations

from opportunity_engine.discovery.exact_lot_child_link_resolution import AggregateHtmlFetchResult
from opportunity_engine.discovery.exact_lot_multihop_resolution import resolve_exact_lot_multihop
from opportunity_engine.discovery.exa_shadow_page_verification import ACTIVE_STOCK_SIGNAL
from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult

ROOT = "https://friptadium.com/"
HUB = "https://friptadium.com/pages/lot-de-vetements-revendeur"
COLLECTION = "https://friptadium.com/collections/femme-basic"
PRODUCT = "https://friptadium.com/products/hauts-femme-au-kilo"
QUERY = "France vêtements mode lot de marchandises à vendre prix quantité stock déstockage disponible"


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
                "market_code": "FR",
                "query": QUERY,
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
            '<a href="/pages/lot-de-vetements-revendeur">Lots revendeur</a>'
            '<a href="https://evil.example/products/fake">off domain</a>'
            '<a href="/blogs/news">blog</a>'
        ),
        HUB: (
            '<a href="/collections/femme-basic">Femme Basic</a>'
            '<a href="/policies/privacy-policy">privacy</a>'
        ),
        COLLECTION: (
            '<a href="/products/hauts-femme-au-kilo">Hauts Femme Basic</a>'
            '<a href="/pages/contact">contact</a>'
        ),
    }.get(url, "")
    if not html:
        return AggregateHtmlFetchResult(url, url, False, 404, "", "HTTP_404")
    return AggregateHtmlFetchResult(url, url, True, 200, html)


def _page_fetcher(url: str) -> PageFetchResult:
    if url == HUB:
        return PageFetchResult(
            url,
            url,
            True,
            200,
            "Lot de vêtements pour revendeur : lots et box au kilo",
            (
                "Stock de vêtements pour revendeurs. Guide complet. Lots en vente. "
                "Formats 3 kg et 10 kg. Prix de 24,99 € à 179,99 €."
            ),
        )
    if url == COLLECTION:
        return PageFetchResult(
            url,
            url,
            True,
            200,
            "Vêtements femme au kilo - Basic",
            "Stock de vêtements en vente. 6 produits. Formats 3 kg. Prix 24,99 €.",
        )
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


def test_multihop_reaches_strict_product_through_bounded_commercial_gateways() -> None:
    report = resolve_exact_lot_multihop(
        _verification(),
        aggregate_fetcher=_html_fetcher,
        page_fetcher=_page_fetcher,
        max_root_parents=1,
        max_navigation_depth=3,
        max_links_per_page=8,
        max_navigation_page_fetches=8,
    )

    assert report["status"] == "SUCCESS"
    assert report["exact_lot_candidate_count"] == 1
    assert report["gateway_page_count"] == 2
    assert report["navigation_page_fetches_attempted"] == 3
    assert report["same_origin_only"] is True
    assert report["bounded_multi_hop"] is True
    assert report["production_mutation"] is False

    exact = report["exact_lots"][0]
    assert exact["url"] == PRODUCT
    assert exact["navigation_depth"] == 3
    assert exact["navigation_chain"] == [ROOT, HUB, COLLECTION, PRODUCT]
    assert exact["evidence"]["price_evidence"] is True
    assert exact["evidence"]["quantity_evidence"] is True
    assert exact["evidence"]["explicit_purchase_evidence"] is True

    visited = {row["url"] for row in report["navigation_results"]}
    assert "https://evil.example/products/fake" not in visited
    assert "https://friptadium.com/blogs/news" not in visited
    assert "https://friptadium.com/policies/privacy-policy" not in visited
    assert "https://friptadium.com/pages/contact" not in visited


def test_multihop_depth_budget_stops_before_product() -> None:
    report = resolve_exact_lot_multihop(
        _verification(),
        aggregate_fetcher=_html_fetcher,
        page_fetcher=_page_fetcher,
        max_root_parents=1,
        max_navigation_depth=2,
        max_links_per_page=8,
        max_navigation_page_fetches=8,
    )

    assert report["status"] == "SUCCESS"
    assert report["exact_lot_candidate_count"] == 0
    assert all(row["url"] != PRODUCT for row in report["navigation_results"])
    assert report["depth_budget_exhausted_count"] >= 1


def test_gateway_pages_never_receive_exact_lot_credit() -> None:
    report = resolve_exact_lot_multihop(
        _verification(),
        aggregate_fetcher=_html_fetcher,
        page_fetcher=_page_fetcher,
        max_root_parents=1,
        max_navigation_depth=3,
        max_links_per_page=8,
        max_navigation_page_fetches=8,
    )

    gateway_urls = {row["url"] for row in report["gateway_pages"]}
    exact_urls = {row["url"] for row in report["exact_lots"]}
    assert gateway_urls == {HUB, COLLECTION}
    assert gateway_urls.isdisjoint(exact_urls)


def test_multihop_fails_closed_when_provider_verification_safety_missing() -> None:
    verification = _verification()
    verification["commercial_specificity_gate_enforced"] = False

    report = resolve_exact_lot_multihop(
        verification,
        aggregate_fetcher=_html_fetcher,
        page_fetcher=_page_fetcher,
    )

    assert report["status"] == "BLOCKED_INPUT"
    assert report["block_reason"] == "COMMERCIAL_SPECIFICITY_GATE_NOT_ENFORCED"
    assert report["exact_lot_candidate_count"] == 0
