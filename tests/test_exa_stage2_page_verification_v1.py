from __future__ import annotations

from opportunity_engine.discovery.exa_shadow_page_verification import (
    EXACT_LOT_CANDIDATE,
    INFO_OR_LEGAL_ONLY,
    SOURCE_INTELLIGENCE_ONLY,
    ACTIVE_STOCK_SIGNAL,
    verify_exa_unique_pages,
)
from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult


def _report() -> dict:
    return {
        "schema_version": "exa-brave-shadow-benchmark-1.0",
        "status": "SUCCESS",
        "shadow_only": True,
        "markets": ["NO", "DE", "FR", "NL"],
        "market_results": [
            {
                "market_code": "NO",
                "query": "Norge bedrift avvikling restlager varelager selges",
                "exa": {
                    "results": [
                        {
                            "title": "Parti med arbeidsjakker",
                            "url": "https://example.no/lot/44",
                            "domain": "example.no",
                            "description": "",
                        },
                        {
                            "title": "Vi kjøper restlager",
                            "url": "https://buyer.no/restlager",
                            "domain": "buyer.no",
                            "description": "",
                        },
                    ]
                },
                "brave": {"results": []},
            },
            {
                "market_code": "DE",
                "query": "Deutschland Geschäftsauflösung Restposten Warenlager Verkauf",
                "exa": {
                    "results": [
                        {
                            "title": "Restposten aus Geschäftsauflösung",
                            "url": "https://example.de/restposten",
                            "domain": "example.de",
                            "description": "",
                        },
                        {
                            "title": "Already shared",
                            "url": "https://shared.de/page",
                            "domain": "shared.de",
                            "description": "",
                        },
                    ]
                },
                "brave": {
                    "results": [
                        {
                            "title": "Same URL",
                            "url": "https://shared.de/page",
                            "domain": "shared.de",
                            "description": "",
                        }
                    ]
                },
            },
            {
                "market_code": "FR",
                "query": "France liquidation entreprise stock déstockage vente",
                "exa": {
                    "results": [
                        {
                            "title": "Vente en liquidation : règles à respecter",
                            "url": "https://legal.fr/regles",
                            "domain": "legal.fr",
                            "description": "",
                        }
                    ]
                },
                "brave": {"results": []},
            },
            {
                "market_code": "NL",
                "query": "Nederland bedrijfsbeëindiging voorraad partijhandel uitverkoop",
                "exa": {
                    "results": [
                        {
                            "title": "Voorraad te koop",
                            "url": "https://market.nl/voorraad",
                            "domain": "market.nl",
                            "description": "",
                        }
                    ]
                },
                "brave": {"results": []},
            },
        ],
    }


def _page(url: str) -> PageFetchResult:
    bodies = {
        "https://example.no/lot/44": (
            "Parti med arbeidsjakker selges nå. 480 stk. Pris 12 000 NOK. "
            "Varene står på lager i Oslo og er tilgjengelig for kjøp."
        ),
        "https://buyer.no/restlager": (
            "Vi kjøper restlager og varepartier fra bedrifter ved avvikling. "
            "Kontakt oss dersom du ønsker å selge ditt varelager."
        ),
        "https://example.de/restposten": (
            "Restposten aus Geschäftsauflösung zu verkaufen. Warenlager mit "
            "Schuhen und Textilien. Verfügbar für Händler."
        ),
        "https://legal.fr/regles": (
            "Vente en liquidation : règles à respecter. Code de commerce et "
            "obligations légales pour les entreprises."
        ),
        "https://market.nl/voorraad": (
            "Voorraad en restpartijen te koop. Beschikbaar voor zakelijke kopers."
        ),
    }
    text = bodies[url]
    return PageFetchResult(
        requested_url=url,
        final_url=url,
        ok=True,
        status_code=200,
        title="Verified page",
        text=text,
    )


def test_stage2_verifies_only_exa_unique_urls_and_classifies_page_role() -> None:
    report = verify_exa_unique_pages(_report(), page_fetcher=_page, max_page_fetches=10)

    assert report["status"] == "SUCCESS"
    assert report["shadow_only"] is True
    assert report["exa_unique_url_count"] == 5
    assert report["page_fetches_attempted"] == 5
    assert report["page_fetches_succeeded"] == 5

    by_url = {item["url"]: item for item in report["verified_pages"]}
    assert "https://shared.de/page" not in by_url
    assert by_url["https://example.no/lot/44"]["classification"] == EXACT_LOT_CANDIDATE
    assert by_url["https://buyer.no/restlager"]["classification"] == SOURCE_INTELLIGENCE_ONLY
    assert by_url["https://example.de/restposten"]["classification"] == ACTIVE_STOCK_SIGNAL
    assert by_url["https://legal.fr/regles"]["classification"] == INFO_OR_LEGAL_ONLY
    assert by_url["https://market.nl/voorraad"]["classification"] == ACTIVE_STOCK_SIGNAL

    assert report["exact_lot_candidate_count"] == 1
    assert report["active_stock_signal_count"] == 2
    assert report["source_intelligence_only_count"] == 1
    assert report["info_or_legal_only_count"] == 1


def test_stage2_page_budget_is_hard_bounded_and_never_grants_production_authority() -> None:
    calls: list[str] = []

    def fetcher(url: str) -> PageFetchResult:
        calls.append(url)
        return _page(url)

    report = verify_exa_unique_pages(_report(), page_fetcher=fetcher, max_page_fetches=2)

    assert len(calls) == 2
    assert report["page_fetches_attempted"] == 2
    assert report["budget_exhausted_count"] == 3
    assert report["production_provider_activation"] is False
    assert report["promotion_to_live_engine_enabled"] is False
    assert report["automatic_contact"] is False
    assert report["automatic_bid"] is False
    assert report["automatic_reservation"] is False
    assert report["automatic_purchase"] is False
    assert report["automatic_payment"] is False


def test_stage2_requires_successful_shadow_benchmark_contract() -> None:
    bad = _report()
    bad["status"] = "FAILURE"
    report = verify_exa_unique_pages(bad, page_fetcher=_page, max_page_fetches=5)

    assert report["status"] == "BLOCKED_INPUT"
    assert report["block_reason"] == "BENCHMARK_NOT_SUCCESSFUL"
    assert report["verified_pages"] == []
