from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.sweden_psauction import psauction_gate_decision


_URL = "https://psauction.se/item/view/580782/parti-med-klader-ca-50-plagg"


def _hit(description: str) -> SearchHit:
    return SearchHit(
        title="Parti med kläder, ca 50 plagg",
        url=_URL,
        description=description,
        provider="Static",
    )


def test_standalone_avslutad_token_is_historical():
    decision = psauction_gate_decision(
        _hit("Avslutad · Info Frakt Visning Utlämning Auktionstyp")
    )

    assert decision.accepted is False
    assert decision.reason == "specific PS Auction item is ended or sold"


def test_standalone_sald_token_is_historical():
    decision = psauction_gate_decision(
        _hit("Konkurs · Såld · Info Frakt Visning Utlämning Auktionstyp")
    )

    assert decision.accepted is False
    assert decision.reason == "specific PS Auction item is ended or sold"


def test_future_auction_ending_phrase_is_not_historical():
    decision = psauction_gate_decision(
        _hit(
            "Auktionen avslutas 2026-08-04. Nuvarande bud 800 SEK. "
            "Parti med 50 plagg."
        )
    )

    assert decision.accepted is True


def test_reserve_price_boilerplate_is_not_historical():
    decision = psauction_gate_decision(
        _hit(
            "Om auktionen avslutas utan att reservationspriset uppnåtts kan "
            "säljaren godkänna budet. Parti med 50 plagg."
        )
    )

    assert decision.accepted is True
