"""Correct Stock-Hurt sale mode and product-brand extraction.

The official product HTML contains global navigation text, including links to
auctions and unrelated product names. This compatibility hook keeps the existing
source parser and redirect recovery, then applies two source-specific rules:

* the catalogue that discovered a product is authoritative for sale mode;
* brands come only from the product title or an explicit product-level Brand field.
"""
from __future__ import annotations

import re
from typing import Any

from opportunity_engine.discovery import stockhurt_official_catalog_enrichment as target
from opportunity_engine.discovery import stockhurt_redirect_partial_recovery as recovery

PATCH_SCHEMA_VERSION = "stockhurt-official-catalog-enrichment-1.2"
_INSTALLED = False
_ORIGINAL_CANDIDATE = target.stockhurt_candidate_from_product_html

_FIELD_STOP_RE = re.compile(
    r"\b(?:category|unit|grade|condition|price|current\s+bid|quantity|minimum|"
    r"weight|sku|product\s+code|availability|shipping|delivery|description)\s*:",
    re.IGNORECASE,
)
_EXPLICIT_BRAND_RE = re.compile(
    r"\bbrand\s*[:\-]\s*(?P<brand>.+?)(?="
    r"\b(?:category|unit|grade|condition|price|current\s+bid|quantity|minimum|"
    r"weight|sku|product\s+code|availability|shipping|delivery|description)\s*:|$)",
    re.IGNORECASE,
)
_TITLE_BREAK_RE = re.compile(
    r"\b(?:premium\s+)?(?:grade\s*[ABC]\b|women'?s\s+|men'?s\s+|kids'?\s+|"
    r"children'?s\s+)?(?:clothing|clothes|jackets?|coats?|dresses?|shirts?|"
    r"trousers?|pants?|jeans|shoes?|footwear|accessories|stock|mix|lot|pallet)\b",
    re.IGNORECASE,
)
_UNIT_SUFFIX_RE = re.compile(
    r"\s*\((?:kg|pcs?|pieces?|units?|items?|pairs?|sets?)\)\s*$",
    re.IGNORECASE,
)
_NOISY_WORDS = {
    "available",
    "careful",
    "category",
    "characterized",
    "clothes",
    "clothing",
    "condition",
    "delivery",
    "finishing",
    "grade",
    "included",
    "new",
    "packaged",
    "prices",
    "products",
    "quality",
    "quoted",
    "shipping",
    "unit",
    "workmanship",
}
_GENERIC_VALUES = {
    "apparel",
    "brand",
    "clothes",
    "clothing",
    "fashion",
    "jackets",
    "mix",
    "premium",
    "stock",
    "wholesale",
}


def _clean_brand_value(raw: str) -> str | None:
    value = target._compact(raw)
    if not value:
        return None
    value = _FIELD_STOP_RE.split(value, maxsplit=1)[0]
    value = value.strip(" \t\r\n,;:|.-_()[]{}⭐★")
    value = re.sub(r"\s+", " ", value)
    if not value or len(value) > 60:
        return None
    words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9&'+.-]+", value)
    if not 1 <= len(words) <= 6:
        return None
    folded_words = {word.casefold().strip(".'+-") for word in words}
    if value.casefold() in _GENERIC_VALUES:
        return None
    if folded_words & _NOISY_WORDS:
        return None
    if not any(any(char.isalpha() for char in word) for word in words):
        return None
    return value


def _brand_from_title(title: str) -> str | None:
    value = _UNIT_SUFFIX_RE.sub("", target._compact(title))
    match = _TITLE_BREAK_RE.search(value)
    if match:
        value = value[: match.start()]
    value = re.sub(r"\bgrade\s*[ABC]\b.*$", "", value, flags=re.IGNORECASE)
    return _clean_brand_value(value)


def extract_official_product_brands(*, title: str, html_text: str) -> list[str]:
    """Return product-level brands without footer or navigation contamination."""
    _, text, _, _ = target._product_document(
        html_text=html_text,
        source_url="https://stockhurt.com/en/product/brand-cleanup/",
    )
    brands: list[str] = []
    title_brand = _brand_from_title(title)
    if title_brand:
        brands.append(title_brand)
    for match in _EXPLICIT_BRAND_RE.finditer(text):
        brand = _clean_brand_value(match.group("brand"))
        if brand:
            brands.append(brand)
    deduplicated: dict[str, str] = {}
    for brand in brands:
        deduplicated.setdefault(brand.casefold(), brand)
    return sorted(deduplicated.values(), key=str.casefold)[:8]


def _sale_mode_from_scope(
    candidate: dict[str, Any],
    catalog_link: target.CatalogLink | None,
) -> tuple[bool, str]:
    if catalog_link is not None:
        if catalog_link.catalog_scope == "PALLET_AUCTIONS":
            return True, "OFFICIAL_CATALOG_SCOPE"
        if catalog_link.catalog_scope == "WHOLESALE_SHOP":
            return False, "OFFICIAL_CATALOG_SCOPE"
    strong_page_evidence = bool(
        candidate.get("current_bid") is not None or candidate.get("auction_end_text")
    )
    return strong_page_evidence, "PRODUCT_PAGE_TRANSACTION_FIELDS"


def stockhurt_candidate_with_sale_mode_brand_cleanup(
    *,
    source_url: str,
    html_text: str,
    observed_at,
    catalog_link: target.CatalogLink | None = None,
) -> dict[str, Any] | None:
    candidate = _ORIGINAL_CANDIDATE(
        source_url=source_url,
        html_text=html_text,
        observed_at=observed_at,
        catalog_link=catalog_link,
    )
    if candidate is None:
        return None

    is_auction, basis = _sale_mode_from_scope(candidate, catalog_link)
    candidate["sale_mode_classification_basis"] = basis
    candidate["sale_mode"] = "AUCTION" if is_auction else "FIXED_PRICE_OR_ENQUIRY"
    candidate["page_role"] = (
        "PALLET_AUCTION_OFFER" if is_auction else "SPECIFIC_STOCK_OFFER"
    )

    if not is_auction:
        raw_terms = list(candidate.get("auction_terms") or [])
        if raw_terms:
            candidate["ignored_navigation_auction_terms"] = raw_terms
        candidate["auction_terms"] = []
        if candidate.get("current_bid") is not None:
            candidate["ignored_navigation_current_bid"] = candidate["current_bid"]
            candidate["current_bid"] = None
        candidate["auction_end_text"] = None
        candidate["missing_information"] = [
            item
            for item in (candidate.get("missing_information") or [])
            if item != "AUCTION_END_TIME"
        ]

    candidate["brands"] = extract_official_product_brands(
        title=target._compact(candidate.get("title")),
        html_text=html_text,
    )
    candidate["brand_extraction_basis"] = "PRODUCT_TITLE_AND_EXPLICIT_BRAND_FIELD"
    candidate["brand_navigation_text_ignored"] = True
    return candidate


def install_stockhurt_sale_mode_brand_cleanup() -> None:
    """Install the parser correction after redirect recovery is registered."""
    global _INSTALLED
    if _INSTALLED:
        return
    target.SCHEMA_VERSION = PATCH_SCHEMA_VERSION
    recovery.PATCH_SCHEMA_VERSION = PATCH_SCHEMA_VERSION
    target.stockhurt_candidate_from_product_html = (
        stockhurt_candidate_with_sale_mode_brand_cleanup
    )
    _INSTALLED = True
