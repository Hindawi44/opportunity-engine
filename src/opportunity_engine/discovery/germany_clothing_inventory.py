"""Bounded German Clothing Inventory discovery configuration.

The Germany foundation reuses the validated conservative discovery engine.
German snippets receive Norwegian aliases only for terms explicitly present in
the source text, so market vocabulary remains outside the core classifier.
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


GERMANY_CLOTHING_QUERY_MATRIX: tuple[DiscoveryQuery, ...] = (
    DiscoveryQuery("de-sale-01", "INVENTORY_LIQUIDATION", "SALE_INTENT", "CLOTHING_INVENTORY", 'Bekleidungsgeschäft Warenbestand zu verkaufen Deutschland -gesucht -jobs -onlineshop'),
    DiscoveryQuery("de-sale-02", "LARGE_LOT_SALE", "SALE_INTENT", "CLOTHING_INVENTORY", 'gesamter Lagerbestand Kleidung zu verkaufen Deutschland -gesucht -jobs'),
    DiscoveryQuery("de-sale-03", "AUCTION", "SALE_INTENT", "CLOTHING_INVENTORY", 'Bekleidung Warenbestand Versteigerung Deutschland -jobs -onlineshop'),
    DiscoveryQuery("de-sale-04", "WAREHOUSE_SURPLUS", "SALE_INTENT", "CLOTHING_INVENTORY", 'Restposten Bekleidung zu verkaufen Deutschland -gesucht -jobs'),
    DiscoveryQuery("de-sale-05", "COMPANY_BANKRUPTCY", "SALE_INTENT", "CLOTHING_INVENTORY", 'Insolvenzversteigerung Kleidung Warenbestand Deutschland -jobs'),
    DiscoveryQuery("de-sale-06", "STORE_CLOSING", "SALE_INTENT", "CLOTHING_INVENTORY", 'Räumungsverkauf Bekleidungsgeschäft kompletter Bestand Deutschland -jobs'),
    DiscoveryQuery("de-lead-01", "COMPANY_BANKRUPTCY", "EVENT_LEAD", "CLOTHING_INVENTORY", 'Insolvenz Bekleidungsgeschäft Warenlager Deutschland -jobs'),
    DiscoveryQuery("de-lead-02", "STORE_CLOSING", "EVENT_LEAD", "CLOTHING_INVENTORY", 'Geschäftsauflösung Modegeschäft Warenbestand Deutschland -jobs'),
    DiscoveryQuery("de-lead-03", "STORE_CLOSING", "EVENT_LEAD", "CLOTHING_INVENTORY", 'Bekleidungsgeschäft schließt Lagerbestand Deutschland -jobs'),
    DiscoveryQuery("de-lead-04", "BRANCH_CLOSURE", "EVENT_LEAD", "CLOTHING_INVENTORY", 'Filialschließung Modegeschäft Warenbestand Deutschland -jobs'),
    DiscoveryQuery("de-lead-05", "INVENTORY_LIQUIDATION", "EVENT_LEAD", "CLOTHING_INVENTORY", 'Lagerauflösung Bekleidung Deutschland -jobs'),
    DiscoveryQuery("de-lead-06", "STORE_CLOSING", "EVENT_LEAD", "CLOTHING_INVENTORY", 'Betriebsaufgabe Textilhandel Warenbestand Deutschland -jobs'),
    DiscoveryQuery("de-special-01", "INVENTORY_LIQUIDATION", "SPECIALIZED", "CLOTHING_INVENTORY", '"kompletter Warenbestand" Bekleidung Versteigerung Deutschland', "SECONDARY"),
    DiscoveryQuery("de-special-02", "LARGE_LOT_SALE", "SPECIALIZED", "CLOTHING_INVENTORY", '"großer Bekleidungsposten" zu verkaufen Deutschland', "SECONDARY"),
    DiscoveryQuery("de-special-03", "WAREHOUSE_SURPLUS", "SPECIALIZED", "CLOTHING_INVENTORY", 'Arbeitskleidung Restposten Konvolut Deutschland', "SECONDARY"),
    DiscoveryQuery("de-special-04", "COMPANY_BANKRUPTCY", "SPECIALIZED", "CLOTHING_INVENTORY", 'Sportbekleidung Insolvenz Warenlager Deutschland', "SECONDARY"),
)

_GERMAN_TO_NORWEGIAN_ALIASES: tuple[tuple[str, str], ...] = (
    ("bekleidungsgeschäft", "klesbutikk"),
    ("modegeschäft", "klesbutikk"),
    ("bekleidung", "klær"),
    ("kleidung", "klær"),
    ("arbeitskleidung", "arbeidstøy"),
    ("sportbekleidung", "sportsklær"),
    ("textilien", "tekstiler"),
    ("schuhe", "sko"),
    ("warenbestand", "varelager"),
    ("lagerbestand", "varelager"),
    ("warenlager", "varelager"),
    ("gesamter lagerbestand", "hele lageret"),
    ("kompletter warenbestand", "hele varelageret"),
    ("restposten", "restlager"),
    ("sonderposten", "overskuddslager"),
    ("lagerposten", "vareparti"),
    ("bekleidungsposten", "klesparti"),
    ("textilposten", "vareparti"),
    ("zu verkaufen", "til salgs"),
    ("versteigerung", "auksjon"),
    ("auktion", "auksjon"),
    ("gebotsabgabe", "budrunde"),
    ("aktuelles gebot", "budrunde"),
    ("insolvenzversteigerung", "konkursauksjon"),
    ("insolvenz", "konkurs"),
    ("räumungsverkauf", "opphørssalg"),
    ("geschäftsauflösung", "avvikling"),
    ("betriebsaufgabe", "avvikling"),
    ("liquidation", "likvidasjon"),
    ("bekleidungsgeschäft schliesst", "butikk stenger"),
    ("filialschliessung", "filial stenger"),
    ("lagerauflösung", "lager ryddes"),
    ("gesamtverkauf", "samlet salg"),
    ("postenverkauf", "partisalg"),
    ("auktion beendet", "auksjonen er avsluttet"),
    ("versteigerung beendet", "auksjonen er avsluttet"),
    ("gebotsabgabe beendet", "auksjonen er avsluttet"),
    ("abgeschlossen", "avsluttet"),
    ("verkauft", "solgt"),
    ("zuschlag erteilt", "solgt"),
    ("stellenangebot", "ledig stilling"),
    ("karriere", "karriere"),
    ("onlineshop", "nettbutikk"),
    ("jetzt kaufen", "handle nå"),
    ("in den warenkorb", "legg i handlekurv"),
)

_GERMAN_CLOTHING_TERMS = (
    "bekleidung", "kleidung", "bekleidungsgeschäft", "modegeschäft",
    "arbeitskleidung", "sportbekleidung", "textilien", "schuhe", "accessoires",
    "mode", "lederbekleidung", "jacken", "hosen",
)
_GERMAN_INVENTORY_TERMS = (
    "warenbestand", "lagerbestand", "warenlager", "gesamter lagerbestand",
    "kompletter warenbestand", "restposten", "sonderposten", "lagerposten",
    "bekleidungsposten", "kleidungsposten", "textilposten", "konvolut",
    "posten bekleidung", "paletten", "kartons",
)
_GERMAN_SALE_TERMS = (
    "zu verkaufen", "versteigerung", "auktion", "gebotsabgabe",
    "räumungsverkauf", "gesamtverkauf", "postenverkauf", "aktuelles gebot",
    "jetzt bieten", "zuschläge ab",
)
_GERMAN_ENDED_TERMS = (
    "auktion beendet", "versteigerung beendet", "gebotsabgabe beendet",
    "versteigerung abgeschlossen", "abgeschlossen", "verkauft",
    "zuschlag erteilt", "beendet",
)
_GERMAN_ACTIVE_TERMS = (
    "endet am", "zuschläge ab", "gebot abgeben", "aktuelles gebot",
    "jetzt bieten", "laufend", "aktiv", "zu verkaufen",
)
_GERMAN_SCENARIOS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("COMPANY_BANKRUPTCY", ("insolvenzversteigerung", "insolvenz", "insolvenzverfahren")),
    ("BRANCH_CLOSURE", ("filialschliessung", "filiale schliesst")),
    ("STORE_CLOSING", ("geschäftsauflösung", "betriebsaufgabe", "räumungsverkauf", "geschäftsschliessung")),
    ("INVENTORY_LIQUIDATION", ("lagerauflösung", "liquidation")),
    ("AUCTION", ("versteigerung", "auktion", "gebotsabgabe", "jetzt bieten")),
    ("WAREHOUSE_SURPLUS", ("restposten", "sonderposten", "überbestand")),
    ("LARGE_LOT_SALE", ("lagerposten", "bekleidungsposten", "kleidungsposten", "textilposten", "konvolut", "postenverkauf")),
)


def build_germany_clothing_inventory_queries(
    query_budget: int = 16,
) -> tuple[DiscoveryQuery, ...]:
    """Return a bounded prefix of the German query matrix."""
    if not 1 <= query_budget <= len(GERMANY_CLOTHING_QUERY_MATRIX):
        raise ValueError(
            f"query_budget must be between 1 and {len(GERMANY_CLOTHING_QUERY_MATRIX)}"
        )
    return GERMANY_CLOTHING_QUERY_MATRIX[:query_budget]


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def german_aliases(value: str) -> tuple[str, ...]:
    """Return aliases supported by German terms explicitly present in the text."""
    text = _normalized(value)
    return tuple(
        dict.fromkeys(
            alias
            for term, alias in _GERMAN_TO_NORWEGIAN_ALIASES
            if term in text
        )
    )


def _with_aliases(hit: SearchHit) -> SearchHit:
    aliases = german_aliases(f"{hit.title} {hit.description}")
    if not aliases:
        return hit
    alias_text = " ".join(aliases)
    description = f"{hit.description} | market aliases: {alias_text}".strip(" |")
    return replace(hit, description=description[:6000])


class GermanyLocalizedSearchProvider:
    """Adapt German snippets to the existing conservative classifier."""

    name = "Germany localized search"

    def __init__(self, provider: SearchProvider) -> None:
        self._provider = provider

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        return tuple(
            _with_aliases(hit)
            for hit in self._provider.search(query, count=count)
        )


def _german_scenario(text: str) -> str | None:
    for scenario, terms in _GERMAN_SCENARIOS:
        if any(term in text for term in terms):
            return scenario
    return None


def enrich_germany_page_verification(
    verification: PageVerification,
) -> PageVerification:
    """Apply German vocabulary to a verified, specific public item page."""
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

    clothing = any(term in text for term in _GERMAN_CLOTHING_TERMS)
    inventory = any(term in text for term in _GERMAN_INVENTORY_TERMS)
    sale = any(term in text for term in _GERMAN_SALE_TERMS)
    scenario = _german_scenario(text)
    listing_status = verification.listing_status
    if any(term in text for term in _GERMAN_ENDED_TERMS):
        listing_status = ENDED
    elif any(term in text for term in _GERMAN_ACTIVE_TERMS):
        listing_status = ACTIVE

    return replace(
        verification,
        inventory_type=(
            verification.inventory_type
            or next((term for term in _GERMAN_CLOTHING_TERMS if term in text), None)
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


def verify_germany_public_page(url: str) -> PageVerification:
    """Conservatively enrich an already verified specific German item page."""
    return enrich_germany_page_verification(verify_public_page(url))
