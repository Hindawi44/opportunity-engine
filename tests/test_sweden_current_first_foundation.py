from datetime import datetime
from zoneinfo import ZoneInfo

from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.sweden_current_first import (
    BLINTO_CURRENT_QUERY_IDS,
    KLARAVIK_CURRENT_QUERY_IDS,
    BlintoCurrentFirstPrefetchedSearchProvider,
    KlaravikCurrentFirstPrefetchedSearchProvider,
    build_blinto_current_first_queries,
    build_klaravik_current_first_queries,
)


class QueryProvider:
    name = "query-provider"

    def __init__(self, hits_by_query):
        self.hits_by_query = hits_by_query
        self.calls = []

    def search(self, query: str, *, count: int = 10):
        self.calls.append((query, count))
        return tuple(self.hits_by_query.get(query, ()))[:count]


def _now():
    return datetime(2026, 8, 17, 12, 0, tzinfo=ZoneInfo("Europe/Stockholm"))


def _blinto_hit(object_id: int, occurrence_id: int, title="Parti med arbetskläder"):
    return SearchHit(
        title=title,
        url=f"https://www.blinto.se/auction/Blaklader-{object_id}-{occurrence_id}/",
        description="Parti med arbetskläder, 38 par byxor. Högsta bud visas.",
        provider="Static",
    )


def _klaravik_hit(slug: str, title="Kläder och skor, parti"):
    return SearchHit(
        title=title,
        url=f"https://www.klaravik.se/auktion/produkt/{slug}/",
        description="Parti med nya kläder och skor, cirka 50 plagg. Nuvarande bud visas.",
        provider="Static",
    )


def test_current_first_builders_keep_eight_request_budget_and_prepend_current_queries():
    blinto = build_blinto_current_first_queries(8, now=_now())
    klaravik = build_klaravik_current_first_queries(8, now=_now())

    assert len(blinto) == 8
    assert len(klaravik) == 8
    assert {query.query_id for query in blinto[:2]} == BLINTO_CURRENT_QUERY_IDS
    assert {query.query_id for query in klaravik[:2]} == KLARAVIK_CURRENT_QUERY_IDS
    assert all("2026-08" in query.query for query in blinto[:2])
    assert all("2026-08" in query.query for query in klaravik[:2])


def test_blinto_current_occurrence_gets_priority_without_extra_requests():
    queries = build_blinto_current_first_queries(8, now=_now())
    current = _blinto_hit(178629, 99002)
    stale_generic = _blinto_hit(205021, 116089, title="Parti med kläder och skor")
    raw = QueryProvider(
        {
            queries[0].query: [current],
            queries[2].query: [stale_generic],
        }
    )
    provider = BlintoCurrentFirstPrefetchedSearchProvider(
        raw,
        queries=queries,
        request_budget=8,
    )

    assert provider.search(queries[0].query, count=10) == (current,)
    assert provider.search(queries[2].query, count=10) == ()
    diagnostics = provider.diagnostics()

    assert len(raw.calls) == 8
    assert diagnostics["requests_made"] == 8
    assert diagnostics["current_window_priority_applied"] is True
    assert diagnostics["current_window_identities"] == ["99002"]
    assert diagnostics["generic_fallback_deferred_count"] == 1
    assert diagnostics["current_window_is_active_proof"] is False


def test_blinto_relisting_identity_uses_occurrence_not_object_id():
    queries = build_blinto_current_first_queries(2, now=_now())
    first_occurrence = _blinto_hit(178629, 99002)
    second_occurrence = _blinto_hit(178629, 99003)
    raw = QueryProvider(
        {
            queries[0].query: [first_occurrence],
            queries[1].query: [second_occurrence],
        }
    )
    provider = BlintoCurrentFirstPrefetchedSearchProvider(
        raw,
        queries=queries,
        request_budget=2,
    )

    provider.search(queries[0].query, count=10)
    diagnostics = provider.diagnostics()

    assert diagnostics["current_window_identities"] == ["99002", "99003"]
    assert diagnostics["current_first_duplicate_count"] == 0
    assert diagnostics["accepted_object_ids"] == ["178629"]
    assert diagnostics["accepted_occurrence_ids"] == ["99002", "99003"]


def test_klaravik_current_slug_gets_priority_without_extra_requests():
    queries = build_klaravik_current_first_queries(8, now=_now())
    current = _klaravik_hit("3100001-klader-och-skor-parti")
    stale_generic = _klaravik_hit("848318-klader-och-skor-parti")
    raw = QueryProvider(
        {
            queries[0].query: [current],
            queries[2].query: [stale_generic],
        }
    )
    provider = KlaravikCurrentFirstPrefetchedSearchProvider(
        raw,
        queries=queries,
        request_budget=8,
    )

    assert provider.search(queries[0].query, count=10) == (current,)
    assert provider.search(queries[2].query, count=10) == ()
    diagnostics = provider.diagnostics()

    assert len(raw.calls) == 8
    assert diagnostics["requests_made"] == 8
    assert diagnostics["current_window_priority_applied"] is True
    assert diagnostics["current_window_identities"] == [
        "3100001-klader-och-skor-parti"
    ]
    assert diagnostics["generic_fallback_deferred_count"] == 1
    assert diagnostics["current_window_is_active_proof"] is False


def test_generic_fallback_remains_available_when_current_window_is_empty():
    queries = build_klaravik_current_first_queries(8, now=_now())
    fallback = _klaravik_hit("848318-klader-och-skor-parti")
    raw = QueryProvider({queries[2].query: [fallback]})
    provider = KlaravikCurrentFirstPrefetchedSearchProvider(
        raw,
        queries=queries,
        request_budget=8,
    )

    assert provider.search(queries[0].query, count=10) == ()
    assert provider.search(queries[2].query, count=10) == (fallback,)
    diagnostics = provider.diagnostics()

    assert len(raw.calls) == 8
    assert diagnostics["current_window_priority_applied"] is False
    assert diagnostics["generic_fallback_deferred_count"] == 0


def test_same_current_identity_is_exposed_only_once_across_query_pack():
    queries = build_klaravik_current_first_queries(2, now=_now())
    same = _klaravik_hit("3100001-klader-och-skor-parti")
    raw = QueryProvider({queries[0].query: [same], queries[1].query: [same]})
    provider = KlaravikCurrentFirstPrefetchedSearchProvider(
        raw,
        queries=queries,
        request_budget=2,
    )

    assert provider.search(queries[0].query, count=10) == (same,)
    assert provider.search(queries[1].query, count=10) == ()
    assert provider.diagnostics()["current_first_duplicate_count"] == 1
