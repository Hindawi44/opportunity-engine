"""Source-targeted query adapter for Norway textile and sewing discovery.

This module connects the Norway Textile Keyword Pack V1 to the existing strict
retrieval contract without changing URL, page-role, lifecycle, deduplication, or
Top 5 gates. It only replaces broad public queries with bounded host-targeted
queries while preserving query IDs, scenarios, intents, and taxonomy categories.
"""
from __future__ import annotations

from dataclasses import replace

from opportunity_engine.discovery.clothing_inventory_search import DiscoveryQuery
from opportunity_engine.discovery.norway_textile_keywords import (
    NorwayTextileKeywordQuery,
    build_norway_textile_keyword_queries,
)
from opportunity_engine.discovery.source_targeted_queries import (
    SOURCE_TARGETED_FRESHNESS,
    SOURCE_TARGETED_QUERY_BUDGET,
)

# Each canonical keyword-pack ID is assigned to one bounded public source. The
# downstream URL gate remains authoritative; a search hit never confirms a sale.
_SOURCE_TARGETED_QUERY_TEXT: dict[str, str] = {
    "sale-01": "klesbutikk varelager selges site:norskavvikling.no",
    "sale-02": "stoffruller restlager selges site:finn.no",
    "sale-03": "industrisymaskiner tekstilbedrift auksjon site:auksjonen.no",
    "sale-04": "sytilbehør sybutikk restlager site:finn.no",
    "sale-05": "skredderverksted utstyr konkursbo site:norskavvikling.no",
    "sale-06": "opphørssalg klesbutikk hele lageret site:stadssalg.no",
    "lead-01": "kleskjede filial stenger varelager site:forvalt.no",
    "lead-02": "systue avvikling utstyr site:forvalt.no",
    "lead-03": "klesproduksjon konkurs produksjonsutstyr site:konkurs.app",
    "lead-04": "klesmerke merkevarer restlager site:norskavvikling.no",
    "lead-05": "skobutikk opphør varelager site:forvalt.no",
    "lead-06": "stoffbutikk opphør stofflager site:forvalt.no",
    "special-01": '"hele varelageret" klær samlet salg site:auksjonen.no',
    "special-02": "stoffruller tekstil auksjon site:auksjonen.no",
    "special-03": "overlock systue selges site:finn.no",
    "special-04": "butikkinnredning klesbutikk selges site:finn.no",
}

_SOURCE_TARGETED_PRIORITY = (
    "sale-03",
    "sale-05",
    "sale-02",
    "sale-04",
    "sale-01",
    "sale-06",
    "lead-01",
    "lead-03",
    "lead-02",
    "lead-04",
    "lead-05",
    "lead-06",
    "special-01",
    "special-02",
    "special-03",
    "special-04",
)


def _to_discovery_query(spec: NorwayTextileKeywordQuery) -> DiscoveryQuery:
    return DiscoveryQuery(
        query_id=spec.query_id,
        scenario=spec.scenario,
        intent=spec.intent,
        asset_scope=spec.category,
        query=_SOURCE_TARGETED_QUERY_TEXT[spec.query_id],
        rotation_group=spec.rotation_group,
    )


def build_norway_textile_source_targeted_queries(
    *, country: str = "Norge",
) -> tuple[DiscoveryQuery, ...]:
    """Return all 16 keyword-pack queries with bounded source targeting."""
    specs = build_norway_textile_keyword_queries(country=country)
    query_ids = {spec.query_id for spec in specs}
    configured_ids = set(_SOURCE_TARGETED_QUERY_TEXT)
    if query_ids != configured_ids:
        missing = sorted(query_ids - configured_ids)
        unexpected = sorted(configured_ids - query_ids)
        raise ValueError(
            "Norway textile source policy does not match keyword pack: "
            f"missing={missing}, unexpected={unexpected}"
        )
    return tuple(_to_discovery_query(spec) for spec in specs)


def select_norway_textile_source_targeted_queries(
    query_budget: int = SOURCE_TARGETED_QUERY_BUDGET,
    *, country: str = "Norge",
) -> tuple[DiscoveryQuery, ...]:
    """Select a bounded priority prefix while preserving canonical IDs."""
    full = build_norway_textile_source_targeted_queries(country=country)
    if not 1 <= query_budget <= len(full):
        raise ValueError(f"query_budget must be between 1 and {len(full)}")
    by_id = {query.query_id: query for query in full}
    return tuple(by_id[query_id] for query_id in _SOURCE_TARGETED_PRIORITY[:query_budget])


NORWAY_TEXTILE_SOURCE_TARGETED_FRESHNESS = SOURCE_TARGETED_FRESHNESS
NORWAY_TEXTILE_SOURCE_TARGETED_QUERY_BUDGET = SOURCE_TARGETED_QUERY_BUDGET
