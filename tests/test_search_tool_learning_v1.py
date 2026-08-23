from __future__ import annotations

from opportunity_engine.discovery.exa_shadow_page_verification import (
    EXACT_LOT_CANDIDATE,
    OUT_OF_DOMAIN,
    verify_provider_unique_pages,
)
from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult
from opportunity_engine.discovery.search_tool_learning import build_search_tool_learning_scorecard
from scripts.run_exa_brave_shadow_benchmark import MARKET_QUERIES


def _benchmark() -> dict:
    return {
        "schema_version": "exa-brave-shadow-benchmark-1.1",
        "status": "SUCCESS",
        "shadow_only": True,
        "project_domain": "CLOTHING_INVENTORY",
        "project_domain_gate_enforced": True,
        "markets": ["NO"],
        "market_results": [
            {
                "market_code": "NO",
                "query": MARKET_QUERIES["NO"],
                "exa": {
                    "results": [
                        {
                            "title": "Parti med arbeidsjakker",
                            "url": "https://exa.example.no/lot/44",
                            "domain": "exa.example.no",
                            "description": "480 arbeidsjakker til salgs",
                        },
                        {
                            "title": "Shared clothing lot",
                            "url": "https://shared.example.no/lot/1",
                            "domain": "shared.example.no",
                            "description": "klær",
                        },
                    ]
                },
                "brave": {
                    "results": [
                        {
                            "title": "Restparti granitt",
                            "url": "https://brave.example.no/item/99",
                            "domain": "brave.example.no",
                            "description": "poolkantsten i granitt",
                        },
                        {
                            "title": "Shared clothing lot",
                            "url": "https://shared.example.no/lot/1",
                            "domain": "shared.example.no",
                            "description": "klær",
                        },
                    ]
                },
            }
        ],
    }


def _page(url: str) -> PageFetchResult:
    if url == "https://exa.example.no/lot/44":
        text = "Parti med arbeidsjakker selges. 480 stk. Pris 12 000 NOK. Klær på lager."
    elif url == "https://brave.example.no/item/99":
        text = "Restparti poolkantsten i grå granitt selges. 34 stk. Pris 9 281 SEK."
    else:
        raise AssertionError(f"unexpected URL: {url}")
    return PageFetchResult(
        requested_url=url,
        final_url=url,
        ok=True,
        status_code=200,
        title="Verified page",
        text=text,
    )


def test_benchmark_queries_are_clothing_domain_anchored_in_every_market() -> None:
    expected = {
        "NO": ("klær", "mote"),
        "SE": ("kläder", "mode"),
        "DE": ("kleidung", "mode"),
        "FR": ("vêtements", "mode"),
        "IT": ("abbigliamento", "moda"),
        "NL": ("kleding", "mode"),
    }
    for market, query in MARKET_QUERIES.items():
        folded = query.casefold()
        assert any(anchor in folded for anchor in expected[market])


def test_provider_unique_verification_is_symmetric_and_domain_gated() -> None:
    benchmark = _benchmark()
    exa = verify_provider_unique_pages(
        benchmark,
        provider="exa",
        page_fetcher=_page,
        max_page_fetches=5,
    )
    brave = verify_provider_unique_pages(
        benchmark,
        provider="brave",
        page_fetcher=_page,
        max_page_fetches=5,
    )

    assert exa["provider"] == "exa"
    assert brave["provider"] == "brave"
    assert exa["provider_unique_url_count"] == 1
    assert brave["provider_unique_url_count"] == 1
    assert exa["verified_pages"][0]["classification"] == EXACT_LOT_CANDIDATE
    assert brave["verified_pages"][0]["classification"] == OUT_OF_DOMAIN
    assert exa["useful_clothing_signal_count"] == 1
    assert brave["useful_clothing_signal_count"] == 0
    assert exa["project_domain_gate_enforced"] is True
    assert brave["project_domain_gate_enforced"] is True


def test_tool_learning_prefers_verified_in_domain_yield_not_raw_hit_count() -> None:
    benchmark = _benchmark()
    exa = verify_provider_unique_pages(
        benchmark,
        provider="exa",
        page_fetcher=_page,
        max_page_fetches=5,
    )
    brave = verify_provider_unique_pages(
        benchmark,
        provider="brave",
        page_fetcher=_page,
        max_page_fetches=5,
    )

    scorecard = build_search_tool_learning_scorecard(
        exa,
        brave,
        min_successful_pages_per_provider=1,
    )

    assert scorecard["decision"] == "EXA_LEADS"
    assert scorecard["metrics"]["exa"]["useful_clothing_signal_count"] == 1
    assert scorecard["metrics"]["brave"]["useful_clothing_signal_count"] == 0
    assert scorecard["metrics"]["exa"]["out_of_domain_count"] == 0
    assert scorecard["metrics"]["brave"]["out_of_domain_count"] == 1
    assert scorecard["automatic_provider_activation"] is False
    assert scorecard["production_mutation"] is False


def test_tool_learning_fails_closed_without_symmetric_verified_sample() -> None:
    benchmark = _benchmark()
    exa = verify_provider_unique_pages(
        benchmark,
        provider="exa",
        page_fetcher=_page,
        max_page_fetches=5,
    )
    brave = verify_provider_unique_pages(
        benchmark,
        provider="brave",
        page_fetcher=_page,
        max_page_fetches=5,
    )
    brave["page_fetches_succeeded"] = 0

    scorecard = build_search_tool_learning_scorecard(
        exa,
        brave,
        min_successful_pages_per_provider=1,
    )

    assert scorecard["decision"] == "INSUFFICIENT_EVIDENCE"
    assert "BRAVE_VERIFIED_SAMPLE_TOO_SMALL" in scorecard["blocking_reasons"]
    assert scorecard["automatic_provider_activation"] is False
