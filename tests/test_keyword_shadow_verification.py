from __future__ import annotations

from opportunity_engine.discovery.keyword_shadow_verification import (
    MAX_PAGE_FETCHES,
    RESULTS_PER_KEYWORD,
    SHADOW_CANDIDATES,
    PageFetchResult,
    run_keyword_shadow_verification,
)
from opportunity_engine.discovery.search_provider import SearchHit


class FakeProvider:
    name = "fake"

    def __init__(self, hits_by_query):
        self.hits_by_query = hits_by_query
        self.calls = []

    def search(self, query: str, *, count: int = 10):
        self.calls.append((query, count))
        return self.hits_by_query.get(query, [])[:count]


def _search_hit(query: str, index: int) -> SearchHit:
    return SearchHit(
        title=f"{query} lotto {index}",
        url=f"https://seller{index}.it/lotto/{index}",
        description="stock abbigliamento lotto vendita prezzo",
        provider="Fake Search",
    )


def _verified_page(url: str) -> PageFetchResult:
    return PageFetchResult(
        requested_url=url,
        final_url=url,
        ok=True,
        status_code=200,
        title="Stock abbigliamento ingrosso - liquidazione",
        text=(
            "Azienda Srl con Partita IVA. B2B ingrosso stock abbigliamento, "
            "lotti da liquidazione fallimentare. Prezzi EUR, 500 pezzi disponibili. "
            "Italia Milano pronta consegna."
        ),
    )


def test_protocol_is_frozen_to_three_survivors_and_fifteen_pages():
    assert [candidate.query for candidate in SHADOW_CANDIDATES] == [
        "lotti fallimentari abbigliamento",
        "vendita stock abbigliamento magazzino",
        "stock abbigliamento ingrosso",
    ]
    assert RESULTS_PER_KEYWORD == 5
    assert MAX_PAGE_FETCHES == 15


def test_verified_page_evidence_uses_same_score_and_can_promote():
    hits_by_query = {
        candidate.query: [_search_hit(candidate.query, i) for i in range(1, 6)]
        for candidate in SHADOW_CANDIDATES
    }
    provider = FakeProvider(hits_by_query)

    report = run_keyword_shadow_verification(
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, key, freshness: provider,
        page_fetcher=_verified_page,
    )

    assert report["status"] == "SUCCESS"
    assert report["same_v1_score_weights"] is True
    assert report["same_v1_decision_thresholds"] is True
    assert report["stage1_query_count"] == 3
    assert report["page_fetches_attempted"] == 15
    assert report["page_fetches_succeeded"] == 15
    assert report["promote_count"] == 3
    assert all(item["score"] >= 80 for item in report["ranking"])
    assert all(item["verified_page_coverage"] == 1.0 for item in report["ranking"])
    assert provider.calls == [(candidate.query, 5) for candidate in SHADOW_CANDIDATES]


def test_failed_page_fetches_do_not_inherit_search_snippet_evidence():
    hits_by_query = {
        candidate.query: [_search_hit(candidate.query, i) for i in range(1, 6)]
        for candidate in SHADOW_CANDIDATES
    }
    provider = FakeProvider(hits_by_query)

    def fail(url: str) -> PageFetchResult:
        return PageFetchResult(
            requested_url=url,
            final_url=url,
            ok=False,
            status_code=403,
            title="",
            text="",
            error="HTTP_403",
        )

    report = run_keyword_shadow_verification(
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, key, freshness: provider,
        page_fetcher=fail,
    )

    assert report["page_fetches_succeeded"] == 0
    assert report["promote_count"] == 0
    assert report["shadow_count"] == 0
    assert report["reject_count"] == 3
    assert all(item["verified_page_coverage"] == 0.0 for item in report["ranking"])
    assert all(item["score"] < 60 for item in report["ranking"])


def test_missing_api_key_blocks_before_page_fetch():
    calls = []

    def page_fetcher(url: str) -> PageFetchResult:
        calls.append(url)
        return _verified_page(url)

    report = run_keyword_shadow_verification(environment={}, page_fetcher=page_fetcher)

    assert report["status"] == "BLOCKED_CONFIGURATION"
    assert report["page_fetches_attempted"] == 0
    assert calls == []
