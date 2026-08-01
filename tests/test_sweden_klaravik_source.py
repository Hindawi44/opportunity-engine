from __future__ import annotations

from dataclasses import dataclass

import pytest

from opportunity_engine.discovery.clothing_inventory_search import ACTIVE, ENDED
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.sweden_klaravik import (
    KlaravikPrefetchedSearchProvider,
    build_klaravik_clothing_queries,
    canonicalize_klaravik_product_url,
    klaravik_gate_decision,
    verify_klaravik_public_page,
)


def _hit(
    title: str,
    url: str,
    description: str = "",
) -> SearchHit:
    return SearchHit(
        title=title,
        url=url,
        description=description,
        provider="Brave Search",
    )


def test_klaravik_query_budget_is_bounded() -> None:
    assert len(build_klaravik_clothing_queries(1)) == 1
    assert len(build_klaravik_clothing_queries(8)) == 8
    with pytest.raises(ValueError):
        build_klaravik_clothing_queries(0)
    with pytest.raises(ValueError):
        build_klaravik_clothing_queries(9)


def test_canonicalize_accepts_only_exact_product_auction_page() -> None:
    assert canonicalize_klaravik_product_url(
        "https://www.klaravik.se/auktion/produkt/klader-och-skor-stort-parti/?utm_source=x"
    ) == (
        "https://klaravik.se/auktion/produkt/klader-och-skor-stort-parti",
        "klader-och-skor-stort-parti",
    )
    assert canonicalize_klaravik_product_url("https://klaravik.se/auktion/") is None
    assert canonicalize_klaravik_product_url(
        "https://example.com/auktion/produkt/klader-parti"
    ) is None


def test_gate_accepts_bulk_clothing_and_rejects_noise_and_ended() -> None:
    accepted = klaravik_gate_decision(
        _hit(
            "Kläder och skor, stort parti",
            "https://klaravik.se/auktion/produkt/klader-och-skor-stort-parti/",
            "Större parti med kläder och skor från butik.",
        )
    )
    assert accepted.accepted is True

    single = klaravik_gate_decision(
        _hit(
            "Arbetsjacka",
            "https://klaravik.se/auktion/produkt/arbetsjacka/",
            "En jacka i storlek L.",
        )
    )
    assert single.accepted is False
    assert "bulk" in single.reason

    ended = klaravik_gate_decision(
        _hit(
            "Parti med kläder och skor",
            "https://klaravik.se/auktion/produkt/parti-klader-skor/",
            "Denna auktion är avslutad! Parti med kläder.",
        )
    )
    assert ended.accepted is False
    assert "ended or sold" in ended.reason


class _FakeProvider:
    name = "fake"

    def __init__(self, responses: dict[str, tuple[SearchHit, ...]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, *, count: int = 10):
        self.calls.append((query, count))
        return self.responses.get(query, ())


def test_prefetch_globally_removes_url_when_any_query_marks_it_ended() -> None:
    queries = build_klaravik_clothing_queries(2)
    url = "https://klaravik.se/auktion/produkt/klader-och-skor-stort-parti/"
    provider = _FakeProvider(
        {
            queries[0].query: (
                _hit("Kläder och skor, stort parti", url, "Stort parti kläder och skor"),
            ),
            queries[1].query: (
                _hit(
                    "Kläder och skor, stort parti",
                    url,
                    "Denna auktion är avslutad! Stort parti kläder och skor",
                ),
            ),
        }
    )
    targeted = KlaravikPrefetchedSearchProvider(
        provider,
        queries=queries,
        request_budget=2,
    )

    assert targeted.search(queries[0].query, count=10) == ()
    assert targeted.search(queries[1].query, count=10) == ()
    diagnostics = targeted.diagnostics()
    assert diagnostics["requests_made"] == 2
    assert diagnostics["historical_listing_count"] == 1
    assert diagnostics["accepted_hits"] == 0
    assert diagnostics["rejected_hits"] == 2


@dataclass
class _FakeResponse:
    url: str
    text: str
    status_code: int = 200

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _html(*, overview: str, status: str, location: str, object_id: int) -> str:
    return f"""
    <html>
      <head>
        <title>Restparti med kläder från sportbutik | Klaravik</title>
        <meta name="description" content="Restparti med kläder från sportbutik">
      </head>
      <body>
        <nav>Översikt Skick Plats &amp; frakt</nav>
        <p>{status}</p>
        <p>Objekt-id: {object_id}</p>
        <h1>Restparti med kläder från sportbutik</h1>
        <p>{location}</p>
        <p>Vid konkursförsäljning gäller särskilda villkor.</p>
        <h2>Översikt</h2>
        <div>{overview}</div>
        <h2>Viktig information</h2>
        <p>Allmän information från Klaravik.</p>
      </body>
    </html>
    """


def test_verifier_uses_item_overview_not_generic_bankruptcy_boilerplate(monkeypatch) -> None:
    url = "https://klaravik.se/auktion/produkt/restparti-med-klader-fran-sportbutik"
    response = _FakeResponse(
        url=url,
        text=_html(
            overview="Restparti med kläder från sportbutik. Många plagg och skor.",
            status="Auktionen avslutas 2026-08-04. Nuvarande bud 2 000 kr.",
            location="Örebro, Örebro län",
            object_id=826330,
        ),
    )
    monkeypatch.setattr(
        "opportunity_engine.discovery.sweden_klaravik.requests.get",
        lambda *args, **kwargs: response,
    )

    result = verify_klaravik_public_page(url)

    assert result.verified is True
    assert result.opportunity_identity == "url-id:826330"
    assert result.identity_stable is True
    assert result.listing_status == ACTIVE
    assert result.event_scenario == "WAREHOUSE_SURPLUS"
    assert result.inventory_type == "mixed_clothing_and_footwear"
    assert result.location == "Örebro, Örebro län"
    assert result.clothing_inventory_evidence is True
    assert result.sale_evidence is True
    assert result.price_nok is None
    assert result.bid_price_nok is None


def test_verifier_detects_source_scoped_bankruptcy_and_ended_status(monkeypatch) -> None:
    url = "https://klaravik.se/auktion/produkt/klader-och-skor-stort-parti"
    response = _FakeResponse(
        url=url,
        text=_html(
            overview=(
                "Större parti med kläder och skor från reklamföretag i konkurs. "
                "Arbetskläder, träningskläder och arbetsskor."
            ),
            status="Denna auktion är avslutad!",
            location="Katrineholm, Södermanlands län",
            object_id=885060,
        ),
    )
    monkeypatch.setattr(
        "opportunity_engine.discovery.sweden_klaravik.requests.get",
        lambda *args, **kwargs: response,
    )

    result = verify_klaravik_public_page(url)

    assert result.listing_status == ENDED
    assert result.event_scenario == "COMPANY_BANKRUPTCY"
    assert result.opportunity_identity == "url-id:885060"
    assert result.sale_evidence is False
    assert result.clothing_inventory_evidence is True
