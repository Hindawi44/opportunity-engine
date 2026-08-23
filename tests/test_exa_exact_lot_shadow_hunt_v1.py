from __future__ import annotations

import pytest

from opportunity_engine.discovery.exa_exact_lot_shadow_hunt import (
    MARKET_EXACT_LOT_QUERIES,
    run_exa_exact_lot_shadow_hunt,
)
from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult
from opportunity_engine.discovery.search_provider import SearchHit


EXPECTED_MARKETS = ["NO", "SE", "DE", "FR", "IT", "NL"]


def test_exact_lot_queries_cover_all_six_markets_with_commercial_specificity() -> None:
    assert list(MARKET_EXACT_LOT_QUERIES) == EXPECTED_MARKETS

    expected_terms = {
        "NO": ("til salgs", "pris", "stk"),
        "SE": ("säljes", "pris", "st"),
        "DE": ("zu verkaufen", "preis", "stück"),
        "FR": ("à vendre", "prix", "quantité"),
        "IT": ("in vendita", "prezzo", "pezzi"),
        "NL": ("te koop", "prijs", "stuks"),
    }
    for market, terms in expected_terms.items():
        query = MARKET_EXACT_LOT_QUERIES[market].casefold()
        for term in terms:
            assert term.casefold() in query


def test_exact_lot_hunt_runs_one_exa_query_per_market_then_direct_page_verification() -> None:
    searched: list[tuple[str, int]] = []

    class FakeProvider:
        def search(self, query: str, *, count: int = 10):
            searched.append((query, count))
            market = next(code for code, value in MARKET_EXACT_LOT_QUERIES.items() if value == query)
            return [
                SearchHit(
                    title=f"{market} exact-lot candidate",
                    url=f"https://example.{market.casefold()}/lot-1",
                    description="",
                    provider="Exa",
                )
            ]

    def provider_factory(api_key: str):
        assert api_key == "exa-secret"
        return FakeProvider()

    def page_fetcher(url: str) -> PageFetchResult:
        if url == "https://example.no/lot-1":
            text = (
                "Vareparti til salgs. 640 stk arbeidsjakker. Pris 18 500 NOK. "
                "Tilgjengelig på lager nå."
            )
        else:
            text = "Company information and general wholesale services."
        return PageFetchResult(
            requested_url=url,
            final_url=url,
            ok=True,
            status_code=200,
            title="Verified original page",
            text=text,
        )

    report = run_exa_exact_lot_shadow_hunt(
        exa_api_key="exa-secret",
        results_per_market=1,
        max_page_fetches=6,
        provider_factory=provider_factory,
        page_fetcher=page_fetcher,
    )

    assert report["status"] == "SUCCESS"
    assert report["shadow_only"] is True
    assert report["markets"] == EXPECTED_MARKETS
    assert report["exa_request_count"] == 6
    assert searched == [(MARKET_EXACT_LOT_QUERIES[code], 1) for code in EXPECTED_MARKETS]

    verification = report["verification"]
    assert verification["exa_unique_url_count"] == 6
    assert verification["page_fetches_attempted"] == 6
    assert verification["page_fetches_succeeded"] == 6
    assert verification["exact_lot_candidate_count"] == 1
    exact = [
        item
        for item in verification["verified_pages"]
        if item["classification"] == "EXACT_LOT_CANDIDATE"
    ]
    assert [item["market_code"] for item in exact] == ["NO"]

    assert report["production_provider_activation"] is False
    assert report["promotion_to_live_engine_enabled"] is False
    assert report["automatic_contact"] is False
    assert report["automatic_bid"] is False
    assert report["automatic_reservation"] is False
    assert report["automatic_purchase"] is False
    assert report["automatic_payment"] is False


def test_exact_lot_hunt_enforces_bounded_results_per_market() -> None:
    with pytest.raises(ValueError, match="results_per_market must be between 1 and 5"):
        run_exa_exact_lot_shadow_hunt(exa_api_key="secret", results_per_market=0)
    with pytest.raises(ValueError, match="results_per_market must be between 1 and 5"):
        run_exa_exact_lot_shadow_hunt(exa_api_key="secret", results_per_market=6)
