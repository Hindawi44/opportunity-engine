from __future__ import annotations

from opportunity_engine.discovery.exa_search import EXA_HIGHLIGHT_DESCRIPTION_PREFIX
from opportunity_engine.discovery import provider_unique_page_verification as verification
from opportunity_engine.discovery.exa_shadow_page_verification import (
    EXACT_LOT_CANDIDATE,
    FETCH_FAILED,
)
from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY


URL = "https://merkandi.no/products/restparti-klaer-500-stk/1572644"
NUMERIC_PRODUCT_URL = (
    "https://merkandi.no/products/klaer-og-fottoy-eksport-miks-bare-1-99/480248"
)


def _benchmark(
    description: str,
    *,
    url: str = URL,
    title: str = "Restparti klær 500 stk til salgs",
) -> dict:
    return {
        "schema_version": "search-experiment-benchmark-1.0",
        "status": "SUCCESS",
        "shadow_only": True,
        "project_domain": CLOTHING_INVENTORY,
        "project_domain_gate_enforced": True,
        "markets": ["NO"],
        "market_results": [
            {
                "market_code": "NO",
                "query": "Norge restlager klær grossist parti",
                "exa": {
                    "results": [
                        {
                            "title": title,
                            "url": url,
                            "domain": "merkandi.no",
                            "description": description,
                            "provider": "Exa",
                        }
                    ]
                },
                "brave": {"results": []},
            }
        ],
    }


def _failed(status_code: int):
    def fetcher(url: str) -> PageFetchResult:
        return PageFetchResult(
            requested_url=url,
            final_url=url,
            ok=False,
            status_code=status_code,
            title="",
            text="",
            error=f"HTTP_{status_code}",
        )

    return fetcher


def test_http_403_highlight_shadow_detects_strict_shape_without_promoting_it() -> None:
    description = EXA_HIGHLIGHT_DESCRIPTION_PREFIX + (
        "Restparti klær til salgs for grossister. Lager med 500 stk. "
        "Pris 2,10 EUR per stk. Tilgjengelig for kjøp."
    )
    report = verification.verify_provider_unique_pages(
        _benchmark(description),
        provider="exa",
        page_fetcher=_failed(403),
        max_page_fetches=1,
    )

    assert report["exact_lot_candidate_count"] == 0
    row = report["verified_pages"][0]
    assert row["classification"] == FETCH_FAILED
    assert row["fetch_ok"] is False
    assert row["tool_learning_useful"] is False
    assert row["evidence"] == {}
    assert row["provider_extractive_403_shadow_used"] is True
    assert row["provider_extractive_403_shadow_classification"] == EXACT_LOT_CANDIDATE
    shadow_evidence = row["provider_extractive_403_shadow_evidence"]
    assert shadow_evidence["project_domain"] == CLOTHING_INVENTORY
    assert shadow_evidence["inventory_evidence"] is True
    assert shadow_evidence["direct_sale_evidence"] is True
    assert shadow_evidence["price_evidence"] is True
    assert shadow_evidence["quantity_evidence"] is True
    assert shadow_evidence["item_specific_url_evidence"] is True

    shadow = report["provider_extractive_403_shadow"]
    assert shadow["status"] == "SUCCESS"
    assert shadow["http_403_row_count"] == 1
    assert shadow["highlight_evidence_available_count"] == 1
    assert shadow["shadow_exact_lot_candidate_count"] == 1
    assert shadow["search_requests_added"] == 0
    assert shadow["direct_page_fetches_added"] == 0
    assert shadow["exact_lot_decision_changes"] == 0
    assert shadow["tool_learning_decision_changes"] == 0
    assert shadow["qualification_evidence"] is False


def test_numeric_product_detail_route_recovers_shadow_url_specificity_only() -> None:
    description = EXA_HIGHLIGHT_DESCRIPTION_PREFIX + (
        "Restlager klær og sko til salgs for grossister. Lager 600 stk. "
        "Pris 1,99 EUR per stk. Tilgjengelig for kjøp."
    )
    report = verification.verify_provider_unique_pages(
        _benchmark(
            description,
            url=NUMERIC_PRODUCT_URL,
            title="Klær og sko eksport miks kun 1,99 EUR",
        ),
        provider="exa",
        page_fetcher=_failed(403),
        max_page_fetches=1,
    )

    assert report["exact_lot_candidate_count"] == 0
    row = report["verified_pages"][0]
    assert row["classification"] == FETCH_FAILED
    assert row["tool_learning_useful"] is False
    assert row["provider_extractive_403_shadow_classification"] == EXACT_LOT_CANDIDATE
    assert row["provider_extractive_403_shadow_numeric_product_detail_recovery"] is True
    evidence = row["provider_extractive_403_shadow_evidence"]
    assert evidence["item_specific_url_evidence"] is True
    assert (
        evidence["provider_extractive_403_shadow_item_specific_url_recovery"]
        == "NUMERIC_PRODUCT_DETAIL_ROUTE"
    )
    shadow = report["provider_extractive_403_shadow"]
    assert shadow["numeric_product_detail_url_recovery_count"] == 1
    assert shadow["shadow_exact_lot_candidate_count"] == 1
    assert shadow["exact_lot_decision_changes"] == 0
    assert shadow["qualification_evidence"] is False


def test_numeric_product_detail_recovery_rejects_generic_slug_and_year_like_id() -> None:
    description = EXA_HIGHLIGHT_DESCRIPTION_PREFIX + (
        "Restlager klær til salgs. Lager 500 stk. Pris 2,10 EUR per stk."
    )
    urls = (
        "https://example.no/products/klaer/480248",
        "https://example.no/products/klaer-og-sko-restlager/2026",
    )
    for url in urls:
        report = verification.verify_provider_unique_pages(
            _benchmark(description, url=url),
            provider="exa",
            page_fetcher=_failed(403),
            max_page_fetches=1,
        )
        row = report["verified_pages"][0]
        assert row["classification"] == FETCH_FAILED
        assert row["provider_extractive_403_shadow_numeric_product_detail_recovery"] is False
        assert report["provider_extractive_403_shadow"][
            "numeric_product_detail_url_recovery_count"
        ] == 0


def test_ordinary_untagged_description_cannot_enter_403_shadow() -> None:
    report = verification.verify_provider_unique_pages(
        _benchmark("Restparti klær til salgs. 500 stk. Pris 2,10 EUR."),
        provider="exa",
        page_fetcher=_failed(403),
        max_page_fetches=1,
    )

    row = report["verified_pages"][0]
    assert row["classification"] == FETCH_FAILED
    assert row["provider_extractive_403_shadow_used"] is False
    assert row["provider_extractive_403_shadow_classification"] is None
    assert report["provider_extractive_403_shadow"]["highlight_evidence_available_count"] == 0
    assert report["provider_extractive_403_shadow"]["shadow_exact_lot_candidate_count"] == 0


def test_tagged_highlight_is_not_used_for_non_403_fetch_failure() -> None:
    description = EXA_HIGHLIGHT_DESCRIPTION_PREFIX + (
        "Restparti klær til salgs. Lager 500 stk. Pris 2,10 EUR."
    )
    report = verification.verify_provider_unique_pages(
        _benchmark(description),
        provider="exa",
        page_fetcher=_failed(404),
        max_page_fetches=1,
    )

    row = report["verified_pages"][0]
    assert row["classification"] == FETCH_FAILED
    assert row["provider_extractive_403_shadow_used"] is False
    assert report["provider_extractive_403_shadow"]["http_403_row_count"] == 0
    assert report["provider_extractive_403_shadow"]["highlight_evidence_available_count"] == 0
