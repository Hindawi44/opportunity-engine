from __future__ import annotations

from opportunity_engine.discovery.exact_lot_child_link_resolution import AggregateHtmlFetchResult
from opportunity_engine.discovery.exact_lot_multihop_resolution import resolve_exact_lot_multihop
from opportunity_engine.discovery.exa_shadow_page_verification import ACTIVE_STOCK_SIGNAL
from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult

ROOT = "https://friptadium.com/"
HUB = "https://friptadium.com/pages/lot-de-vetements-revendeur"
COLLECTION = "https://friptadium.com/collections/femme-basic"
PRODUCT = "https://friptadium.com/products/hauts-femme-au-kilo"
DELIVERY = "https://friptadium.com/delivery"
CONTACT = "https://friptadium.com/contact"
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


def _page(url: str, *, seller_and_fulfilment: bool = False) -> PageFetchResult:
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
        suffix = " Seller: Friptadium SAS. Delivery: available by quote." if seller_and_fulfilment else ""
        return PageFetchResult(
            url,
            url,
            True,
            200,
            "Hauts femme au kilo à revendre",
            (
                "Stock de vêtements Grade A. Choisissez 3 kg à 24,99 €. "
                "Environ 12 à 18 pièces. Ajouter au panier. Paiement sécurisé."
                + suffix
            ),
        )
    return PageFetchResult(url, url, False, 404, "", "", "HTTP_404")


def test_multihop_attaches_bounded_companion_context_without_changing_exact_lot_gate() -> None:
    aggregate_calls: list[str] = []

    def aggregate_fetcher(url: str) -> AggregateHtmlFetchResult:
        aggregate_calls.append(url)
        pages = {
            ROOT: (
                '<a href="/pages/lot-de-vetements-revendeur">Lots revendeur</a>'
                '<a href="/delivery">Delivery</a>'
                '<a href="/contact">Contact</a>'
            ),
            HUB: '<a href="/collections/femme-basic">Femme Basic</a>',
            COLLECTION: '<a href="/products/hauts-femme-au-kilo">Hauts Femme Basic</a>',
            DELIVERY: '<p>Delivery: available by commercial quote</p>',
            CONTACT: '<p>Company: Friptadium SAS</p><p>Company number: FR123456789</p>',
        }
        html = pages.get(url, "")
        if not html:
            return AggregateHtmlFetchResult(url, url, False, 404, "", "HTTP_404")
        return AggregateHtmlFetchResult(url, url, True, 200, html)

    report = resolve_exact_lot_multihop(
        _verification(),
        aggregate_fetcher=aggregate_fetcher,
        page_fetcher=_page,
        max_root_parents=1,
        max_navigation_depth=3,
        max_links_per_page=6,
        max_navigation_page_fetches=8,
    )

    assert report["status"] == "SUCCESS"
    assert report["exact_lot_candidate_count"] == 1
    assert report["navigation_page_fetches_attempted"] == 3
    assert report["commercial_companion_root_count"] == 1
    assert report["commercial_companion_page_fetches_attempted"] == 2
    assert report["commercial_companion_page_fetches_succeeded"] == 2
    assert aggregate_calls.count(DELIVERY) == 1
    assert aggregate_calls.count(CONTACT) == 1

    exact = report["exact_lots"][0]
    assert exact["exact_lot_accepted"] is True
    companion = exact["evidence"]["commercial_companion_verification"]
    assert companion["status"] == "SUCCESS"
    assert companion["seller_identity_candidates"]
    assert companion["fulfilment_candidates"] == ["Delivery: available by commercial quote"]
    assert companion["lot_condition_evidence_allowed"] is False
    assert companion["companion_evidence_is_qualification_evidence"] is False
    assert companion["paid_search_request_count"] == 0
    assert exact["evidence"]["commercial_companion_evidence_is_qualification_evidence"] is False


def test_multihop_does_not_fetch_companions_when_item_page_already_has_seller_and_fulfilment() -> None:
    companion_calls: list[str] = []

    def aggregate_fetcher(url: str) -> AggregateHtmlFetchResult:
        pages = {
            ROOT: (
                '<a href="/pages/lot-de-vetements-revendeur">Lots revendeur</a>'
                '<a href="/delivery">Delivery</a><a href="/contact">Contact</a>'
            ),
            HUB: '<a href="/collections/femme-basic">Femme Basic</a>',
            COLLECTION: '<a href="/products/hauts-femme-au-kilo">Hauts Femme Basic</a>',
        }
        if url in pages:
            return AggregateHtmlFetchResult(url, url, True, 200, pages[url])
        companion_calls.append(url)
        return AggregateHtmlFetchResult(url, url, True, 200, "<p>Company: Should Not Fetch SAS</p>")

    def page_fetcher(url: str) -> PageFetchResult:
        return _page(url, seller_and_fulfilment=True)

    report = resolve_exact_lot_multihop(
        _verification(),
        aggregate_fetcher=aggregate_fetcher,
        page_fetcher=page_fetcher,
        max_root_parents=1,
        max_navigation_depth=3,
        max_links_per_page=6,
        max_navigation_page_fetches=8,
    )

    assert report["exact_lot_candidate_count"] == 1
    assert report["commercial_companion_root_count"] == 0
    assert report["commercial_companion_page_fetches_attempted"] == 0
    assert companion_calls == []
    exact = report["exact_lots"][0]
    assert "commercial_companion_verification" not in exact["evidence"]
