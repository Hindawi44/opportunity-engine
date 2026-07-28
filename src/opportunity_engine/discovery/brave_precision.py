"""Precision query policy for Brave-backed Clothing Inventory discovery.

This module refines the approved scenario matrix without changing its IDs,
scenario ownership, or Discovery/Analysis boundary. It uses Brave-supported
exact-match and exclusion operators to reduce predictable buyer-intent, job,
ordinary-store, and stale-listing noise before page verification.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from opportunity_engine.discovery.clothing_inventory_search import (
    CLOTHING_INVENTORY_QUERY_MATRIX,
    DiscoveryQuery,
)

BRAVE_PRECISION_FRESHNESS = "pm"

_PRECISION_QUERY_TEXT: dict[str, str] = {
    "sale-01": (
        '"klesbutikk" varelager selges Norge '
        '-jobb -stilling -nettbutikk -"ønskes kjøpt" -kjøpes'
    ),
    "sale-02": (
        '"hele lageret" klær "til salgs" Norge '
        '-jobb -nettbutikk -"ønskes kjøpt" -kjøpes'
    ),
    "sale-03": (
        '"vareparti" klær auksjon Norge '
        '-avsluttet -solgt -"ønskes kjøpt" -kjøpes'
    ),
    "sale-04": (
        '"restlager" klær selges Norge '
        '-jobb -nettbutikk -"ønskes kjøpt" -kjøpes'
    ),
    "sale-05": (
        '"konkursbo" klær auksjon Norge '
        '-avsluttet -solgt -jobb -stilling'
    ),
    "sale-06": (
        '"opphørssalg" klesbutikk "hele lageret" Norge '
        '-jobb -nettbutikk -"ønskes kjøpt" -kjøpes'
    ),
    "lead-01": (
        'konkurs klesbutikk varelager Norge '
        '-jobb -stilling -nettbutikk -wikipedia -podcast'
    ),
    "lead-02": (
        '"klesbutikk" avvikling Norge '
        '-jobb -stilling -nettbutikk -wikipedia -podcast'
    ),
    "lead-03": (
        '"butikk stenger" klær Norge '
        '-jobb -stilling -nettbutikk -wikipedia -podcast'
    ),
    "lead-04": (
        '"filial legges ned" klesbutikk Norge '
        '-jobb -stilling -nettbutikk -wikipedia -podcast'
    ),
    "lead-05": (
        '"lager ryddes" klesbutikk Norge '
        '-jobb -stilling -nettbutikk -wikipedia -podcast'
    ),
    "lead-06": (
        'opphør klesbutikk Trøndelag '
        '-jobb -stilling -nettbutikk -wikipedia -podcast'
    ),
    "special-01": (
        '"hele varelageret" klær "samlet salg" Norge '
        '-jobb -nettbutikk -"ønskes kjøpt" -kjøpes'
    ),
    "special-02": (
        '"stort klesparti" selges Norge '
        '-jobb -nettbutikk -"ønskes kjøpt" -kjøpes'
    ),
    "special-03": (
        '"arbeidstøy" restlager parti Norge '
        '-jobb -nettbutikk -"ønskes kjøpt" -kjøpes'
    ),
    "special-04": (
        '"sportsklær" konkursbo varelager Norge '
        '-jobb -stilling -nettbutikk -wikipedia -podcast'
    ),
}


def build_clothing_inventory_precision_queries(
    base_queries: Iterable[DiscoveryQuery] = CLOTHING_INVENTORY_QUERY_MATRIX,
) -> tuple[DiscoveryQuery, ...]:
    """Return the same scenario matrix with bounded Brave precision operators."""
    queries = tuple(base_queries)
    query_ids = {query.query_id for query in queries}
    configured_ids = set(_PRECISION_QUERY_TEXT)
    if query_ids != configured_ids:
        missing = sorted(query_ids - configured_ids)
        unexpected = sorted(configured_ids - query_ids)
        raise ValueError(
            "Brave precision policy does not match the approved query matrix: "
            f"missing={missing}, unexpected={unexpected}"
        )
    return tuple(
        replace(query, query=_PRECISION_QUERY_TEXT[query.query_id])
        for query in queries
    )
