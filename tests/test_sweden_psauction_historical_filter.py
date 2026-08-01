from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.sweden_psauction import (
    PSAuctionTargetedSearchProvider,
    build_psauction_clothing_queries,
    psauction_gate_decision,
)


class StaticProvider:
    name = "static"

    def __init__(self, hits):
        self.hits = list(hits)

    def search(self, query: str, *, count: int = 10):
        return self.hits[:count]


def _historical_hit() -> SearchHit:
    return SearchHit(
        title="Parti med 180 par nya skor i originalkartong",
        url=(
            "https://psauction.se/item/view/1448337/"
            "parti-med-180-par-nya-skor-i-originalkartong"
        ),
        description="Avyttring · Såld · Avslutad · Parti med skor.",
        provider="Static",
    )


def _unresolved_hit() -> SearchHit:
    return SearchHit(
        title="Parti med damkläder från Masai (ca 1300 stycken plagg)",
        url=(
            "https://psauction.se/item/view/670524/"
            "parti-med-damklader-fran-masai"
        ),
        description="Parti med cirka 1300 plagg från butikslager.",
        provider="Static",
    )


def test_known_ended_or_sold_item_is_rejected_before_page_verification():
    decision = psauction_gate_decision(_historical_hit())

    assert decision.accepted is False
    assert decision.item_id == "1448337"
    assert decision.reason == "specific PS Auction item is ended or sold"


def test_auction_ending_in_future_is_not_confused_with_ended_status():
    hit = SearchHit(
        title="Parti med kläder, ca 100 plagg",
        url="https://psauction.se/item/view/1560018/parti-med-klader",
        description="Auktionen avslutas 2026-08-04. Nuvarande bud 800 SEK.",
        provider="Static",
    )

    assert psauction_gate_decision(hit).accepted is True


def test_provider_preserves_historical_ids_in_diagnostics_but_returns_only_open_leads():
    query = build_psauction_clothing_queries(1)[0]
    provider = PSAuctionTargetedSearchProvider(
        StaticProvider([_historical_hit(), _unresolved_hit()]),
        queries=(query,),
        request_budget=1,
    )

    accepted = provider.search(query.query, count=10)
    diagnostics = provider.diagnostics()

    assert [hit.url for hit in accepted] == [_unresolved_hit().url]
    assert diagnostics["historical_item_count"] == 1
    assert diagnostics["historical_item_ids"] == ["1448337"]
    assert diagnostics["accepted_item_ids"] == ["670524"]
    assert diagnostics["rejection_reasons"] == {
        "specific PS Auction item is ended or sold": 1
    }
