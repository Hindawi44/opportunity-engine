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

SOURCE_TARGETED_FRESHNESS = "pm"
SOURCE_TARGETED_QUERY_BUDGET = 8

_SOURCE_TARGETED_QUERY_TEXT: dict[str, str] = {
    "sale-01": (
        "site:norskavvikling.no klesbutikk varelager selges "
        "-nyheter -artikkel -jobb -stilling -nettbutikk "
        '-"ønskes kjøpt" -kjøpes'
    ),
    "sale-02": (
        'site:finn.no/recommerce/forsale/item "hele lageret" klær "til salgs" '
        "-nyheter -artikkel -jobb -nettbutikk "
        '-"ønskes kjøpt" -kjøpes'
    ),
    "sale-03": (
        "site:auksjonen.no vareparti klær auksjon "
        "-nyheter -artikkel -blogg -avsluttet -solgt "
        '-"ønskes kjøpt" -kjøpes'
    ),
    "sale-04": (
        "site:stadssalg.no restlager klær selges "
        "-nyheter -artikkel -blogg -jobb -nettbutikk "
        '-"ønskes kjøpt" -kjøpes'
    ),
    "sale-05": (
        "site:norskavvikling.no konkursbo klær auksjon "
        "-nyheter -artikkel -jobb -stilling -avsluttet -solgt"
    ),
    "sale-06": (
        'site:stadssalg.no opphørssalg klesbutikk "hele lageret" '
        "-nyheter -artikkel -jobb -nettbutikk "
        '-"ønskes kjøpt" -kjøpes'
    ),
    "lead-01": (
        "site:forvalt.no/Konkurs konkurs klesbutikk varelager "
        "-jobb -stilling -nettbutikk -wikipedia -podcast"
    ),
    "lead-02": (
        'site:virksomhet.brreg.no konkurs "Detaljhandel med klær" '
        "-jobb -stilling -nettbutikk -wikipedia -podcast"
    ),
    "lead-03": (
        "site:konkurs.app klesbutikk konkurs "
        "-jobb -stilling -nettbutikk -wikipedia -podcast"
    ),
    "lead-04": (
        'site:forvalt.no/Konkurs "filial legges ned" klesbutikk '
        "-jobb -stilling -nettbutikk -wikipedia -podcast"
    ),
    "lead-05": (
        'site:norskavvikling.no "lager ryddes" klesbutikk '
        "-jobb -stilling -nettbutikk -wikipedia -podcast"
    ),
    "lead-06": (
        "site:forvalt.no/Konkurs opphør klesbutikk Trøndelag "
        "-jobb -stilling -nettbutikk -wikipedia -podcast"
    ),
    "special-01": (
        'site:auksjonen.no "hele varelageret" klær "samlet salg" '
        "-nyheter -artikkel -blogg -jobb -nettbutikk "
        '-"ønskes kjøpt" -kjøpes'
    ),
    "special-02": (
        'site:finn.no/recommerce/forsale/item "stort klesparti" selges '
        "-nyheter -artikkel -jobb -nettbutikk "
        '-"ønskes kjøpt" -kjøpes'
    ),
    "special-03": (
        "site:auksjonen.no arbeidstøy restlager parti "
        "-nyheter -artikkel -blogg -jobb -nettbutikk "
        '-"ønskes kjøpt" -kjøpes'
    ),
    "special-04": (
        "site:norskavvikling.no sportsklær konkursbo varelager "
        "-nyheter -artikkel -jobb -stilling -nettbutikk -podcast"
    ),
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

SOURCE_TARGETED_REFERENCE_QUERIES: tuple[DiscoveryQuery, ...] = (
    DiscoveryQuery(
        "reference-axl",
        "COMPANY_BANKRUPTCY",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        'site:norskavvikling.no "AXL Sport Og Fritid" Kolvereid',
        "SECONDARY",
    ),
    DiscoveryQuery(
        "reference-by-fiona",
        "COMPANY_BANKRUPTCY",
        "EVENT_LEAD",
        "CLOTHING_INVENTORY",
        'site:forvalt.no/Konkurs "ANNA J AS" Namsos',
        "SECONDARY",
    ),
    DiscoveryQuery(
        "reference-tommeliten",
        "COMPANY_BANKRUPTCY",
        "EVENT_LEAD",
        "CLOTHING_INVENTORY",
        'site:virksomhet.brreg.no "TOMMELITEN BARNEKLÆR AS" konkurs',
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
