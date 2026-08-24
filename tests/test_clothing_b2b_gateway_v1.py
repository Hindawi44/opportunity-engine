from __future__ import annotations

from opportunity_engine.discovery.exa_shadow_page_verification import (
    ACTIVE_STOCK_SIGNAL,
    SOURCE_INTELLIGENCE_ONLY,
    UNPROVEN_PAGE,
)
from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult
from opportunity_engine.discovery.provider_unique_page_verification import verify_provider_unique_pages
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY, FABRIC_PROCUREMENT


def _benchmark(url: str, title: str = "Clothing wholesale stock") -> dict:
    return {
        "schema_version": "test-benchmark-1.0",
        "status": "SUCCESS",
        "shadow_only": True,
        "project_domain": CLOTHING_INVENTORY,
        "project_domain_gate_enforced": True,
        "markets": ["FR"],
        "market_results": [
            {
                "market_code": "FR",
                "query": "France déstockage vêtements grossiste stock lot",
                "exa": {
                    "results": [
                        {
                            "title": title,
                            "url": url,
                            "domain": "example.fr",
                            "description": title,
                        }
                    ]
                },
                "brave": {"results": []},
            }
        ],
    }


def _fetch(url: str, title: str, text: str) -> PageFetchResult:
    return PageFetchResult(
        requested_url=url,
        final_url=url,
        ok=True,
        status_code=200,
        title=title,
        text=text,
    )


def test_b2b_clothing_stock_with_price_or_quantity_becomes_navigation_gateway_only() -> None:
    url = "https://example.fr/"
    report = verify_provider_unique_pages(
        _benchmark(url, "Grossiste vêtements déstockage"),
        provider="exa",
        page_fetcher=lambda _: _fetch(
            url,
            "Grossiste vêtements déstockage",
            "Stock de vêtements en déstockage pour grossistes. 240 pièces. Prix 5 EUR.",
        ),
        max_page_fetches=5,
    )

    [page] = report["verified_pages"]
    assert page["classification"] == ACTIVE_STOCK_SIGNAL
    assert page["evidence"]["project_domain"] == CLOTHING_INVENTORY
    assert page["evidence"]["inventory_evidence"] is True
    assert page["evidence"]["b2b_wholesale_evidence"] is True
    assert page["evidence"]["qualified_b2b_sale_evidence"] is True
    assert page["evidence"]["direct_sale_evidence"] is True
    assert page["evidence"]["item_specific_url_evidence"] is False
    assert page["tool_learning_useful"] is False
    assert report["exact_lot_candidate_count"] == 0
    assert report["active_stock_signal_count"] == 1
    assert report["non_specific_active_filtered_count"] == 1


def test_wholesale_word_without_price_or_quantity_does_not_create_gateway() -> None:
    url = "https://example.fr/"
    report = verify_provider_unique_pages(
        _benchmark(url),
        provider="exa",
        page_fetcher=lambda _: _fetch(
            url,
            "Grossiste vêtements",
            "Stock de vêtements en déstockage pour grossistes et revendeurs.",
        ),
        max_page_fetches=5,
    )

    [page] = report["verified_pages"]
    assert page["classification"] == UNPROVEN_PAGE
    assert page["evidence"]["b2b_wholesale_evidence"] is True
    assert page["evidence"]["qualified_b2b_sale_evidence"] is False
    assert page["evidence"]["direct_sale_evidence"] is False
    assert report["active_stock_signal_count"] == 0


def test_buyer_source_page_is_not_upgraded_by_b2b_words_and_price_quantity() -> None:
    url = "https://example.fr/"
    report = verify_provider_unique_pages(
        _benchmark(url),
        provider="exa",
        page_fetcher=lambda _: _fetch(
            url,
            "Grossiste vêtements stock",
            "Nous achetons votre stock de vêtements. Grossiste B2B. 200 pièces. Prix indicatif 5 EUR.",
        ),
        max_page_fetches=5,
    )

    [page] = report["verified_pages"]
    assert page["classification"] == SOURCE_INTELLIGENCE_ONLY
    assert page["evidence"]["buyer_or_source_evidence"] is True
    assert page["evidence"]["qualified_b2b_sale_evidence"] is False
    assert report["active_stock_signal_count"] == 0


def test_fabric_b2b_page_cannot_become_clothing_gateway() -> None:
    url = "https://example.fr/"
    report = verify_provider_unique_pages(
        _benchmark(url),
        provider="exa",
        page_fetcher=lambda _: _fetch(
            url,
            "Grossiste tissus deadstock",
            "Deadstock fabrics et tissus en gros. 200 mètres. Prix 5 EUR.",
        ),
        max_page_fetches=5,
    )

    [page] = report["verified_pages"]
    assert page["classification"] == UNPROVEN_PAGE
    assert page["evidence"]["project_domain"] == FABRIC_PROCUREMENT
    assert page["evidence"]["qualified_b2b_sale_evidence"] is False
    assert report["active_stock_signal_count"] == 0
