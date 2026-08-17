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


def test_current_first_builders_keep_eight_request_budget_and_use_retail_liquidation_language():
    blinto = build_blinto_current_first_queries(8, now=_now())
    klaravik = build_klaravik_current_first_queries(8, now=_now())

    assert len(blinto) == 8
    assert len(klaravik) == 8
    assert {query.query_id for query in blinto[:2]} == BLINTO_CURRENT_QUERY_IDS
    assert {query.query_id for query in klaravik[:2]} == KLARAVIK_CURRENT_QUERY_IDS

    for query in (*blinto[:2], *klaravik[:2]):
        text = query.query.casefold()
        assert "augusti 2026" in text
        assert "arbetskläder" not in text
        assert "auktionen avslutas" not in text
        assert "nuvarande bud" not in text

    assert "klädbutik" in blinto[0].query
    assert "modebutik" in blinto[0].query
    assert "butikslager" in blinto[0].query
    assert "utförsäljning" in blinto[1].query
    assert "avveckling" in blinto[1].query
    assert "konkurs" in blinto[1].query
    assert "klädbutik" in klaravik[0].query
    assert "butikslager" in klaravik[0].query
    assert "restlager" in klaravik[1].query


def test_blinto_current_occurrence_gets_priority_but_generic_fallback_is_preserved():
    queries = build_blinto_current_first_queries(8, now=_now())
    current = _blinto_hit(178629, 99002)
    generic = _blinto_hit(205021, 116089, title="Parti med kläder och skor")
    raw = QueryProvider(
        {
            queries[0].query: [current],
            queries[2].query: [generic],
        }
    )
    provider = BlintoCurrentFirstPrefetchedSearchProvider(
        raw,
        queries=queries,
        request_budget=8,
    )

    current_hits = provider.search(queries[0].query, count=10)
    assert len(current_hits) == 1
    assert current_hits[0].url == "https://blinto.se/auction/Blaklader-178629-99002"

    fallback_hits = provider.search(queries[2].query, count=10)
    assert len(fallback_hits) == 1
    assert fallback_hits[0].url == "https://blinto.se/auction/Blaklader-205021-116089"

    diagnostics = provider.diagnostics()
    assert len(raw.calls) == 8
    assert diagnostics["requests_made"] == 8
    assert diagnostics["current_first_policy"] == "SWEDEN_CURRENT_FIRST_V2_VERIFY_BEFORE_SUPPRESS"
    assert diagnostics["current_window_priority_applied"] is True
    assert diagnostics["current_window_identities"] == ["99002"]
    assert diagnostics["generic_fallback_deferred_count"] == 0
    assert diagnostics["generic_fallback_preserved_count"] == 1
    assert diagnostics["current_window_is_active_proof"] is False
    assert diagnostics["fallback_suppression_requires_verified_active"] is True


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


def test_klaravik_current_slug_gets_priority_but_generic_fallback_is_preserved():
    queries = build_klaravik_current_first_queries(8, now=_now())
    current = _klaravik_hit("3100001-klader-och-skor-parti")
    generic = _klaravik_hit("848318-klader-och-skor-parti")
    raw = QueryProvider(
        {
            queries[0].query: [current],
            queries[2].query: [generic],
        }
    )
    provider = KlaravikCurrentFirstPrefetchedSearchProvider(
        raw,
        queries=queries,
        request_budget=8,
    )

    current_hits = provider.search(queries[0].query, count=10)
    assert len(current_hits) == 1
    assert current_hits[0].url == (
        "https://klaravik.se/auktion/produkt/3100001-klader-och-skor-parti"
    )

    fallback_hits = provider.search(queries[2].query, count=10)
    assert len(fallback_hits) == 1
    assert fallback_hits[0].url == (
        "https://klaravik.se/auktion/produkt/848318-klader-och-skor-parti"
    )

    diagnostics = provider.diagnostics()
    assert len(raw.calls) == 8
    assert diagnostics["requests_made"] == 8
    assert diagnostics["current_window_priority_applied"] is True
    assert diagnostics["current_window_identities"] == [
        "3100001-klader-och-skor-parti"
    ]
    assert diagnostics["generic_fallback_deferred_count"] == 0
    assert diagnostics["generic_fallback_preserved_count"] == 1
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
    fallback_hits = provider.search(queries[2].query, count=10)
    assert len(fallback_hits) == 1
    assert fallback_hits[0].url == (
        "https://klaravik.se/auktion/produkt/848318-klader-och-skor-parti"
    )
    diagnostics = provider.diagnostics()

    assert len(raw.calls) == 8
    assert diagnostics["current_window_priority_applied"] is False
    assert diagnostics["generic_fallback_deferred_count"] == 0
    assert diagnostics["generic_fallback_preserved_count"] == 1


def test_same_identity_is_exposed_only_once_and_current_query_wins():
    queries = build_klaravik_current_first_queries(8, now=_now())
    same = _klaravik_hit("3100001-klader-och-skor-parti")
    raw = QueryProvider({queries[0].query: [same], queries[2].query: [same]})
    provider = KlaravikCurrentFirstPrefetchedSearchProvider(
        raw,
        queries=queries,
        request_budget=8,
    )

    first_hits = provider.search(queries[0].query, count=10)
    assert len(first_hits) == 1
    assert first_hits[0].url == (
        "https://klaravik.se/auktion/produkt/3100001-klader-och-skor-parti"
    )
    assert provider.search(queries[2].query, count=10) == ()
    diagnostics = provider.diagnostics()
    assert diagnostics["current_first_duplicate_count"] == 1
    assert diagnostics["generic_fallback_deferred_count"] == 0
