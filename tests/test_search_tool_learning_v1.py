from __future__ import annotations

from copy import deepcopy

from opportunity_engine.discovery.exa_shadow_page_verification import (
    ACTIVE_STOCK_SIGNAL,
    EXACT_LOT_CANDIDATE,
    OUT_OF_DOMAIN,
    UNPROVEN_PAGE,
)
from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult
from opportunity_engine.discovery.provider_unique_page_verification import verify_provider_unique_pages
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


def _single_unique_benchmark(*, provider: str, url: str, title: str) -> dict:
    other = "brave" if provider == "exa" else "exa"
    report = {
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
                provider: {
                    "results": [
                        {
                            "title": title,
                            "url": url,
                            "domain": "example.no",
                            "description": title,
                        }
                    ]
                },
                other: {"results": []},
            }
        ],
    }
    return report


def _fetched(url: str, text: str, *, title: str = "Verified page") -> PageFetchResult:
    return PageFetchResult(
        requested_url=url,
        final_url=url,
        ok=True,
        status_code=200,
        title=title,
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


def test_non_item_specific_active_signal_is_not_tool_learning_useful() -> None:
    url = "https://news.example.no/2026/08/clothing-stock-story"
    benchmark = _single_unique_benchmark(
        provider="brave",
        url=url,
        title="Klær og jakker på lager selges ut",
    )

    report = verify_provider_unique_pages(
        benchmark,
        provider="brave",
        page_fetcher=lambda _: _fetched(
            url,
            "Klær og jakker på lager selges ut. Restlager tilgjengelig nå.",
        ),
        max_page_fetches=5,
    )

    [page] = report["verified_pages"]
    assert page["classification"] == ACTIVE_STOCK_SIGNAL
    assert page["evidence"]["item_specific_url_evidence"] is False
    assert page["tool_learning_useful"] is False
    assert report["active_stock_signal_count"] == 1
    assert report["non_specific_active_filtered_count"] == 1
    assert report["useful_clothing_signal_count"] == 0


def test_out_of_domain_evidence_counts_as_noise_even_when_page_is_unproven() -> None:
    url = "https://example.no/company/granite-information"
    benchmark = _single_unique_benchmark(
        provider="exa",
        url=url,
        title="Granitt og byggematerialer lagerinformasjon",
    )

    report = verify_provider_unique_pages(
        benchmark,
        provider="exa",
        page_fetcher=lambda _: _fetched(
            url,
            "Granitt og byggematerialer på lager. Informasjon om sortiment og virksomhet.",
        ),
        max_page_fetches=5,
    )

    [page] = report["verified_pages"]
    assert page["classification"] == UNPROVEN_PAGE
    assert page["evidence"]["project_domain"] == OUT_OF_DOMAIN
    assert report["out_of_domain_count"] == 1
    assert report["useful_clothing_signal_count"] == 0


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


def test_tool_learning_cannot_declare_winner_when_both_have_zero_useful_pages() -> None:
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
    exa = deepcopy(exa)
    brave = deepcopy(brave)
    exa["useful_clothing_signal_count"] = 0
    brave["useful_clothing_signal_count"] = 0
    exa["out_of_domain_count"] = 3
    brave["out_of_domain_count"] = 0

    scorecard = build_search_tool_learning_scorecard(
        exa,
        brave,
        min_successful_pages_per_provider=1,
    )

    assert scorecard["decision"] == "INSUFFICIENT_EVIDENCE"
    assert "NO_VERIFIED_USEFUL_COMMERCIAL_PAGES" in scorecard["blocking_reasons"]
