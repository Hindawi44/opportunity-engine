"""Six-market Exa shadow hunt focused on clothing-inventory exact lots.

The queries require project-domain clothing/fashion evidence together with sale
availability, price and quantity intent in the local market language. Results
still pass through direct-page verification and remain shadow-only; no search
hit is promoted automatically.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from opportunity_engine.discovery.exa_search import ExaSearchProvider
from opportunity_engine.discovery.exa_shadow_page_verification import (
    PageFetcher,
    fetch_public_page,
    verify_exa_unique_pages,
)

MARKET_EXACT_LOT_QUERIES = {
    "NO": "Norge klær mote vareparti til salgs pris stk restlager lager nå",
    "SE": "Sverige kläder mode restparti säljes pris st överskottslager lager nu",
    "DE": "Deutschland Kleidung Mode Restposten zu verkaufen Preis Stück Warenlager aktuell",
    "FR": "France vêtements mode lot de marchandises à vendre prix quantité stock déstockage disponible",
    "IT": "Italia abbigliamento moda lotto stock in vendita prezzo pezzi magazzino disponibile",
    "NL": "Nederland kleding groothandel partij pakket pallet te koop prijs per stuk voorraad",
}


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _domain(url: str) -> str:
    return (urlparse(url).hostname or "").casefold().removeprefix("www.")


def run_exa_exact_lot_shadow_hunt(
    *,
    exa_api_key: str,
    results_per_market: int = 5,
    max_page_fetches: int = 30,
    provider_factory=ExaSearchProvider,
    page_fetcher: PageFetcher = fetch_public_page,
) -> dict[str, Any]:
    """Run six bounded clothing-domain Exa queries and verify original pages."""
    token = _compact(exa_api_key)
    if not token:
        raise ValueError("Exa API key is required")
    if not 1 <= results_per_market <= 5:
        raise ValueError("results_per_market must be between 1 and 5")

    provider = provider_factory(token)
    rows: list[dict[str, Any]] = []
    for market, query in MARKET_EXACT_LOT_QUERIES.items():
        hits = provider.search(query, count=results_per_market)
        results = [
            {
                "title": _compact(hit.title)[:1000],
                "url": _compact(hit.url),
                "domain": _domain(_compact(hit.url)),
                "description": _compact(hit.description)[:1000],
                "provider": _compact(hit.provider),
            }
            for hit in hits
        ]
        rows.append(
            {
                "market_code": market,
                "query": query,
                "exa": {
                    "result_count": len(results),
                    "unique_domain_count": len(
                        {item["domain"] for item in results if item["domain"]}
                    ),
                    "results": results,
                },
                "brave": {
                    "result_count": 0,
                    "unique_domain_count": 0,
                    "results": [],
                },
            }
        )

    discovery_report = {
        "schema_version": "exa-exact-lot-shadow-discovery-1.1",
        "status": "SUCCESS",
        "shadow_only": True,
        "provider_mode": "exa_exact_lot_clothing_inventory",
        "project_domain": "CLOTHING_INVENTORY",
        "project_domain_gate_enforced": True,
        "markets": list(MARKET_EXACT_LOT_QUERIES),
        "results_per_market": results_per_market,
        "exa_request_count": len(MARKET_EXACT_LOT_QUERIES),
        "market_results": rows,
        "interpretation_guard": (
            "Commercially specific search results are observations until the original page proves both clothing-domain relevance and exact-lot evidence."
        ),
    }
    verification = verify_exa_unique_pages(
        discovery_report,
        page_fetcher=page_fetcher,
        max_page_fetches=max_page_fetches,
    )

    return {
        "schema_version": "exa-exact-lot-shadow-hunt-1.1",
        "status": verification.get("status"),
        "shadow_only": True,
        "project_domain": "CLOTHING_INVENTORY",
        "project_domain_gate_enforced": True,
        "markets": list(MARKET_EXACT_LOT_QUERIES),
        "results_per_market": results_per_market,
        "exa_request_count": len(MARKET_EXACT_LOT_QUERIES),
        "discovery": discovery_report,
        "verification": verification,
        "production_provider_activation": False,
        "promotion_to_live_engine_enabled": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
