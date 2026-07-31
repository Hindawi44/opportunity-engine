"""Norway-specific vocabulary adapter for the canonical textile taxonomy."""
from __future__ import annotations

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
_CHAIN_TERMS = ("kleskjede", "butikkjede", "filial", "butikkavdeling")
_BRAND_TERMS = ("klesmerke", "merkevare", "merkevarer")


def _matches(text: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(term for term in terms if term in text)


def classify_norway_textile_opportunity(
    title: str,
    description: str = "",
) -> TaxonomyDecision:
    """Apply conservative Norwegian aliases after the canonical taxonomy.

    The adapter only fills two explicit local-language gaps: clothing chains and
    clothing brands. It never converts a generic liquidation into textile scope.
    """
    decision = classify_textile_opportunity(title, description)
    if decision.status == "IN_SCOPE":
        return decision

    text = " ".join(f"{title} {description}".casefold().split())
    closure_hits = _matches(text, _CLOSURE_TERMS)
    inventory_hits = _matches(text, _INVENTORY_EVENT_TERMS)
    chain_hits = _matches(text, _CHAIN_TERMS)
    brand_hits = _matches(text, _BRAND_TERMS)

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
