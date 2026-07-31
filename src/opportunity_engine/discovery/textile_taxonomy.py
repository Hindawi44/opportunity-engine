"""Canonical textile and sewing opportunity taxonomy V1.

The taxonomy is deliberately independent from ranking and financial analysis. It
classifies public text into stable in-sector categories, records the matched
commercial, sector, inventory, and rejection signals, and produces a
machine-readable audit without changing lifecycle, Top 5, alerts, or purchase
decisions.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "textile-sewing-opportunity-taxonomy-v1"


class OpportunityCategory(StrEnum):
    SMALL_CLOTHING_STORE_LIQUIDATION = "SMALL_CLOTHING_STORE_LIQUIDATION"
    CLOTHING_CHAIN_OR_BRANCH_CLOSURE = "CLOTHING_CHAIN_OR_BRANCH_CLOSURE"
    BRAND_INVENTORY_LIQUIDATION = "BRAND_INVENTORY_LIQUIDATION"
    CLOTHING_INVENTORY = "CLOTHING_INVENTORY"
    SHOES_BAGS_ACCESSORIES_INVENTORY = "SHOES_BAGS_ACCESSORIES_INVENTORY"
    FABRIC_TEXTILE_STOCK = "FABRIC_TEXTILE_STOCK"
    TAILOR_WORKSHOP_LIQUIDATION = "TAILOR_WORKSHOP_LIQUIDATION"
    SEWING_ATELIER_LIQUIDATION = "SEWING_ATELIER_LIQUIDATION"
    SEWING_FACTORY_LIQUIDATION = "SEWING_FACTORY_LIQUIDATION"
    SEWING_MACHINERY = "SEWING_MACHINERY"
    HABERDASHERY_AND_NOTIONS = "HABERDASHERY_AND_NOTIONS"
    CLOTHING_STORE_FIXTURES = "CLOTHING_STORE_FIXTURES"


PRIMARY_CATEGORIES = frozenset(
    category
    for category in OpportunityCategory
    if category is not OpportunityCategory.CLOTHING_STORE_FIXTURES
)
SECONDARY_CATEGORIES = frozenset({OpportunityCategory.CLOTHING_STORE_FIXTURES})


_EVENT_TERMS: dict[str, tuple[str, ...]] = {
    "BANKRUPTCY": ("konkurs", "konkursbo", "tvangsavvikling", "insolvens"),
    "CLOSURE": (
        "opphør",
        "opphørssalg",
        "avvikling",
        "avvikles",
        "legges ned",
        "butikk stenger",
        "butikken stenger",
        "filial stenger",
        "avdeling stenger",
        "nedlagt",
        "nedlegges",
    ),
    "LIQUIDATION": (
        "lageravvikling",
        "likvidasjon",
        "tømmesalg",
        "hele lageret selges",
        "alt skal bort",
    ),
    "AUCTION": ("auksjon", "nettauksjon", "budrunde", "budfrist"),
    "SURPLUS": ("restlager", "overskuddslager", "overskuddsvarer"),
    "SALE": ("til salgs", "selges", "partisalg", "samlet salg", "overtas"),
}
_STRONG_EVENT_KINDS = frozenset(
    {"BANKRUPTCY", "CLOSURE", "LIQUIDATION", "AUCTION", "SURPLUS"}
)

_GENERIC_INVENTORY_TERMS = (
    "varelager",
    "lagerbeholdning",
    "hele lageret",
    "hele varelageret",
    "komplett lager",
    "restlager",
    "overskuddslager",
    "vareparti",
    "parti med",
    "stort parti",
    "samlet parti",
)

_CLOTHING_RETAIL_TERMS = (
    "klesbutikk",
    "motebutikk",
    "bekledningsbutikk",
    "butikk for klær",
    "boutique",
    "butikk med klær",
)
_CHAIN_BRAND_TERMS = (
    "kleskjede",
    "butikkjede",
    "filial",
    "butikkavdeling",
    "merkevare",
    "merkevarer",
    "klesmerke",
)
_CLOTHING_GOODS_TERMS = (
    "klær",
    "bekledning",
    "plagg",
    "arbeidstøy",
    "sportsklær",
    "brudekjoler",
    "bunad",
    "undertøy",
    "klesparti",
)
_ACCESSORY_TERMS = (
    "sko",
    "vesker",
    "håndvesker",
    "belter",
    "hodeplagg",
    "moteaccessoirer",
    "moteaccessories",
    "tilbehør til klær",
)
_FABRIC_TERMS = (
    "stoff",
    "stofflager",
    "metervare",
    "tekstiler",
    "tekstilparti",
    "stoffruller",
    "stoffrull",
    "fôrstoff",
    "skinnlager",
    "lærparti",
)
_TAILOR_TERMS = ("skredder", "skredderi", "skredderverksted", "sømverksted")
_ATELIER_TERMS = ("systue", "syatelier", "sy-atelier", "systudio", "sømstudio")
_FACTORY_TERMS = (
    "klesproduksjon",
    "konfeksjon",
    "konfeksjonsfabrikk",
    "tekstilfabrikk",
    "syfabrikk",
    "produksjonsverksted",
)
_MACHINERY_TERMS = (
    "industrisymaskin",
    "industrisymaskiner",
    "symaskin",
    "symaskiner",
    "overlock",
    "interlock",
    "blindstingsmaskin",
    "skjærebord",
    "presseutstyr",
    "dampgenerator",
)
_NOTIONS_TERMS = (
    "sytråd",
    "glidelås",
    "glidelåser",
    "knapper",
    "synåler",
    "strikk",
    "kantbånd",
    "sytilbehør",
    "sømtilbehør",
    "kortvarer",
)
_FIXTURE_TERMS = (
    "mannekeng",
    "mannequin",
    "klesstativ",
    "butikkstativ",
    "utstillingsstativ",
    "prøverom",
    "butikkinnredning",
    "kleshengere",
    "displaybord",
    "lagerreol",
    "pallereol",
)

_UNRELATED_SECTOR_TERMS: dict[str, tuple[str, ...]] = {
    "KITCHEN_OR_FURNITURE": (
        "kjøkken",
        "kjøkkenproduksjon",
        "møbelproduksjon",
        "møbelplater",
        "kontormøbler",
    ),
    "CONSTRUCTION": ("byggematerialer", "trelast", "anleggsutstyr"),
    "SCHOOL_STORAGE": ("skoleinventar", "elevskap", "skoleskap", "skolegarderobe"),
    "VEHICLE_WORKSHOP": ("bilverksted", "bildeler", "dekkverksted"),
    "AGRICULTURE": ("landbruksmaskin", "landbruksmaskiner", "traktor"),
    "GENERIC_STORAGE": ("garderobeskap", "lagerreoler", "pallereoler"),
}

_CATEGORY_PRIORITY: tuple[OpportunityCategory, ...] = (
    OpportunityCategory.CLOTHING_CHAIN_OR_BRANCH_CLOSURE,
    OpportunityCategory.SMALL_CLOTHING_STORE_LIQUIDATION,
    OpportunityCategory.TAILOR_WORKSHOP_LIQUIDATION,
    OpportunityCategory.SEWING_ATELIER_LIQUIDATION,
    OpportunityCategory.SEWING_FACTORY_LIQUIDATION,
    OpportunityCategory.BRAND_INVENTORY_LIQUIDATION,
    OpportunityCategory.FABRIC_TEXTILE_STOCK,
    OpportunityCategory.SEWING_MACHINERY,
    OpportunityCategory.HABERDASHERY_AND_NOTIONS,
    OpportunityCategory.SHOES_BAGS_ACCESSORIES_INVENTORY,
    OpportunityCategory.CLOTHING_INVENTORY,
    OpportunityCategory.CLOTHING_STORE_FIXTURES,
)


@dataclass(frozen=True, slots=True)
class TaxonomyDecision:
    status: str
    primary_category: str | None
    primary_tier: str | None
    matched_categories: tuple[str, ...]
    event_signals: tuple[str, ...]
    sector_signals: tuple[str, ...]
    inventory_signals: tuple[str, ...]
    rejection_signals: tuple[str, ...]
    reason: str
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in (
            "matched_categories",
            "event_signals",
            "sector_signals",
            "inventory_signals",
            "rejection_signals",
        ):
            payload[key] = list(payload[key])
        return payload


def _normalize(*parts: object) -> str:
    return " ".join(" ".join(str(part).casefold().split()) for part in parts if part)


def _matched_phrases(text: str, phrases: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(phrase for phrase in phrases if phrase.casefold() in text))


def _named_matches(text: str, groups: Mapping[str, tuple[str, ...]]) -> tuple[str, ...]:
    matches: list[str] = []
    for group, phrases in groups.items():
        matches.extend(f"{group}:{phrase}" for phrase in _matched_phrases(text, phrases))
    return tuple(matches)


def classify_textile_opportunity(title: str, description: str = "") -> TaxonomyDecision:
    """Classify public text without changing opportunity lifecycle or economics."""
    text = _normalize(title, description)
    if not text:
        return TaxonomyDecision(
            status="OUT_OF_SCOPE",
            primary_category=None,
            primary_tier=None,
            matched_categories=(),
            event_signals=(),
            sector_signals=(),
            inventory_signals=(),
            rejection_signals=(),
            reason="missing title and description",
        )

    event_signals = _named_matches(text, _EVENT_TERMS)
    event_kinds = {signal.split(":", 1)[0] for signal in event_signals}
    has_strong_event = bool(event_kinds & _STRONG_EVENT_KINDS)
    has_sale_event = "SALE" in event_kinds

    inventory_matches = _matched_phrases(text, _GENERIC_INVENTORY_TERMS)
    clothing_retail = _matched_phrases(text, _CLOTHING_RETAIL_TERMS)
    chain_brand = _matched_phrases(text, _CHAIN_BRAND_TERMS)
    clothing_goods = _matched_phrases(text, _CLOTHING_GOODS_TERMS)
    accessories = _matched_phrases(text, _ACCESSORY_TERMS)
    fabrics = _matched_phrases(text, _FABRIC_TERMS)
    tailor = _matched_phrases(text, _TAILOR_TERMS)
    atelier = _matched_phrases(text, _ATELIER_TERMS)
    factory = _matched_phrases(text, _FACTORY_TERMS)
    machinery = _matched_phrases(text, _MACHINERY_TERMS)
    notions = _matched_phrases(text, _NOTIONS_TERMS)
    fixtures = _matched_phrases(text, _FIXTURE_TERMS)

    sector_signals = tuple(
        dict.fromkeys((*clothing_retail, *chain_brand, *tailor, *atelier, *factory))
    )
    inventory_signals = tuple(
        dict.fromkeys(
            (
                *inventory_matches,
                *clothing_goods,
                *accessories,
                *fabrics,
                *machinery,
                *notions,
                *fixtures,
            )
        )
    )
    rejection_signals = _named_matches(text, _UNRELATED_SECTOR_TERMS)

    categories: set[OpportunityCategory] = set()
    if chain_brand and (clothing_retail or clothing_goods) and has_strong_event:
        categories.add(OpportunityCategory.CLOTHING_CHAIN_OR_BRANCH_CLOSURE)
    if clothing_retail and has_strong_event and not chain_brand:
        categories.add(OpportunityCategory.SMALL_CLOTHING_STORE_LIQUIDATION)
    if chain_brand and (clothing_goods or accessories) and (
        inventory_matches or has_strong_event
    ):
        categories.add(OpportunityCategory.BRAND_INVENTORY_LIQUIDATION)
    if clothing_goods and inventory_matches:
        categories.add(OpportunityCategory.CLOTHING_INVENTORY)
    if accessories and inventory_matches:
        categories.add(OpportunityCategory.SHOES_BAGS_ACCESSORIES_INVENTORY)
    if fabrics and (inventory_matches or has_strong_event):
        categories.add(OpportunityCategory.FABRIC_TEXTILE_STOCK)
    if tailor and has_strong_event:
        categories.add(OpportunityCategory.TAILOR_WORKSHOP_LIQUIDATION)
    if atelier and has_strong_event:
        categories.add(OpportunityCategory.SEWING_ATELIER_LIQUIDATION)
    if factory and has_strong_event:
        categories.add(OpportunityCategory.SEWING_FACTORY_LIQUIDATION)
    if machinery and (inventory_matches or has_strong_event or has_sale_event):
        categories.add(OpportunityCategory.SEWING_MACHINERY)
    if notions and (inventory_matches or has_strong_event):
        categories.add(OpportunityCategory.HABERDASHERY_AND_NOTIONS)

    explicit_textile_business = bool(
        clothing_retail
        or clothing_goods
        or accessories
        or fabrics
        or tailor
        or atelier
        or factory
    )
    if fixtures and explicit_textile_business and (
        inventory_matches or has_strong_event or has_sale_event
    ):
        categories.add(OpportunityCategory.CLOTHING_STORE_FIXTURES)

    ordered_categories = tuple(
        category for category in _CATEGORY_PRIORITY if category in categories
    )
    if not ordered_categories:
        if rejection_signals:
            reason = "unrelated-sector signal without qualifying textile evidence"
        elif not has_strong_event and not inventory_matches:
            reason = "no liquidation event or commercial inventory signal"
        else:
            reason = "no qualifying clothing, textile, tailoring, or sewing category"
        return TaxonomyDecision(
            status="OUT_OF_SCOPE",
            primary_category=None,
            primary_tier=None,
            matched_categories=(),
            event_signals=event_signals,
            sector_signals=sector_signals,
            inventory_signals=inventory_signals,
            rejection_signals=rejection_signals,
            reason=reason,
        )

    primary = ordered_categories[0]
    tier = "PRIMARY" if primary in PRIMARY_CATEGORIES else "SECONDARY"
    reason = "qualified textile-sector category signals found"
    if rejection_signals:
        reason += "; unrelated co-signals retained for human review"
    return TaxonomyDecision(
        status="IN_SCOPE",
        primary_category=primary.value,
        primary_tier=tier,
        matched_categories=tuple(category.value for category in ordered_categories),
        event_signals=event_signals,
        sector_signals=sector_signals,
        inventory_signals=inventory_signals,
        rejection_signals=rejection_signals,
        reason=reason,
    )


def build_textile_taxonomy_audit(
    candidates: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a detached audit, including a valid zero-candidate result."""
    decisions: list[dict[str, Any]] = []
    category_counts = {category.value: 0 for category in OpportunityCategory}
    included_count = 0

    for index, candidate in enumerate(candidates):
        title = str(candidate.get("title") or "")
        description = str(candidate.get("description") or candidate.get("text") or "")
        decision = classify_textile_opportunity(title, description)
        if decision.status == "IN_SCOPE":
            included_count += 1
            for category in decision.matched_categories:
                category_counts[category] += 1
        decisions.append(
            {
                "candidate_id": str(
                    candidate.get("candidate_id")
                    or candidate.get("opportunity_id")
                    or candidate.get("url")
                    or f"candidate-{index + 1}"
                ),
                "title": title,
                "source": candidate.get("source"),
                "url": candidate.get("url"),
                "taxonomy": decision.to_dict(),
            }
        )

    candidate_count = len(decisions)
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate_count": candidate_count,
        "included_count": included_count,
        "rejected_count": candidate_count - included_count,
        "category_counts": category_counts,
        "decisions": decisions,
        "scope": {
            "changes_lifecycle": False,
            "changes_scoring": False,
            "changes_ranking": False,
            "changes_top5": False,
            "changes_alerts": False,
            "changes_persistence": False,
            "automatic_contact": False,
            "automatic_purchase": False,
        },
    }
