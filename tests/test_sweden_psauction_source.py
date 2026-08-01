from __future__ import annotations

from opportunity_engine.discovery.clothing_inventory_search import (
    STRONG_LEAD_REQUIRES_VERIFICATION,
    classify_search_hit,
)
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.sweden_clothing_inventory import (
    SwedenLocalizedSearchProvider,
)
from opportunity_engine.discovery.sweden_psauction import (
    PSAUCTION_CLOTHING_QUERY_MATRIX,
    PSAuctionTargetedSearchProvider,
    build_psauction_clothing_queries,
    psauction_gate_decision,
)


class FakeProvider:
    name = "fake"

    def __init__(self, hits):
        self.hits = tuple(hits)
        self.queries = []

    def search(self, query: str, *, count: int = 10):
        self.queries.append((query, count))
        return self.hits[:count]


def _hit(**overrides):
    data = {
        "title": "Parti med kläder och accessoarer, ca 600 artiklar",
        "url": "https://psauction.se/item/view/1319712/parti-med-klader-och-accessoarer-ca-600-artiklar",
        "description": "Konkursbo. Lager med cirka 600 plagg säljs på auktion.",
        "provider": "Brave Search",
    }
    data.update(overrides)
    return SearchHit(**data)


def test_query_pack_is_bounded_and_site_restricted():
    queries = build_psauction_clothing_queries(8)

    assert len(queries) == 8
    assert all("site:psauction.se/item/view" in query.query for query in queries)
    assert all(query.asset_scope == "CLOTHING_INVENTORY" for query in queries)
    assert len({query.query for query in PSAUCTION_CLOTHING_QUERY_MATRIX}) == len(
        PSAUCTION_CLOTHING_QUERY_MATRIX
    )


def test_query_budget_fails_closed_outside_pack_bounds():
    for value in (0, len(PSAUCTION_CLOTHING_QUERY_MATRIX) + 1):
        try:
            build_psauction_clothing_queries(value)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid query budget must fail")


def test_gate_accepts_one_specific_psauction_clothing_lot():
    decision = psauction_gate_decision(_hit())

    assert decision.accepted is True
    assert decision.item_id == "1319712"
    assert decision.canonical_url.endswith(
        "/item/view/1319712/parti-med-klader-och-accessoarer-ca-600-artiklar"
    )


def test_gate_rejects_auction_index_and_wrong_host():
    index = psauction_gate_decision(
        _hit(url="https://psauction.se/auctions")
    )
    other_host = psauction_gate_decision(
        _hit(url="https://example.com/item/view/1319712/test")
    )

    assert index.accepted is False
    assert "specific item page" in index.reason
    assert other_host.accepted is False
    assert other_host.reason == "not a PS Auction host"


def test_gate_rejects_non_clothing_psauction_item():
    decision = psauction_gate_decision(
        _hit(
            title="Cirkelsåg med tillbehör",
            description="Maskin från konkursbo säljs på auktion.",
        )
    )

    assert decision.accepted is False
    assert "lacks clothing evidence" in decision.reason


def test_targeted_provider_filters_hits_and_reports_diagnostics():
    query = build_psauction_clothing_queries(1)[0]
    provider = FakeProvider(
        [
            _hit(),
            _hit(url="https://psauction.se/auctions"),
            _hit(
                title="Verktygsparti",
                url="https://psauction.se/item/view/999999/verktygsparti",
                description="Maskiner och verktyg från konkursbo.",
            ),
        ]
    )
    targeted = PSAuctionTargetedSearchProvider(
        provider,
        queries=(query,),
        request_budget=1,
    )

    accepted = targeted.search(query.query, count=10)
    diagnostics = targeted.diagnostics()

    assert [hit.url for hit in accepted] == [_hit().url]
    assert diagnostics["requests_made"] == 1
    assert diagnostics["raw_hits"] == 3
    assert diagnostics["accepted_hits"] == 1
    assert diagnostics["rejected_hits"] == 2
    assert diagnostics["accepted_item_ids"] == ["1319712"]


def test_psauction_hit_remains_unverified_until_public_page_check():
    query = build_psauction_clothing_queries(1)[0]
    raw_provider = FakeProvider([_hit()])
    targeted = PSAuctionTargetedSearchProvider(
        raw_provider,
        queries=(query,),
        request_budget=1,
    )
    localized = SwedenLocalizedSearchProvider(targeted)

    hit = localized.search(query.query, count=10)[0]
    observation = classify_search_hit(hit, query)

    assert observation.state == STRONG_LEAD_REQUIRES_VERIFICATION
    assert observation.opportunity_identity == "url-id:1319712"
    assert observation.identity_stable is True
