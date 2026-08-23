"""Authoritative project-domain boundary for discovery and learning.

The Opportunity Engine is not a general-merchandise liquidation engine. Its
commercial scope is deliberately narrow:

* CLOTHING_INVENTORY: clothing, fashion, apparel, footwear and bridal garments
  offered as commercial stock / liquidation inventory;
* FABRIC_PROCUREMENT: fabric and textile stock handled by the bounded
  procurement lane.

Everything else fails closed as OUT_OF_DOMAIN. The classifier is deterministic
and evidence-based; generic words such as stock, liquidation, lot, price or
quantity never establish project-domain relevance on their own.
"""
from __future__ import annotations

import re

CLOTHING_INVENTORY = "CLOTHING_INVENTORY"
FABRIC_PROCUREMENT = "FABRIC_PROCUREMENT"
OUT_OF_DOMAIN = "OUT_OF_DOMAIN"

_ALLOWED_CLOTHING_CATEGORIES = frozenset(
    {
        "APPAREL",
        "CLOTHING",
        "CLOTHING_INVENTORY",
        "FASHION",
        "FOOTWEAR",
        "SHOES",
        "GARMENTS",
        "WORKWEAR",
        "SPORTSWEAR",
        "BRIDAL",
        "BRIDALWEAR",
        "WEDDING_DRESSES",
    }
)
_ALLOWED_FABRIC_CATEGORIES = frozenset(
    {
        "FABRIC",
        "FABRICS",
        "TEXTILE",
        "TEXTILES",
        "FABRIC_PROCUREMENT",
        "FABRIC_DEADSTOCK",
        "TEXTILE_STOCK",
    }
)
_BLOCKED_CATEGORIES = frozenset(
    {
        "APPLIANCES",
        "BUILDING_MATERIALS",
        "ELECTRONICS",
        "FLOORING",
        "FURNITURE",
        "GENERAL_MERCHANDISE",
        "GENERAL_MERCHANDISE_STOCKLOT",
        "HARDWARE",
        "HOMEWARE",
        "HOUSEHOLD",
        "TOOLS",
    }
)

# Structured NACE evidence is stronger than a company name. Keep this bounded
# to clothing manufacture / wholesale / specialist retail codes that already
# appear in the official market-signal stream. Do not treat generic retail or
# liquidation codes as project-domain evidence.
_CLOTHING_INDUSTRY_PREFIXES = (
    "14.",
    "46.42",
    "47.71",
)

# Distinctive garment / fashion vocabulary across the six operated markets.
_CLOTHING_MARKERS = (
    "apparel",
    "clothing",
    "clothes",
    "garment",
    "garments",
    "fashion",
    "footwear",
    "shoes",
    "sportswear",
    "workwear",
    "menswear",
    "womenswear",
    "kidswear",
    "jacket",
    "jackets",
    "shirt",
    "shirts",
    "trouser",
    "trousers",
    "dress",
    "dresses",
    "jeans",
    "skirt",
    "skirts",
    "coat",
    "coats",
    "bridal",
    "wedding dress",
    "klær",
    "klaer",
    "klesbutikk",
    "klesbutikken",
    "kleslager",
    "arbeidsklær",
    "arbeidsklaer",
    "arbeidsjakke",
    "arbeidsjakker",
    "bekledning",
    "mote",
    "jakke",
    "jakker",
    "bukser",
    "skjorter",
    "kjoler",
    "sko",
    "brudekjole",
    "korsett",
    "korsettsalong",
    "kläder",
    "klader",
    "klädlager",
    "kladlager",
    "klädbutik",
    "kladbutik",
    "klädbutiken",
    "kladbutiken",
    "jackor",
    "byxor",
    "skjortor",
    "klänningar",
    "klanningar",
    "bröllopsklänning",
    "brollopsklanning",
    "kleidung",
    "bekleidung",
    "arbeitskleidung",
    "modeware",
    "modeartikel",
    "modekette",
    "mode-kette",
    "modemarke",
    "modehändler",
    "modehandler",
    "schuhe",
    "schuhen",
    "jacken",
    "hosen",
    "hemden",
    "kleider",
    "brautkleid",
    "vêtement",
    "vêtements",
    "vetement",
    "vetements",
    "habillement",
    "chaussures",
    "vestes",
    "pantalons",
    "chemises",
    "robes",
    # French product titles often name a garment family without repeating the
    # generic word "vêtements". Keep these markers deliberately compound so a
    # broad word such as "haut" cannot make unrelated pages clothing evidence.
    "haut femme",
    "hauts femme",
    "haut homme",
    "hauts homme",
    "robe de mariée",
    "robe de mariee",
    "abbigliamento",
    "vestiti",
    "calzature",
    "giacche",
    "pantaloni",
    "camicie",
    "abiti",
    "abito da sposa",
    "kleding",
    "kledingvoorraad",
    "kledingwinkel",
    "kledingwinkelvoorraad",
    "schoenen",
    "jassen",
    "broeken",
    "overhemden",
    "jurken",
    "trouwjurk",
)

_FABRIC_MARKERS = (
    "fabric",
    "fabrics",
    "fabric stock",
    "fabric deadstock",
    "textile fabric",
    "textile fabrics",
    "cloth roll",
    "cloth rolls",
    "fabric roll",
    "fabric rolls",
    "metervare",
    "metervarer",
    "stoffrull",
    "stoffruller",
    "tyg",
    "tygrulle",
    "tygrullar",
    "meterware",
    "stoffballen",
    "gewebe",
    "tissu",
    "tissus",
    "rouleau de tissu",
    "rouleaux de tissu",
    "tessuto",
    "tessuti",
    "rotolo di tessuto",
    "rotoli di tessuto",
    "stoffen",
    "stofrol",
    "stofrollen",
)

# These are diagnostic negatives only. Absence of positive project-domain
# evidence already fails closed, so this list need not enumerate every unrelated
# product category.
_OUT_OF_DOMAIN_MARKERS = (
    "appliance",
    "appliances",
    "bosch",
    "siemens",
    "electronics",
    "flooring",
    "granite",
    "granit",
    "poolkantsten",
    "poolsarg",
    "building material",
    "building materials",
    "byggematerial",
    "byggematerialer",
    "verktøy",
    "verktoy",
    "fliser",
    "trelast",
    "hardware",
    "furniture",
    "general merchandise",
)


def _compact(value: object) -> str:
    return " ".join(str(value or "").casefold().split()).strip()


def _category(value: object) -> str:
    return "_".join(str(value or "").strip().upper().replace("-", " ").split())


def _industry_code_values(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        candidates = (value,)
    elif isinstance(value, (list, tuple, set, frozenset)):
        candidates = tuple(value)
    else:
        return ()

    values: list[str] = []
    for candidate in candidates:
        normalized = _compact(candidate).replace(" ", "")
        if normalized:
            values.append(normalized)
    return tuple(values)


def _contains_clothing_industry_code(value: object) -> bool:
    return any(
        code.startswith(prefix)
        for code in _industry_code_values(value)
        for prefix in _CLOTHING_INDUSTRY_PREFIXES
    )


def _contains_marker(text: str, marker: str) -> bool:
    if not text or not marker:
        return False
    # Word boundaries based on \w are safe for Latin letters with accents and
    # prevent short markers such as "mote" or "sko" from matching inside an
    # unrelated longer token.
    return bool(re.search(rf"(?<!\w){re.escape(marker.casefold())}(?!\w)", text))


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(_contains_marker(text, marker) for marker in markers)


def classify_project_domain(
    *,
    text: object = "",
    category: object = "",
    industry_codes: object = (),
) -> str:
    """Classify evidence into the project's allowed commercial domains.

    Explicit structured categories take precedence. Bounded clothing-industry
    codes are accepted as structured evidence. Free text still requires a
    distinctive clothing/fashion or fabric/textile marker. Generic commercial
    evidence alone intentionally returns OUT_OF_DOMAIN.
    """

    normalized_category = _category(category)
    if normalized_category in _ALLOWED_CLOTHING_CATEGORIES:
        return CLOTHING_INVENTORY
    if normalized_category in _ALLOWED_FABRIC_CATEGORIES:
        return FABRIC_PROCUREMENT
    if normalized_category in _BLOCKED_CATEGORIES:
        return OUT_OF_DOMAIN
    if _contains_clothing_industry_code(industry_codes):
        return CLOTHING_INVENTORY

    combined = _compact(f"{category or ''} {text or ''}")
    if _contains_any(combined, _CLOTHING_MARKERS):
        return CLOTHING_INVENTORY
    if _contains_any(combined, _FABRIC_MARKERS):
        return FABRIC_PROCUREMENT
    if _contains_any(combined, _OUT_OF_DOMAIN_MARKERS):
        return OUT_OF_DOMAIN
    return OUT_OF_DOMAIN


def is_project_domain(
    *,
    text: object = "",
    category: object = "",
    industry_codes: object = (),
) -> bool:
    return classify_project_domain(
        text=text,
        category=category,
        industry_codes=industry_codes,
    ) in {
        CLOTHING_INVENTORY,
        FABRIC_PROCUREMENT,
    }


def is_clothing_inventory(
    *,
    text: object = "",
    category: object = "",
    industry_codes: object = (),
) -> bool:
    return (
        classify_project_domain(
            text=text,
            category=category,
            industry_codes=industry_codes,
        )
        == CLOTHING_INVENTORY
    )


def is_fabric_procurement(
    *,
    text: object = "",
    category: object = "",
    industry_codes: object = (),
) -> bool:
    return (
        classify_project_domain(
            text=text,
            category=category,
            industry_codes=industry_codes,
        )
        == FABRIC_PROCUREMENT
    )
