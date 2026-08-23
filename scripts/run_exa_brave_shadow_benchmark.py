#!/usr/bin/env python3
"""Run a bounded clothing-inventory Exa-vs-Brave shadow search benchmark.

This script is diagnostic only. Search hits are not opportunities and the
output cannot contact, bid, reserve, purchase, pay, or activate a provider in
production. Query wording is explicitly anchored to CLOTHING_INVENTORY so the
benchmark cannot reward a provider for unrelated liquidation noise.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.exa_exact_lot_shadow_hunt import MARKET_EXACT_LOT_QUERIES
from opportunity_engine.discovery.exa_search import ExaSearchProvider
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY

MARKET_QUERIES = {
    "NO": "Norge klær mote bedrift avvikling restlager varelager selges",
    "SE": "Sverige kläder mode företag avveckling restlager lager säljes",
    "DE": "Deutschland Kleidung Mode Geschäftsauflösung Restposten Warenlager Verkauf",
    "FR": "France vêtements mode liquidation entreprise stock déstockage vente",
    "IT": "Italia abbigliamento moda cessazione attività liquidazione magazzino stock vendita",
    "NL": "Nederland kleding mode bedrijfsbeëindiging voorraad partijhandel uitverkoop",
}

QUERY_MODES = ("discovery", "exact_lot")


def market_queries_for_mode(query_mode: str) -> dict[str, str]:
    """Return a defensive copy of the bounded query set for one search intent."""
    if query_mode == "discovery":
        return dict(MARKET_QUERIES)
    if query_mode == "exact_lot":
        return dict(MARKET_EXACT_LOT_QUERIES)
    raise ValueError("query_mode must be discovery or exact_lot")


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _domain(url: str) -> str:
    host = (urlparse(url).hostname or "").casefold()
    return host.removeprefix("www.")


def _row(hit) -> dict[str, str]:
    return {
        "title": _compact(hit.title)[:1000],
        "url": _compact(hit.url),
        "domain": _domain(_compact(hit.url)),
        "description": _compact(hit.description)[:1000],
        "provider": _compact(hit.provider),
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def run_benchmark(
    *,
    exa_api_key: str,
    brave_api_key: str | None,
    markets: list[str],
    results_per_query: int,
    provider_mode: str,
    query_mode: str = "discovery",
) -> dict[str, Any]:
    if not 1 <= results_per_query <= 5:
        raise ValueError("results_per_query must be between 1 and 5")
    selected_queries = market_queries_for_mode(query_mode)
    normalized_markets = [code.strip().upper() for code in markets if code.strip()]
    unsupported = [code for code in normalized_markets if code not in selected_queries]
    if unsupported:
        raise ValueError(f"unsupported markets: {unsupported}")
    if not normalized_markets:
        raise ValueError("at least one market is required")
    if provider_mode not in {"exa", "both"}:
        raise ValueError("provider_mode must be exa or both")
    if provider_mode == "both" and not _compact(brave_api_key):
        raise ValueError("BRAVE_SEARCH_API_KEY is required for provider_mode=both")

    exa = ExaSearchProvider(exa_api_key)
    rows: list[dict[str, Any]] = []
    exa_request_count = 0
    brave_request_count = 0

    for market in normalized_markets:
        query = selected_queries[market]
        exa_hits = exa.search(query, count=results_per_query)
        exa_request_count += 1
        brave_hits = []
        if provider_mode == "both":
            brave = BraveSearchProvider(
                str(brave_api_key),
                country=market,
                freshness="pm",
                extra_snippets=True,
            )
            brave_hits = brave.search(query, count=results_per_query)
            brave_request_count += 1

        exa_rows = [_row(hit) for hit in exa_hits]
        brave_rows = [_row(hit) for hit in brave_hits]
        exa_urls = {item["url"] for item in exa_rows}
        brave_urls = {item["url"] for item in brave_rows}
        exa_domains = {item["domain"] for item in exa_rows if item["domain"]}
        brave_domains = {item["domain"] for item in brave_rows if item["domain"]}

        rows.append(
            {
                "market_code": market,
                "query": query,
                "exa": {
                    "result_count": len(exa_rows),
                    "unique_domain_count": len(exa_domains),
                    "results": exa_rows,
                },
                "brave": {
                    "result_count": len(brave_rows),
                    "unique_domain_count": len(brave_domains),
                    "results": brave_rows,
                },
                "comparison": {
                    "shared_url_count": len(exa_urls & brave_urls),
                    "exa_unique_url_count": len(exa_urls - brave_urls),
                    "brave_unique_url_count": len(brave_urls - exa_urls),
                    "shared_domain_count": len(exa_domains & brave_domains),
                    "exa_unique_domain_count": len(exa_domains - brave_domains),
                    "brave_unique_domain_count": len(brave_domains - exa_domains),
                },
            }
        )

    return {
        "schema_version": "exa-brave-shadow-benchmark-1.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "SUCCESS",
        "shadow_only": True,
        "provider_mode": provider_mode,
        "query_mode": query_mode,
        "query_set": {market: selected_queries[market] for market in normalized_markets},
        "project_domain": CLOTHING_INVENTORY,
        "project_domain_gate_enforced": True,
        "markets": normalized_markets,
        "results_per_query": results_per_query,
        "exa_request_count": exa_request_count,
        "brave_request_count": brave_request_count,
        "market_results": rows,
        "interpretation_guard": (
            "Search hits are discovery observations only; exact pages must prove CLOTHING_INVENTORY relevance before tool learning may reward them."
        ),
        "production_provider_activation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--markets",
        default="NO,SE,DE,FR,IT,NL",
        help="Comma-separated subset of NO,SE,DE,FR,IT,NL",
    )
    parser.add_argument("--results-per-query", type=int, default=3)
    parser.add_argument(
        "--provider-mode",
        choices=("exa", "both"),
        default="both",
        help="exa performs a connectivity/search proof; both compares Exa and Brave",
    )
    parser.add_argument(
        "--query-mode",
        choices=QUERY_MODES,
        default="discovery",
        help="discovery uses closure/liquidation intent; exact_lot requires item-specific price and quantity intent",
    )
    args = parser.parse_args()

    exa_api_key = _compact(os.environ.get("EXA_API_KEY"))
    if not exa_api_key:
        raise SystemExit("EXA_API_KEY is required")
    brave_api_key = _compact(os.environ.get("BRAVE_SEARCH_API_KEY")) or None

    report = run_benchmark(
        exa_api_key=exa_api_key,
        brave_api_key=brave_api_key,
        markets=args.markets.split(","),
        results_per_query=args.results_per_query,
        provider_mode=args.provider_mode,
        query_mode=args.query_mode,
    )
    output = Path(args.output)
    _write_json(output, report)
    print(f"status={report['status']}")
    print(f"shadow_only={report['shadow_only']}")
    print(f"query_mode={report['query_mode']}")
    print(f"markets={','.join(report['markets'])}")
    print(f"exa_requests={report['exa_request_count']}")
    print(f"brave_requests={report['brave_request_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
