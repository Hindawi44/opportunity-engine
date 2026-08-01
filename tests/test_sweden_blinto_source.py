from __future__ import annotations

from dataclasses import dataclass

import pytest

from opportunity_engine.discovery.clothing_inventory_search import ACTIVE, ENDED
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.sweden_blinto import (
    BlintoPrefetchedSearchProvider,
    blinto_gate_decision,
    build_blinto_clothing_queries,
    canonicalize_blinto_auction_url,
    enrich_blinto_discovery_result,
    verify_blinto_public_page,
)


def _hit(title: str, url: str, description: str = "") -> SearchHit:
    return SearchHit(
        title=title,
        url=url,
        description=description,
        provider="Brave Search",
    )


def test_blinto_query_budget_is_bounded() -> None:
    assert len(build_blinto_clothing_queries(1)) == 1
    assert len(build_blinto_clothing_queries(8)) == 8
    with pytest.raises(ValueError):
        build_blinto_clothing_queries(0)
    with pytest.raises(ValueError):
        build_blinto_clothing_queries(9)


def test_canonicalize_preserves_object_and_occurrence_identity() -> None:
    identity = canonicalize_blinto_auction_url(
        "https://www.blinto.se/auction/Parti-212451-124376/?utm_source=x"
    )

    assert identity is not None
    assert identity.canonical_url == "https://blinto.se/auction/Parti-212451-124376"
    assert identity.object_id == "212451"
    assert identity.occurrence_id == "124376"
    assert identity.listing_key == "124376"
    assert canonicalize_blinto_auction_url("https://blinto.se/auction/") is None
    assert canonicalize_blinto_auction_url(
        "https://example.com/auction/Parti-212451-124376"
    ) is None


def test_gate_accepts_bulk_clothing_and_rejects_cabinets_and_single_items() -> None:
    accepted = blinto_gate_decision(
        _hit(
            "Arbetskläder - Parti med Arbetskläder | Blinto auktioner",
            "https://www.blinto.se/auction/Parti-med-Arbetsklader-157417-61518/",
            "Ett parti med 34 par arbetsbyxor. Överskott med nya byxor.",
        )
    )
    assert accepted.accepted is True
    assert accepted.object_id == "157417"
    assert accepted.occurrence_id == "61518"

    cabinet = blinto_gate_decision(
        _hit(
            "Klädskåp - Klädskåp | Blinto auktioner",
            "https://www.blinto.se/auction/Kladskap-137818-40458/",
            "Klädskåp med sex dörrar.",
        )
    )
    assert cabinet.accepted is False
    assert "equipment" in cabinet.reason

    single = blinto_gate_decision(
        _hit(
            "Arbetskläder - Arbetsjacka | Blinto auktioner",
            "https://www.blinto.se/auction/Arbetsjacka-150000-50000/",
            "En jacka i storlek L.",
        )
    )
    assert single.accepted is False
    assert "bulk" in single.reason


class _FakeProvider:
    name = "fake"

    def __init__(self, responses: dict[str, tuple[SearchHit, ...]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, *, count: int = 10):
        self.calls.append((query, count))
        return self.responses.get(query, ())


def test_prefetch_suppresses_only_ended_occurrence_not_relisted_object() -> None:
    queries = build_blinto_clothing_queries(2)
    ended_url = "https://blinto.se/auction/Parti-212451-124376/"
    relisted_url = "https://blinto.se/auction/Parti-212451-136834/"
    provider = _FakeProvider(
        {
            queries[0].query: (
                _hit("Arbetskläder - Parti", ended_url, "Parti med arbetskläder"),
                _hit("Arbetskläder - Parti", relisted_url, "Parti med arbetskläder"),
            ),
            queries[1].query: (
                _hit(
                    "Arbetskläder - Parti",
                    ended_url,
                    "Auktionen är avslutad. Parti med arbetskläder.",
                ),
            ),
        }
    )
    targeted = BlintoPrefetchedSearchProvider(
        provider,
        queries=queries,
        request_budget=2,
    )

    first = targeted.search(queries[0].query, count=10)
    assert [hit.url for hit in first] == [
        "https://blinto.se/auction/Parti-212451-136834"
    ]
    assert targeted.search(queries[1].query, count=10) == ()
    diagnostics = targeted.diagnostics()
    assert diagnostics["historical_listing_keys"] == ["124376"]
    assert diagnostics["accepted_object_ids"] == ["212451"]
    assert diagnostics["accepted_occurrence_ids"] == ["136834"]


@dataclass
class _FakeResponse:
    url: str
    text: str
    status_code: int = 200

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _html(
    *,
    description: str,
    status: str,
    location: str,
    object_id: int,
    bid: str = "",
) -> str:
    return f"""
    <html>
      <head>
        <title>Överskott - Parti med arbetskläder | Blinto auktioner</title>
        <meta name="description" content="Parti med arbetskläder">
      </head>
      <body>
        <h1>Överskott Parti med arbetskläder</h1>
        <p>{location} {object_id} Varulager &amp; Överskott</p>
        <h2>Beskrivning</h2>
        <div>{description}</div>
        <p>Lasthjälp finns.</p>
        <h2>Kontakta kundtjänst</h2>
        <p>Allmän information om Blinto.</p>
        <p>Karta över {location.upper()}</p>
        <p>{status}</p>
        <p>{bid}</p>
        <p>Alla objekt finns hos ägaren och köparen ansvarar själv för hämtning och frakt.</p>
      </body>
    </html>
    """


def test_verifier_extracts_active_surplus_quantity_and_source_identity(monkeypatch) -> None:
    url = "https://blinto.se/auction/Parti-med-arbetsklader-157419-61520"
    response = _FakeResponse(
        url="https://www.blinto.se/auction/Parti-med-arbetsklader-157419-61520/",
        text=_html(
            description=(
                "Ett parti med blandade klädesplagg bestående av 53 överdelar. "
                "Överskott av nya kläder. Marknadsvärde 18.000 SEK."
            ),
            status="Auktionen avslutas Tors 15/12 11:02.",
            location="Växjö",
            object_id=157419,
            bid="Högsta bud 2 900 SEK",
        ),
    )
    monkeypatch.setattr(
        "opportunity_engine.discovery.sweden_blinto.requests.get",
        lambda *args, **kwargs: response,
    )

    result = verify_blinto_public_page(url)

    assert result.verified is True
    assert result.opportunity_identity == "blinto-auction:157419:61520"
    assert result.identity_stable is True
    assert result.listing_status == ACTIVE
    assert result.event_scenario == "WAREHOUSE_SURPLUS"
    assert result.inventory_type == "mixed_clothing_inventory"
    assert result.quantity == 53
    assert result.location == "Växjö"
    assert result.clothing_inventory_evidence is True
    assert result.sale_evidence is True
    assert result.price_nok is None
    assert result.bid_price_nok is None
    assert "source bid value: 2900 SEK" in (result.bounded_context or "")
    assert "source reference value: 18000 SEK" in (result.bounded_context or "")


def test_verifier_detects_ended_workwear_and_never_writes_sek_to_nok(monkeypatch) -> None:
    url = "https://blinto.se/auction/Parti-med-Arbetsklader-157417-61518"
    response = _FakeResponse(
        url="https://www.blinto.se/auction/Parti-med-Arbetsklader-157417-61518/",
        text=_html(
            description=(
                "Ett parti med arbetsbyxor bestående av 34 par byxor. "
                "Överskott med nya arbetskläder. Marknadsvärde 20.000 SEK."
            ),
            status="Auktionen är avslutad. Såld.",
            location="Växjö",
            object_id=157417,
            bid="3 000 SEK Vinnande bud",
        ),
    )
    monkeypatch.setattr(
        "opportunity_engine.discovery.sweden_blinto.requests.get",
        lambda *args, **kwargs: response,
    )

    result = verify_blinto_public_page(url)

    assert result.listing_status == ENDED
    assert result.event_scenario == "WAREHOUSE_SURPLUS"
    assert result.quantity == 34
    assert result.sale_evidence is False
    assert result.price_nok is None
    assert result.bid_price_nok is None


def test_result_enrichment_adds_sek_fields_without_changing_hard_gates() -> None:
    url = "https://blinto.se/auction/Parti-med-arbetsklader-157419-61520"
    result = {
        "all_discovered_candidates": [
            {
                "source_urls": [url],
                "listing_status": "ACTIVE",
                "top5_eligible": False,
                "analysis_eligible": False,
                "price_nok": None,
                "bid_price_nok": None,
                "confirmed_information": [],
                "verification": [
                    {
                        "bounded_context": (
                            "source bid value: 2900 SEK | "
                            "source reference value: 18000 SEK | "
                            "loading assistance: available | "
                            "buyer responsible for pickup and transport"
                        )
                    }
                ],
            }
        ],
        "discovery_top5": [],
        "search_run_report": {},
    }

    enriched = enrich_blinto_discovery_result(result)
    candidate = enriched["all_discovered_candidates"][0]

    assert candidate["source_object_id"] == "157419"
    assert candidate["auction_occurrence_id"] == "61520"
    assert candidate["bid_price_sek"] == 2900
    assert candidate["reference_value_sek"] == 18000
    assert candidate["loading_assistance_available"] is True
    assert candidate["buyer_responsible_for_pickup_and_transport"] is True
    assert candidate["price_nok"] is None
    assert candidate["bid_price_nok"] is None
    assert candidate["top5_eligible"] is False
    assert candidate["analysis_eligible"] is False
    assert enriched["search_run_report"]["source_page_enrichment"] == {
        "source": "BLINTO",
        "candidates_enriched": 1,
        "sek_bid_values_extracted": 1,
        "sek_reference_values_extracted": 1,
        "nok_price_fields_written": False,
        "listing_status_changed": False,
        "top5_eligibility_changed": False,
    }
