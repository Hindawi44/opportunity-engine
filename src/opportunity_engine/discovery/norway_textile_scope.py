"""Norway-specific vocabulary adapter for the canonical textile taxonomy."""
from __future__ import annotations

import re

from opportunity_engine.discovery.textile_taxonomy import (
    SCHEMA_VERSION,
    OpportunityCategory,
    TaxonomyDecision,
    classify_textile_opportunity,
)


_CLOSURE_TERMS = (
    "opphør", "opphørssalg", "avvikling", "avvikles", "stenger",
    "legges ned", "nedlegges", "nedlagt", "filial stenger",
)
_INVENTORY_EVENT_TERMS = (
    "konkurs", "konkursbo", "restlager", "overskuddslager", "varelager",
    "lageravvikling", "tømmesalg", "selges", "til salgs", "auksjon",
)
_DIRECT_SALE_TERMS = ("selges", "til salgs", "auksjon", "budrunde")
_LOT_TERMS = (
    "vareparti", "klesparti", "parti med", "stort parti", "samlet parti",
    "restlager", "overskuddslager", "varelager", "hele lageret",
)
_CLOTHING_GOODS_TERMS = (
    "klær", "arbeidsklær", "arbeidstøy", "arbeidsjakke", "arbeidsjakker",
    "jakker", "bukser", "skjorter", "gensere", "kjoler", "brudekjoler",
    "sportsklær", "bekledning", "plagg",
)
_CLOTHING_STORE_TERMS = ("klesbutikk", "motebutikk", "bekledningsbutikk")
_CHAIN_TERMS = ("kleskjede", "butikkjede", "filial", "butikkavdeling")
_BRAND_TERMS = ("klesmerke", "merkevare", "merkevarer")
_QUANTITY_LOT = re.compile(r"\b\d{2,6}\s*(?:stk|plagg|varer|enheter|par)\b")


def _matches(text: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(term for term in terms if term in text)


def classify_norway_textile_opportunity(
    title: str,
    description: str = "",
) -> TaxonomyDecision:
    """Apply conservative Norwegian aliases after the canonical taxonomy.

    The adapter fills explicit local-language gaps for clothing lots,
    clothing-store inventory, clothing chains, and clothing brands. It never
    converts a generic liquidation or an ordinary single garment into textile
    inventory scope.
    """
    decision = classify_textile_opportunity(title, description)
    if decision.status == "IN_SCOPE":
        return decision

    text = " ".join(f"{title} {description}".casefold().split())
    closure_hits = _matches(text, _CLOSURE_TERMS)
    inventory_hits = _matches(text, _INVENTORY_EVENT_TERMS)
    direct_sale_hits = _matches(text, _DIRECT_SALE_TERMS)
    lot_hits = _matches(text, _LOT_TERMS)
    goods_hits = _matches(text, _CLOTHING_GOODS_TERMS)
    store_hits = _matches(text, _CLOTHING_STORE_TERMS)
    chain_hits = _matches(text, _CHAIN_TERMS)
    brand_hits = _matches(text, _BRAND_TERMS)
    quantity_lot = _QUANTITY_LOT.search(text) is not None

    # Preserve real public clothing-lot cases without admitting ordinary
    # single-item listings. Clothing goods need a lot phrase or a multi-item
    # quantity together with an auction/sale signal.
    if goods_hits and (
        lot_hits
        or (quantity_lot and direct_sale_hits)
    ):
        category = OpportunityCategory.CLOTHING_INVENTORY.value
        event_signals = tuple(
            f"AUCTION:{term}" if term == "auksjon" else f"SALE:{term}"
            for term in direct_sale_hits
        )
        if not event_signals:
            event_signals = tuple(
                f"INVENTORY_EVENT:{term}" for term in inventory_hits
            )
        inventory_signals = tuple(
            dict.fromkeys((*lot_hits, *goods_hits, "multi_item_quantity" if quantity_lot else ""))
        )
        return TaxonomyDecision(
            status="IN_SCOPE",
            primary_category=category,
            primary_tier="PRIMARY",
            matched_categories=(category,),
            event_signals=event_signals,
            sector_signals=goods_hits,
            inventory_signals=tuple(value for value in inventory_signals if value),
            rejection_signals=decision.rejection_signals,
            reason="explicit Norwegian multi-item clothing lot signals found",
            schema_version=SCHEMA_VERSION,
        )

    if store_hits and inventory_hits and direct_sale_hits:
        category = OpportunityCategory.CLOTHING_INVENTORY.value
        return TaxonomyDecision(
            status="IN_SCOPE",
            primary_category=category,
            primary_tier="PRIMARY",
            matched_categories=(category,),
            event_signals=tuple(f"SALE:{term}" for term in direct_sale_hits),
            sector_signals=store_hits,
            inventory_signals=inventory_hits,
            rejection_signals=decision.rejection_signals,
            reason="explicit Norwegian clothing-store inventory sale signals found",
            schema_version=SCHEMA_VERSION,
        )

    if chain_hits and closure_hits:
        category = OpportunityCategory.CLOTHING_CHAIN_OR_BRANCH_CLOSURE.value
        return TaxonomyDecision(
            status="IN_SCOPE",
            primary_category=category,
            primary_tier="PRIMARY",
            matched_categories=(category,),
            event_signals=tuple(f"CLOSURE:{term}" for term in closure_hits),
            sector_signals=chain_hits,
            inventory_signals=inventory_hits,
            rejection_signals=decision.rejection_signals,
            reason="explicit Norwegian clothing-chain closure signals found",
            schema_version=SCHEMA_VERSION,
        )

    if brand_hits and inventory_hits:
        category = OpportunityCategory.BRAND_INVENTORY_LIQUIDATION.value
        return TaxonomyDecision(
            status="IN_SCOPE",
            primary_category=category,
            primary_tier="PRIMARY",
            matched_categories=(category,),
            event_signals=tuple(f"INVENTORY_EVENT:{term}" for term in inventory_hits),
            sector_signals=brand_hits,
            inventory_signals=inventory_hits,
            rejection_signals=decision.rejection_signals,
            reason="explicit Norwegian clothing-brand inventory signals found",
            schema_version=SCHEMA_VERSION,
        )

    return decision
