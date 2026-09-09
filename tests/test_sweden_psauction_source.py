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
    build_psauction_exact_status_query,
    build_psauction_clothing_queries,
    canonicalize_psauction_item_url,
    canonicalize_psauction_listing_url,
    psauction_listing_route,
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
    assert all("site:psauction.se/auction" in query.query for query in queries[:2])
    assert all("site:psauction.se/item/view" in query.query for query in queries[2:])
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


def test_exact_item_url_canonicalization_is_bounded():
    canonical = canonicalize_psauction_item_url(_hit().url)
    current = (
        "https://psauction.se/auction/68986/"
        "vaxjo-inunder-ab-i-konkurs"
    )
    ended = (
        "https://psauction.se/auction/ended/68906/"
        "avyttring-av-arbets-och-skyddsklader-3"
    )

    assert canonical == (_hit().url, "1319712")
    assert canonicalize_psauction_listing_url(current) == (current, "68986")
    assert canonicalize_psauction_listing_url(ended) == (ended, "68906")
    assert psauction_listing_route(current) == "auction"
    assert psauction_listing_route(ended) == "ended_auction"
    assert build_psauction_exact_status_query(current) == (
        'site:psauction.se/auction "68986"'
    )
    assert build_psauction_exact_status_query(ended) == (
        'site:psauction.se/auction/ended "68906"'
    )
    assert build_psauction_exact_status_query(_hit().url) == (
        'site:psauction.se/item/view "1319712"'
    )
    assert canonicalize_psauction_item_url("https://psauction.se/auctions") is None
    assert canonicalize_psauction_item_url(
        "https://example.com/item/view/1319712/test"
    ) is None


def test_gate_accepts_one_specific_psauction_clothing_lot():
    decision = psauction_gate_decision(_hit())

    assert decision.accepted is True
    assert decision.item_id == "1319712"
    assert decision.canonical_url.endswith(
        "/item/view/1319712/parti-med-klader-och-accessoarer-ca-600-artiklar"
    )


def test_gate_accepts_bulk_accessories_with_explicit_quantity():
    decision = psauction_gate_decision(
        _hit(
            title="Ca 100 st Läderbälten, Strl 90-105",
            url="https://psauction.se/item/view/1560018/ca-100-st-laderbalten-strl-90-105",
            description="Auktionen avslutas. Nuvarande bud 800 SEK.",
        )
    )

    assert decision.accepted is True
    assert decision.item_id == "1560018"


def test_gate_accepts_current_vaxjo_bankruptcy_auction_route():
    decision = psauction_gate_decision(
        SearchHit(
            title="Växjö Inunder AB i konkurs",
            url=(
                "https://psauction.se/auction/68986/"
                "vaxjo-inunder-ab-i-konkurs"
            ),
            description=(
                "Auktionen innehåller butiksinredning, möbler och kläder såsom "
                "underkläder och badkläder. 35 objekt. Auktionen slutar "
                "2026-09-10."
            ),
            provider="PS Auction bankruptcy index",
        )
    )

    assert decision.accepted is True
    assert decision.item_id == "68986"


def test_gate_rejects_ended_current_auction_route():
    decision = psauction_gate_decision(
        SearchHit(
            title="Avslutad modebutik AB i konkurs",
            url="https://psauction.se/auction/68000/avslutad-modebutik",
            description=(
                "Auktionen innehåller kläder och butiksinredning. 24 objekt. "
                "Auktionen är avslutad."
            ),
            provider="PS Auction bankruptcy index",
        )
    )

    assert decision.accepted is False
    assert decision.item_id == "68000"
    assert decision.reason == "specific PS Auction item is ended or sold"


def test_gate_rejects_explicit_ended_auction_route_without_snippet_status():
    decision = psauction_gate_decision(
        SearchHit(
            title="Avyttring av arbets- och skyddskläder",
            url=(
                "https://psauction.se/auction/ended/68906/"
                "avyttring-av-arbets-och-skyddsklader-3"
            ),
            description="79 objekt i Helsingborg.",
            provider="PS Auction ended index",
        )
    )

    assert decision.accepted is False
    assert decision.item_id == "68906"
    assert decision.reason == "specific PS Auction item is ended or sold"


def test_gate_rejects_single_clothing_item_without_bulk_evidence():
    decision = psauction_gate_decision(
        _hit(
            title="Golfskor G/Fore Mens Gallivan2r, Strl 44",
            url="https://psauction.se/item/view/1517289/golfskor-strl-44",
            description="Auktionen avslutas. Nuvarande bud 200 SEK.",
        )
    )

    assert decision.accepted is False
    assert decision.reason == "specific clothing item lacks bulk inventory evidence"


def test_gate_rejects_shop_fittings_without_clothing_inventory():
    decision = psauction_gate_decision(
        _hit(
            title="Butiksinredning – Hyllor, bord, speglar och klädställ",
            url="https://psauction.se/item/view/1319713/butiksinredning-hyllor-bord",
            description="Inredning från klädbutik säljs på auktion.",
        )
    )

    assert decision.accepted is False
    assert "lacks clothing evidence" in decision.reason


def test_gate_rejects_auction_index_and_wrong_host():
    index = psauction_gate_decision(
        _hit(url="https://psauction.se/auctions")
    )
    other_host = psauction_gate_decision(
        _hit(url="https://example.com/item/view/1319712/test")
    )

    assert index.accepted is False
    assert "specific listing page" in index.reason
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
    assert diagnostics["accepted_samples"][0]["item_id"] == "1319712"
    assert len(diagnostics["rejected_samples"]) == 2
    assert diagnostics["rejected_samples"][0]["query_id"] == query.query_id
    assert diagnostics["rejected_samples"][0]["url"] == "https://psauction.se/auctions"
    assert diagnostics["rejected_samples"][0]["reason"] == (
        "PS Auction URL is not one specific listing page"
    )
    assert diagnostics["rejected_samples"][1]["item_id"] == "999999"
    assert "lacks clothing evidence" in diagnostics["rejected_samples"][1]["reason"]


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
