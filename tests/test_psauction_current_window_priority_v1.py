from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.sweden_psauction import build_psauction_clothing_queries
from opportunity_engine.discovery.sweden_psauction_prefetch import (
    PSAuctionPrefetchedSearchProvider,
)


NOW = datetime(2026, 8, 17, 12, 0, tzinfo=ZoneInfo("Europe/Stockholm"))


class FakeProvider:
    name = "fake"

    def __init__(self, hits_by_query):
        self.hits_by_query = hits_by_query
        self.calls = defaultdict(int)

    def search(self, query: str, *, count: int = 10):
        self.calls[query] += 1
        return tuple(self.hits_by_query.get(query, ()))[:count]


def _hit(item_id: str, *, ended: bool = False) -> SearchHit:
    status = "Auktionen är avslutad. Såld." if ended else "Auktionen avslutas 2026-08-30 16:00."
    return SearchHit(
        title="Parti med arbetskläder",
        url=f"https://psauction.se/item/view/{item_id}/parti-med-arbetsklader",
        description=f"Lagerparti med arbetskläder. {status}",
        provider="fixture",
    )


def test_current_window_candidate_defers_unrelated_generic_fallback() -> None:
    queries = build_psauction_clothing_queries(3, now=NOW)
    current = _hit("900001")
    generic = _hit("900002")
    fake = FakeProvider({
        queries[0].query: (current,),
        queries[2].query: (generic,),
    })
    provider = PSAuctionPrefetchedSearchProvider(
        fake,
        queries=queries,
        request_budget=3,
    )

    assert [hit.url for hit in provider.search(queries[0].query)] == [current.url]
    assert provider.search(queries[2].query) == ()

    diagnostics = provider.diagnostics()
    assert diagnostics["requests_made"] == 3
    assert diagnostics["current_window_item_ids"] == ["900001"]
    assert diagnostics["current_window_priority_applied"] is True
    assert diagnostics["generic_fallback_deferred_count"] == 1
    assert diagnostics["current_window_is_active_proof"] is False


def test_global_ended_evidence_vetoes_current_window_priority() -> None:
    queries = build_psauction_clothing_queries(3, now=NOW)
    same_live_snippet = _hit("900001")
    same_ended_snippet = _hit("900001", ended=True)
    generic = _hit("900002")
    fake = FakeProvider({
        queries[0].query: (same_live_snippet,),
        queries[2].query: (same_ended_snippet, generic),
    })
    provider = PSAuctionPrefetchedSearchProvider(
        fake,
        queries=queries,
        request_budget=3,
    )

    assert provider.search(queries[0].query) == ()
    generic_hits = provider.search(queries[2].query)
    assert [hit.url for hit in generic_hits] == [generic.url]

    diagnostics = provider.diagnostics()
    assert diagnostics["historical_item_ids"] == ["900001"]
    assert diagnostics["current_window_item_ids"] == []
    assert diagnostics["current_window_priority_applied"] is False
    assert diagnostics["generic_fallback_deferred_count"] == 0


def test_generic_fallback_remains_when_current_window_yields_nothing() -> None:
    queries = build_psauction_clothing_queries(3, now=NOW)
    generic = _hit("900003")
    fake = FakeProvider({queries[2].query: (generic,)})
    provider = PSAuctionPrefetchedSearchProvider(
        fake,
        queries=queries,
        request_budget=3,
    )

    provider.search(queries[0].query)
    assert [hit.url for hit in provider.search(queries[2].query)] == [generic.url]

    diagnostics = provider.diagnostics()
    assert diagnostics["requests_made"] == 3
    assert diagnostics["current_window_candidate_count"] == 0
    assert diagnostics["current_window_priority_applied"] is False
    assert diagnostics["accepted_item_ids"] == ["900003"]


def test_current_item_is_deduplicated_across_current_and_generic_queries() -> None:
    queries = build_psauction_clothing_queries(3, now=NOW)
    same = _hit("900004")
    fake = FakeProvider({
        queries[0].query: (same,),
        queries[2].query: (same,),
    })
    provider = PSAuctionPrefetchedSearchProvider(
        fake,
        queries=queries,
        request_budget=3,
    )

    first = provider.search(queries[0].query)
    assert len(first) == 1
    assert provider.search(queries[2].query) == ()

    diagnostics = provider.diagnostics()
    assert diagnostics["accepted_item_ids"] == ["900004"]
    assert diagnostics["accepted_urls"] == [first[0].url]
    assert diagnostics["requests_made"] == 3
    assert diagnostics["request_budget"] == 3
