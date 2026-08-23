from __future__ import annotations

from opportunity_engine.discovery.exact_lot_child_link_resolution import (
    AggregateHtmlFetchResult,
    _extract_candidate_child_links,
    resolve_exact_lot_child_links,
)
from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY


def test_extract_candidate_child_links_is_same_origin_descendant_and_item_specific() -> None:
    parent = "https://www.sdpie.com/lots-en-vente/"
    html = """
    <html><body>
      <a href="/lots-en-vente/lot-de-vestes-et-costumes/">Vestes</a>
      <a href="https://www.sdpie.com/lots-en-vente/lot-de-vetements-friperie/#details">Friperie</a>
      <a href="/lots-en-vente/">Index</a>
      <a href="/products/">Products index</a>
      <a href="/lot/unrelated-root-lot">Not a descendant</a>
      <a href="https://evil.example/lot/stolen">Off site</a>
    </body></html>
    """

    assert _extract_candidate_child_links(parent_url=parent, html_text=html) == [
        "https://www.sdpie.com/lots-en-vente/lot-de-vestes-et-costumes/",
        "https://www.sdpie.com/lots-en-vente/lot-de-vetements-friperie/",
    ]


def test_resolver_follows_only_verified_clothing_aggregate_and_emits_only_exact_lots() -> None:
    parent = "https://www.sdpie.com/lots-en-vente/"
    exact_child = "https://www.sdpie.com/lots-en-vente/lot-de-vestes-et-costumes/"
    broad_child = "https://www.sdpie.com/lots-en-vente/lot-de-vetements-friperie/"
    verification = {
        "status": "SUCCESS",
        "provider": "exa",
        "shadow_only": True,
        "symmetric_provider_verification": True,
        "commercial_specificity_gate_enforced": True,
        "project_domain_gate_enforced": True,
        "required_project_domain": CLOTHING_INVENTORY,
        "verified_pages": [
            {
                "market_code": "FR",
                "query": "lot vêtements à vendre prix quantité",
                "title": "Lots en vente",
                "url": parent,
                "final_url": parent,
                "fetch_ok": True,
                "classification": "ACTIVE_STOCK_SIGNAL",
                "tool_learning_useful": False,
                "evidence": {
                    "project_domain": CLOTHING_INVENTORY,
                    "inventory_evidence": True,
                    "direct_sale_evidence": True,
                    "item_specific_url_evidence": False,
                },
            },
            {
                "market_code": "FR",
                "query": "ignored",
                "title": "Article",
                "url": "https://www.sdpie.com/blog/liquidation-guide/",
                "final_url": "https://www.sdpie.com/blog/liquidation-guide/",
                "fetch_ok": True,
                "classification": "INFO_OR_LEGAL_ONLY",
                "tool_learning_useful": False,
                "evidence": {"project_domain": CLOTHING_INVENTORY},
            },
        ],
    }

    parent_calls: list[str] = []
    child_calls: list[str] = []

    def parent_fetcher(url: str) -> AggregateHtmlFetchResult:
        parent_calls.append(url)
        return AggregateHtmlFetchResult(
            requested_url=url,
            final_url=url,
            ok=True,
            status_code=200,
            html=(
                '<a href="/lots-en-vente/lot-de-vestes-et-costumes/">Exact</a>'
                '<a href="/lots-en-vente/lot-de-vetements-friperie/">Broad</a>'
                '<a href="https://elsewhere.example/lot/nope">Nope</a>'
            ),
            error=None,
            truncated=False,
        )

    def child_fetcher(url: str) -> PageFetchResult:
        child_calls.append(url)
        if url == exact_child:
            return PageFetchResult(
                requested_url=url,
                final_url=url,
                ok=True,
                status_code=200,
                title="Lot de vestes et costumes",
                text="Lot de marchandises vêtements en vente. Prix 10 000 EUR. Quantité 3 796 pièces.",
                error=None,
                truncated=False,
            )
        if url == broad_child:
            return PageFetchResult(
                requested_url=url,
                final_url=url,
                ok=True,
                status_code=200,
                title="Lot de vêtements friperie",
                text="Lot de marchandises vêtements en vente. Quantité 230 000 pièces. Prix sur demande.",
                error=None,
                truncated=False,
            )
        raise AssertionError(f"unexpected child URL: {url}")

    report = resolve_exact_lot_child_links(
        verification,
        aggregate_fetcher=parent_fetcher,
        child_page_fetcher=child_fetcher,
        max_parent_fetches=2,
        max_child_page_fetches=5,
    )

    assert parent_calls == [parent]
    assert child_calls == [exact_child, broad_child]
    assert report["status"] == "SUCCESS"
    assert report["provider"] == "exa"
    assert report["eligible_parent_count"] == 1
    assert report["parent_fetches_attempted"] == 1
    assert report["candidate_child_url_count"] == 2
    assert report["child_page_fetches_attempted"] == 2
    assert report["exact_lot_candidate_count"] == 1
    assert report["exact_lots"][0]["url"] == exact_child
    assert report["exact_lots"][0]["parent_url"] == parent
    assert report["exact_lots"][0]["evidence"]["price_evidence"] is True
    assert report["exact_lots"][0]["evidence"]["quantity_evidence"] is True
    assert report["exact_lots"][0]["evidence"]["direct_sale_evidence"] is True
    assert report["exact_lots"][0]["evidence"]["project_domain"] == CLOTHING_INVENTORY
    assert report["child_results"][1]["classification"] == "ACTIVE_STOCK_SIGNAL"
    assert report["child_results"][1]["exact_lot_accepted"] is False
    assert report["production_mutation"] is False
    assert report["automatic_contact"] is False
    assert report["automatic_purchase"] is False


def test_resolver_blocks_non_symmetric_or_non_clothing_input() -> None:
    report = resolve_exact_lot_child_links(
        {
            "status": "SUCCESS",
            "provider": "brave",
            "shadow_only": True,
            "symmetric_provider_verification": False,
            "commercial_specificity_gate_enforced": True,
            "project_domain_gate_enforced": True,
            "required_project_domain": CLOTHING_INVENTORY,
            "verified_pages": [],
        }
    )

    assert report["status"] == "BLOCKED_INPUT"
    assert report["block_reason"] == "INPUT_NOT_SYMMETRIC_PROVIDER_VERIFICATION"
    assert report["exact_lots"] == []
