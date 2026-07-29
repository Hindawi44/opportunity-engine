"""Source-targeted Brave query policy for Clothing Inventory retrieval.

This policy keeps the approved sixteen-query contract but assigns each query to
one bounded sale source or event registry. It is retrieval-only: snippets and
registry pages cannot confirm a sale or bypass the existing verification gates.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from opportunity_engine.discovery.clothing_inventory_search import (
    CLOTHING_INVENTORY_QUERY_MATRIX,
    DiscoveryQuery,
)

# Source targeting already constrains the host, while the URL gate constrains the
# page shape. Do not apply a date filter by default: Brave freshness is based on
# the page's indexed date, not whether a sale is still active.
SOURCE_TARGETED_FRESHNESS = "none"
SOURCE_TARGETED_QUERY_BUDGET = 8

# Keep queries deliberately short. The previous live run combined path-scoped
# site operators, exact phrases, many exclusions, and freshness=pm; Brave
# returned zero raw hits for all eleven requests. Host-only site restrictions
# plus the existing URL gate provide precision without suppressing recall.
_SOURCE_TARGETED_QUERY_TEXT: dict[str, str] = {
    "sale-01": "klesbutikk varelager selges site:norskavvikling.no",
    "sale-02": (
        'vareparti klær site:finn.no -"ønskes kjøpt" -kjøpes'
    ),
    "sale-03": "vareparti klær site:auksjonen.no",
    "sale-04": "restlager klær site:stadssalg.no",
    "sale-05": "konkursbo klær site:norskavvikling.no",
    "sale-06": "opphørssalg klesbutikk site:stadssalg.no",
    "lead-01": "konkurs klesbutikk site:forvalt.no",
    "lead-02": "detaljhandel klær konkurs site:virksomhet.brreg.no",
    "lead-03": "klesbutikk konkurs site:konkurs.app",
    "lead-04": "filial stenger klesbutikk site:forvalt.no",
    "lead-05": "lager ryddes klesbutikk site:norskavvikling.no",
    "lead-06": "opphør klesbutikk Trøndelag site:forvalt.no",
    "special-01": "hele varelageret klær site:auksjonen.no",
    "special-02": (
        'stort klesparti site:finn.no -"ønskes kjøpt" -kjøpes'
    ),
    "special-03": "arbeidstøy parti site:auksjonen.no",
    "special-04": "sportsklær konkursbo site:norskavvikling.no",
}

_SOURCE_TARGETED_PRIORITY = (
    "sale-03",
    "sale-05",
    "sale-04",
    "sale-02",
    "lead-01",
    "lead-02",
    "lead-03",
    "lead-06",
    "sale-01",
    "sale-06",
    "special-01",
    "special-02",
    "special-03",
    "special-04",
    "lead-04",
    "lead-05",
)

# Reference checks use stable organisation numbers rather than names. Live Brave
# evidence showed that name-heavy queries either returned no results or returned
# other organisations from the same registry. The number is also present in the
# canonical public organisation URL, allowing identity recovery without relaxing
# the URL gate or any downstream verification rule.
SOURCE_TARGETED_REFERENCE_QUERIES: tuple[DiscoveryQuery, ...] = (
    DiscoveryQuery(
        "reference-axl",
        "COMPANY_BANKRUPTCY",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        "AXL Sport Og Fritid Kolvereid site:norskavvikling.no",
        "SECONDARY",
    ),
    DiscoveryQuery(
        "reference-by-fiona",
        "COMPANY_BANKRUPTCY",
        "EVENT_LEAD",
        "CLOTHING_INVENTORY",
        "989324217 site:forvalt.no",
        "SECONDARY",
    ),
    DiscoveryQuery(
        "reference-tommeliten",
        "COMPANY_BANKRUPTCY",
        "EVENT_LEAD",
        "CLOTHING_INVENTORY",
        "932113309 site:virksomhet.brreg.no",
        "SECONDARY",
    ),
)


def build_source_targeted_queries(
    base_queries: Iterable[DiscoveryQuery] = CLOTHING_INVENTORY_QUERY_MATRIX,
) -> tuple[DiscoveryQuery, ...]:
    """Return the approved query matrix with one explicit source per query."""
    queries = tuple(base_queries)
    query_ids = {query.query_id for query in queries}
    configured_ids = set(_SOURCE_TARGETED_QUERY_TEXT)
    if query_ids != configured_ids:
        missing = sorted(query_ids - configured_ids)
        unexpected = sorted(configured_ids - query_ids)
        raise ValueError(
            "source-targeted policy does not match the approved query matrix: "
            f"missing={missing}, unexpected={unexpected}"
        )
    return tuple(
        replace(query, query=_SOURCE_TARGETED_QUERY_TEXT[query.query_id])
        for query in queries
    )


def select_source_targeted_queries(
    query_budget: int = SOURCE_TARGETED_QUERY_BUDGET,
) -> tuple[DiscoveryQuery, ...]:
    """Select a bounded, source-diverse prefix without changing canonical IDs."""
    full = build_source_targeted_queries()
    if not 1 <= query_budget <= len(full):
        raise ValueError(f"query_budget must be between 1 and {len(full)}")
    by_id = {query.query_id: query for query in full}
    return tuple(by_id[query_id] for query_id in _SOURCE_TARGETED_PRIORITY[:query_budget])
