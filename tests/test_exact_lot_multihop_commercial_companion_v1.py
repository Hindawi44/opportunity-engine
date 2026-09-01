from __future__ import annotations

from opportunity_engine.discovery.exact_lot_child_link_resolution import AggregateHtmlFetchResult
from opportunity_engine.discovery.exact_lot_multihop_resolution import resolve_exact_lot_multihop
from opportunity_engine.discovery.exa_shadow_page_verification import ACTIVE_STOCK_SIGNAL
from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult

ROOT = "https://example.se/restpartier"
PRODUCT = "https://example.se/product/restparti-damklader-140-st"
FRAGT = "https://example.se/frakt"
CONTACT = "https://example.se/kontakt"
QUERY = "Sverige restparti kläder grossist lager"


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
                "market_code": "SE",
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


def test_multihop_attaches_bounded_companion_context_without_changing_exact_lot_gate() -> None:
    aggregate_calls: list[str] = []

    def aggregate_fetcher(url: str) -> AggregateHtmlFetchResult:
        aggregate_calls.append(url)
        pages = {
            ROOT: (
                '<a href="/product/restparti-damklader-140-st">Damkläder</a>'
                '<a href="/frakt">Frakt</a>'
                '<a href="/kontakt">Kontakt</a>'
            ),
            FRAGT: '<p>Frakt: tillkommer enligt offert</p>',
            CONTACT: '<p>Företag: Example Grossist AB</p><p>Organisationsnummer: 556677-8899</p>',
        }
        html = pages.get(url, "")
        if not html:
            return AggregateHtmlFetchResult(url, url, False, 404, "", "HTTP_404")
        return AggregateHtmlFetchResult(url, url, True, 200, html)

    def page_fetcher(url: str) -> PageFetchResult:
        if url == PRODUCT:
            return PageFetchResult(
                url,
                url,
                True,
                200,
                "Restparti damkläder 140 st",
                "Restparti kläder säljes. Kvantitet: 140 st. Pris: 14 000 SEK. Available for sale.",
            )
        return PageFetchResult(url, url, False, 404, "", "", "HTTP_404")

    report = resolve_exact_lot_multihop(
        _verification(),
        aggregate_fetcher=aggregate_fetcher,
        page_fetcher=page_fetcher,
        max_root_parents=1,
        max_navigation_depth=1,
        max_links_per_page=6,
        max_navigation_page_fetches=4,
    )

    assert report["status"] == "SUCCESS"
    assert report["exact_lot_candidate_count"] == 1
    assert report["navigation_page_fetches_attempted"] == 1
    assert report["commercial_companion_root_count"] == 1
    assert report["commercial_companion_page_fetches_attempted"] == 2
    assert report["commercial_companion_page_fetches_succeeded"] == 2
    assert aggregate_calls.count(FRAGT) == 1
    assert aggregate_calls.count(CONTACT) == 1

    exact = report["exact_lots"][0]
    assert exact["exact_lot_accepted"] is True
    companion = exact["evidence"]["commercial_companion_verification"]
    assert companion["status"] == "SUCCESS"
    assert companion["seller_identity_candidates"]
    assert companion["fulfilment_candidates"] == ["Frakt: tillkommer enligt offert"]
    assert companion["lot_condition_evidence_allowed"] is False
    assert companion["companion_evidence_is_qualification_evidence"] is False
    assert companion["paid_search_request_count"] == 0
    assert exact["evidence"]["commercial_companion_evidence_is_qualification_evidence"] is False


def test_multihop_does_not_fetch_companions_when_item_page_already_has_seller_and_fulfilment() -> None:
    companion_calls: list[str] = []

    def aggregate_fetcher(url: str) -> AggregateHtmlFetchResult:
        if url == ROOT:
            return AggregateHtmlFetchResult(
                url,
                url,
                True,
                200,
                (
                    '<a href="/product/restparti-damklader-140-st">Damkläder</a>'
                    '<a href="/frakt">Frakt</a><a href="/kontakt">Kontakt</a>'
                ),
            )
        companion_calls.append(url)
        return AggregateHtmlFetchResult(url, url, True, 200, "<p>Företag: Should Not Fetch AB</p>")

    def page_fetcher(url: str) -> PageFetchResult:
        return PageFetchResult(
            url,
            url,
            True,
            200,
            "Restparti damkläder 140 st",
            (
                "Restparti kläder säljes. Kvantitet: 140 st. Pris: 14 000 SEK. "
                "Säljare: Example AB. Frakt: enligt offert."
            ),
        )

    report = resolve_exact_lot_multihop(
        _verification(),
        aggregate_fetcher=aggregate_fetcher,
        page_fetcher=page_fetcher,
        max_root_parents=1,
        max_navigation_depth=1,
        max_links_per_page=6,
        max_navigation_page_fetches=4,
    )

    assert report["exact_lot_candidate_count"] == 1
    assert report["commercial_companion_root_count"] == 0
    assert report["commercial_companion_page_fetches_attempted"] == 0
    assert companion_calls == []
    exact = report["exact_lots"][0]
    assert "commercial_companion_verification" not in exact["evidence"]
