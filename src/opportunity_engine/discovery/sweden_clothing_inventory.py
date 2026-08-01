"""Bounded Swedish Clothing Inventory discovery configuration.

The Swedish pilot reuses the validated Norway discovery engine. Search snippets
receive conservative Norwegian aliases only for terms that are explicitly
present in the Swedish text, allowing the existing classifier to operate without
mixing market-specific vocabulary into its core rules.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Sequence

from opportunity_engine.discovery.clothing_inventory_search import (
    ACTIVE,
    ENDED,
    ITEM_LISTING,
    DiscoveryQuery,
    PageVerification,
    verify_public_page,
)
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider


SWEDEN_CLOTHING_QUERY_MATRIX: tuple[DiscoveryQuery, ...] = (
    DiscoveryQuery("se-sale-01", "INVENTORY_LIQUIDATION", "SALE_INTENT", "CLOTHING_INVENTORY", 'klädbutik varulager säljes Sverige -köpes -jobb -webbutik'),
    DiscoveryQuery("se-sale-02", "LARGE_LOT_SALE", "SALE_INTENT", "CLOTHING_INVENTORY", 'hela lagret kläder till salu Sverige -köpes -jobb'),
    DiscoveryQuery("se-sale-03", "AUCTION", "SALE_INTENT", "CLOTHING_INVENTORY", 'lagerparti kläder auktion Sverige -jobb -webbutik'),
    DiscoveryQuery("se-sale-04", "WAREHOUSE_SURPLUS", "SALE_INTENT", "CLOTHING_INVENTORY", 'restlager kläder säljes Sverige -köpes -jobb'),
    DiscoveryQuery("se-sale-05", "COMPANY_BANKRUPTCY", "SALE_INTENT", "CLOTHING_INVENTORY", 'konkursbo kläder auktion Sverige -jobb'),
    DiscoveryQuery("se-sale-06", "STORE_CLOSING", "SALE_INTENT", "CLOTHING_INVENTORY", 'utförsäljning klädbutik hela lagret Sverige -jobb'),
    DiscoveryQuery("se-lead-01", "COMPANY_BANKRUPTCY", "EVENT_LEAD", "CLOTHING_INVENTORY", 'konkurs klädbutik varulager Sverige -jobb'),
    DiscoveryQuery("se-lead-02", "STORE_CLOSING", "EVENT_LEAD", "CLOTHING_INVENTORY", 'klädbutik avveckling Sverige -jobb'),
    DiscoveryQuery("se-lead-03", "STORE_CLOSING", "EVENT_LEAD", "CLOTHING_INVENTORY", 'butik stänger kläder Sverige -jobb'),
    DiscoveryQuery("se-lead-04", "BRANCH_CLOSURE", "EVENT_LEAD", "CLOTHING_INVENTORY", 'filial stänger klädbutik Sverige -jobb'),
    DiscoveryQuery("se-lead-05", "INVENTORY_LIQUIDATION", "EVENT_LEAD", "CLOTHING_INVENTORY", 'lager rensas klädbutik Sverige -jobb'),
    DiscoveryQuery("se-lead-06", "STORE_CLOSING", "EVENT_LEAD", "CLOTHING_INVENTORY", 'klädbutik läggs ned Sverige -jobb'),
    DiscoveryQuery("se-special-01", "INVENTORY_LIQUIDATION", "SPECIALIZED", "CLOTHING_INVENTORY", '"hela varulagret" kläder samlad försäljning Sverige', "SECONDARY"),
    DiscoveryQuery("se-special-02", "LARGE_LOT_SALE", "SPECIALIZED", "CLOTHING_INVENTORY", '"stort klädparti" säljes Sverige', "SECONDARY"),
    DiscoveryQuery("se-special-03", "WAREHOUSE_SURPLUS", "SPECIALIZED", "CLOTHING_INVENTORY", 'arbetskläder restlager parti Sverige', "SECONDARY"),
    DiscoveryQuery("se-special-04", "COMPANY_BANKRUPTCY", "SPECIALIZED", "CLOTHING_INVENTORY", 'sportkläder konkursbo varulager Sverige', "SECONDARY"),
)

_SWEDISH_TO_NORWEGIAN_ALIASES: tuple[tuple[str, str], ...] = (
    ("klädbutik", "klesbutikk"),
    ("kläder", "klær"),
    ("klädparti", "klesparti"),
    ("arbetskläder", "arbeidstøy"),
    ("sportkläder", "sportsklær"),
    ("beklädnad", "bekledning"),
    ("skor", "sko"),
    ("varulager", "varelager"),
    ("varulagret", "varelager"),
    ("hela lagret", "hele lageret"),
    ("hela varulagret", "hele varelageret"),
    ("lagerparti", "vareparti"),
    ("överskottslager", "overskuddslager"),
    ("restlager", "restlager"),
    ("säljes", "selges"),
    ("till salu", "til salgs"),
    ("auktion", "auksjon"),
    ("nätauktion", "nettauksjon"),
    ("budgivning", "budrunde"),
    ("konkursbo", "konkursbo"),
    ("konkurs", "konkurs"),
    ("utförsäljning", "opphørssalg"),
    ("avveckling", "avvikling"),
    ("likvidation", "likvidasjon"),
    ("butik stänger", "butikk stenger"),
    ("läggs ned", "legges ned"),
    ("filial stänger", "filial stenger"),
    ("lager rensas", "lager ryddes"),
    ("samlad försäljning", "samlet salg"),
    ("partiförsäljning", "partisalg"),
    ("ledigt jobb", "ledig stilling"),
    ("karriär", "karriere"),
    ("webbutik", "nettbutikk"),
    ("handla nu", "handle nå"),
    ("lägg i varukorgen", "legg i handlekurv"),
)

_SWEDISH_CLOTHING_TERMS = (
    "kläder", "klädbutik", "klädparti", "arbetskläder", "sportkläder",
    "beklädnad", "skor", "textil", "mode", "plagg",
)
_SWEDISH_INVENTORY_TERMS = (
    "varulager", "varulagret", "hela lagret", "hela varulagret", "lagerparti",
    "restlager", "överskottslager", "partiförsäljning",
)
_SWEDISH_SALE_TERMS = (
    "säljes", "till salu", "auktion", "nätauktion", "budgivning",
    "utförsäljning", "samlad försäljning",
)
_SWEDISH_ENDED_TERMS = ("avslutad", "utgången", "såld", "auktionen är avslutad")
_SWEDISH_ACTIVE_TERMS = ("aktiv", "pågående", "till salu", "säljes", "budgivning")
_SWEDISH_SCENARIOS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("COMPANY_BANKRUPTCY", ("konkursbo", "konkurs")),
    ("BRANCH_CLOSURE", ("filial stänger", "filial läggs ned")),
    ("STORE_CLOSING", ("butik stänger", "klädbutik läggs ned", "utförsäljning", "avveckling")),
    ("INVENTORY_LIQUIDATION", ("lager rensas", "likvidation")),
    ("AUCTION", ("auktion", "nätauktion", "budgivning")),
    ("WAREHOUSE_SURPLUS", ("restlager", "överskottslager")),
    ("LARGE_LOT_SALE", ("lagerparti", "klädparti", "partiförsäljning", "samlad försäljning")),
)


def build_sweden_clothing_inventory_queries(
    query_budget: int = 16,
) -> tuple[DiscoveryQuery, ...]:
    """Return a bounded prefix of the Swedish query matrix."""
    if not 1 <= query_budget <= len(SWEDEN_CLOTHING_QUERY_MATRIX):
        raise ValueError(
            f"query_budget must be between 1 and {len(SWEDEN_CLOTHING_QUERY_MATRIX)}"
        )
    return SWEDEN_CLOTHING_QUERY_MATRIX[:query_budget]


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def swedish_aliases(value: str) -> tuple[str, ...]:
    """Return only aliases supported by terms explicitly present in the text."""
    text = _normalized(value)
    return tuple(
        dict.fromkeys(
            alias
            for term, alias in _SWEDISH_TO_NORWEGIAN_ALIASES
            if term in text
        )
    )


def _with_aliases(hit: SearchHit) -> SearchHit:
    aliases = swedish_aliases(f"{hit.title} {hit.description}")
    if not aliases:
        return hit
    alias_text = " ".join(aliases)
    description = f"{hit.description} | market aliases: {alias_text}".strip(" |")
    return replace(hit, description=description[:6000])


class SwedenLocalizedSearchProvider:
    """Adapt Swedish snippets to the existing conservative classifier."""

    name = "Sweden localized search"

    def __init__(self, provider: SearchProvider) -> None:
        self._provider = provider

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        return tuple(
            _with_aliases(hit)
            for hit in self._provider.search(query, count=count)
        )


def _swedish_scenario(text: str) -> str | None:
    for scenario, terms in _SWEDISH_SCENARIOS:
        if any(term in text for term in terms):
            return scenario
    return None


def verify_sweden_public_page(url: str) -> PageVerification:
    """Conservatively enrich an already verified specific Swedish item page."""
    verification = verify_public_page(url)
    text = _normalized(
        " ".join(
            value
            for value in (
                verification.title,
                verification.text,
                verification.bounded_context,
            )
            if value
        )
    )
    if (
        verification.page_role != ITEM_LISTING
        or not verification.identity_stable
        or not verification.verified
        or not text
    ):
        return verification

    clothing = any(term in text for term in _SWEDISH_CLOTHING_TERMS)
    inventory = any(term in text for term in _SWEDISH_INVENTORY_TERMS)
    sale = any(term in text for term in _SWEDISH_SALE_TERMS)
    scenario = _swedish_scenario(text)
    listing_status = verification.listing_status
    if any(term in text for term in _SWEDISH_ENDED_TERMS):
        listing_status = ENDED
    elif any(term in text for term in _SWEDISH_ACTIVE_TERMS):
        listing_status = ACTIVE

    return replace(
        verification,
        inventory_type=(
            verification.inventory_type
            or next((term for term in _SWEDISH_CLOTHING_TERMS if term in text), None)
        ),
        listing_status=listing_status,
        clothing_inventory_evidence=(
            verification.clothing_inventory_evidence or (clothing and inventory)
        ),
        sale_evidence=(
            verification.sale_evidence or (sale and (clothing or inventory))
        ),
        event_scenario=scenario or verification.event_scenario,
    )
