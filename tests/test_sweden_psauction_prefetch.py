from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.sweden_psauction import (
    build_psauction_clothing_queries,
)
from opportunity_engine.discovery.sweden_psauction_prefetch import (
    PSAuctionPrefetchedSearchProvider,
)


class QueryProvider:
    name = "query-provider"

    def __init__(self, hits_by_query):
        self.hits_by_query = hits_by_query
        self.calls = []

    def search(self, query: str, *, count: int = 10):
        self.calls.append((query, count))
        return self.hits_by_query.get(query, [])[:count]


def _open_hit() -> SearchHit:
    return SearchHit(
        title="Parti med kläder, ca 50 plagg",
        url="https://psauction.se/item/view/580782/parti-med-klader",
        description="Parti med cirka 50 plagg från konkursbo.",
        provider="Static",
    )


def _ended_hit_same_id() -> SearchHit:
    return SearchHit(
        title="Parti med kläder, ca 50 plagg",
        url="https://psauction.se/item/view/580782/parti-med-klader",
        description="Avyttring · Såld · Avslutad · Parti med cirka 50 plagg.",
        provider="Static",
    )


def _unresolved_hit() -> SearchHit:
    return SearchHit(
        title="Parti med damkläder, ca 1300 plagg",
        url="https://psauction.se/item/view/670524/parti-med-damklader",
        description="Butikslager med cirka 1300 plagg.",
        provider="Static",
    )


def test_prefetch_removes_item_globally_when_any_query_marks_it_ended():
    first, second = build_psauction_clothing_queries(2)
    raw = QueryProvider(
        {
            first.query: [_open_hit(), _unresolved_hit()],
            second.query: [_ended_hit_same_id()],
        }
    )
    provider = PSAuctionPrefetchedSearchProvider(
        raw,
        queries=(first, second),
        request_budget=2,
    )

    first_hits = provider.search(first.query, count=10)
    second_hits = provider.search(second.query, count=10)
    diagnostics = provider.diagnostics()

    assert [hit.url for hit in first_hits] == [_unresolved_hit().url]
    assert second_hits == ()
    assert raw.calls == [(first.query, 10), (second.query, 10)]
    assert diagnostics["prefetched"] is True
    assert diagnostics["historical_item_ids"] == ["580782"]
    assert diagnostics["accepted_item_ids"] == ["670524"]
    assert diagnostics["requests_made"] == 2


def test_prefetch_reuses_cached_queries_without_extra_provider_calls():
    first, second = build_psauction_clothing_queries(2)
    raw = QueryProvider({first.query: [_unresolved_hit()], second.query: []})
    provider = PSAuctionPrefetchedSearchProvider(
        raw,
        queries=(first, second),
        request_budget=2,
    )

    provider.search(first.query, count=10)
    provider.search(second.query, count=10)
    provider.search(first.query, count=10)

    assert len(raw.calls) == 2


def test_prefetch_rejects_count_change_after_cache_creation():
    first = build_psauction_clothing_queries(1)[0]
    provider = PSAuctionPrefetchedSearchProvider(
        QueryProvider({first.query: [_unresolved_hit()]}),
        queries=(first,),
        request_budget=1,
    )

    provider.search(first.query, count=10)
    try:
        provider.search(first.query, count=5)
    except ValueError as exc:
        assert "count must remain stable" in str(exc)
    else:
        raise AssertionError("count changes must fail closed")
