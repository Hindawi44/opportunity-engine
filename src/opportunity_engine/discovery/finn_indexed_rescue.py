"""Bounded rescue retrieval for FINN item pages indexed by Brave.

This module tests one narrow question: can the Discovery Engine retrieve the
same kind of specific FINN clothing-lot item pages that a successful manual web
search can find? It deliberately stops before page verification, analysis, or
commercial action.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence
from urllib.parse import parse_qs, urlparse

from opportunity_engine.discovery.clothing_inventory_search import (
    DiscoveryQuery,
    classify_search_hit,
    normalize_public_url,
)
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider

FINN_INDEXED_RESCUE_FRESHNESS = "py"
FINN_INDEXED_REFERENCE_ITEM_IDS = frozenset({
    "457076453",  # 15 Rains jackets from the successful manual search
    "431015947",  # approximately 150 pairs of women's shoes
    "468298756",  # mixed clothes, shoes and bags with stand
})

FINN_INDEXED_LISTING_QUERIES: tuple[DiscoveryQuery, ...] = (
    DiscoveryQuery(
        "finn-index-01",
        "LARGE_LOT_SALE",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        'site:finn.no/recommerce/forsale/item '
        '("vareparti" OR "klesparti" OR "partisalg") '
        '(klær OR plagg OR arbeidstøy) -"ønskes kjøpt" -kjøpes',
    ),
    DiscoveryQuery(
        "finn-index-02",
        "WAREHOUSE_SURPLUS",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        'site:finn.no/recommerce/forsale/item "restlager" '
        '(klær OR plagg OR sko OR jakker OR bukser) -"ønskes kjøpt" -kjøpes',
    ),
    DiscoveryQuery(
        "finn-index-03",
        "LARGE_LOT_SALE",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        'site:finn.no/recommerce/forsale/item '
        '("selges samlet" OR "samlet parti") '
        '(klær OR sko OR jakker OR bukser) -"ønskes kjøpt" -kjøpes',
    ),
    DiscoveryQuery(
        "finn-index-04",
        "LARGE_LOT_SALE",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        'site:finn.no/recommerce/forsale/item ("stk" OR "par") '
        '(jakker OR bukser OR sko OR arbeidstøy) '
        '(parti OR partisalg OR "selges samlet") -"ønskes kjøpt" -kjøpes',
    ),
    DiscoveryQuery(
        "finn-index-05",
        "LARGE_LOT_SALE",
        "SPECIALIZED",
        "CLOTHING_INVENTORY",
        'site:finn.no/recommerce/forsale/item Rains '
        '(jakker OR regntøy) (parti OR "stk" OR "selges samlet") '
        '-"ønskes kjøpt" -kjøpes',
        "SECONDARY",
    ),
    DiscoveryQuery(
        "finn-index-06",
        "WAREHOUSE_SURPLUS",
        "SPECIALIZED",
        "CLOTHING_INVENTORY",
        'site:finn.no/recommerce/forsale/item '
        '(arbeidsbukser OR arbeidstøy OR arbeidsjakker) '
        '(parti OR partisalg OR "stk") -"ønskes kjøpt" -kjøpes',
        "SECONDARY",
    ),
    DiscoveryQuery(
        "finn-index-07",
        "LARGE_LOT_SALE",
        "SPECIALIZED",
        "CLOTHING_INVENTORY",
        'site:finn.no/recommerce/forsale/item (damebukser OR dameklær) '
        '(parti OR "stk" OR "selges samlet") -"ønskes kjøpt" -kjøpes',
        "SECONDARY",
    ),
    DiscoveryQuery(
        "finn-index-08",
        "LARGE_LOT_SALE",
        "SPECIALIZED",
        "CLOTHING_INVENTORY",
        'site:finn.no/recommerce/forsale/item (sko OR loafers OR pumps) '
        '("par" OR parti OR "selges samlet") -"ønskes kjøpt" -kjøpes',
        "SECONDARY",
    ),
)

_CLOTHING_TERMS = (
    "klær", "plagg", "jakke", "jakker", "bukse", "bukser", "damebukser",
    "sko", "damesko", "loafers", "pumps", "arbeidstøy", "arbeidsbukser",
    "arbeidsjakker", "regntøy", "rains", "vesker",
)
_BULK_TERMS = (
    "vareparti", "klesparti", "partisalg", "parti", "restlager",
    "selges samlet", "samlet parti", "hele lageret", "hele varelageret",
    "stort parti", "lager",
)
_BUYER_INTENT_TERMS = (
    "ønskes kjøpt", "ønsker å kjøpe", "vil kjøpe", "kjøpes", "søker etter",
)
_QUANTITY_SIGNAL = re.compile(
    r"\b\d{2,4}\s*(?:stk|par|plagg|jakker|bukser|sko|vesker)\b",
    flags=re.IGNORECASE,
)
_FINN_ITEM_PATH = re.compile(r"^/recommerce/forsale/item/(\d+)(?:/)?$", re.I)


@dataclass(slots=True)
class FinnIndexedItem:
    item_id: str
    title: str
    url: str
    description: str
    found_by_queries: list[str] = field(default_factory=list)
    clothing_signal: bool = False
    bulk_signal: bool = False
    buyer_intent: bool = False
    retrieval_eligible: bool = False
    existing_classifier_state: str = ""
    existing_classifier_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "title": self.title,
            "url": self.url,
            "description": self.description,
            "found_by_queries": list(self.found_by_queries),
            "clothing_signal": self.clothing_signal,
            "bulk_signal": self.bulk_signal,
            "buyer_intent": self.buyer_intent,
            "retrieval_eligible": self.retrieval_eligible,
            "existing_classifier_state": self.existing_classifier_state,
            "existing_classifier_reason": self.existing_classifier_reason,
            "reference_item": self.item_id in FINN_INDEXED_REFERENCE_ITEM_IDS,
        }


def extract_finn_item_id(url: str) -> str | None:
    """Return a stable FINN item ID from supported public item URL shapes."""
    canonical = normalize_public_url(url)
    if not canonical:
        return None
    parsed = urlparse(canonical)
    if parsed.hostname not in {"finn.no", "www.finn.no"}:
        return None
    match = _FINN_ITEM_PATH.fullmatch(parsed.path)
    if match:
        return match.group(1)
    if parsed.path.lower().endswith("/bap/forsale/ad.html"):
        value = parse_qs(parsed.query).get("finnkode", [""])[0]
        return value if value.isdigit() else None
    return None


def _normalized_text(*values: str) -> str:
    return " ".join(" ".join(value.casefold().split()) for value in values if value)


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def run_finn_indexed_retrieval(
    provider: SearchProvider,
    *,
    queries: Iterable[DiscoveryQuery] = FINN_INDEXED_LISTING_QUERIES,
    results_per_query: int = 20,
    minimum_specific_items: int = 5,
) -> dict[str, Any]:
    """Retrieve, deduplicate and diagnose specific FINN item pages.

    Retrieval eligibility is intentionally weaker than confirmation. A retained
    item still requires the existing bounded public-page verification gate.
    """
    if not 1 <= results_per_query <= 20:
        raise ValueError("results_per_query must be between 1 and 20")
    if minimum_specific_items < 1:
        raise ValueError("minimum_specific_items must be positive")

    query_list = tuple(queries)
    items: dict[str, FinnIndexedItem] = {}
    errors: list[dict[str, str]] = []
    hits_received = 0
    non_item_hits = 0

    for query in query_list:
        try:
            hits: Sequence[SearchHit] = provider.search(
                query.query,
                count=results_per_query,
            )
        except Exception as exc:  # provider failures are reported, never hidden
            errors.append({"query_id": query.query_id, "error": str(exc)})
            continue

        hits_received += len(hits)
        for hit in hits:
            item_id = extract_finn_item_id(hit.url)
            if item_id is None:
                non_item_hits += 1
                continue

            canonical_url = normalize_public_url(hit.url)
            text = _normalized_text(hit.title, hit.description)
            clothing_signal = any(term in text for term in _CLOTHING_TERMS)
            bulk_signal = (
                any(term in text for term in _BULK_TERMS)
                or bool(_QUANTITY_SIGNAL.search(text))
            )
            buyer_intent = any(term in text for term in _BUYER_INTENT_TERMS)
            classification = classify_search_hit(hit, query)

            existing = items.get(item_id)
            if existing is None:
                existing = FinnIndexedItem(
                    item_id=item_id,
                    title=hit.title.strip(),
                    url=canonical_url,
                    description=hit.description.strip(),
                )
                items[item_id] = existing
            elif len(hit.description.strip()) > len(existing.description):
                existing.description = hit.description.strip()
            if len(hit.title.strip()) > len(existing.title):
                existing.title = hit.title.strip()

            _append_unique(existing.found_by_queries, query.query_id)
            existing.clothing_signal = existing.clothing_signal or clothing_signal
            existing.bulk_signal = existing.bulk_signal or bulk_signal
            existing.buyer_intent = existing.buyer_intent or buyer_intent
            existing.retrieval_eligible = (
                existing.clothing_signal
                and existing.bulk_signal
                and not existing.buyer_intent
            )
            if classification.state != "REJECTED_NOISE" or not existing.existing_classifier_state:
                existing.existing_classifier_state = classification.state
                existing.existing_classifier_reason = classification.reason

    ordered = sorted(
        items.values(),
        key=lambda item: (
            item.retrieval_eligible,
            item.item_id in FINN_INDEXED_REFERENCE_ITEM_IDS,
            len(item.found_by_queries),
            len(item.description),
        ),
        reverse=True,
    )
    eligible = [item for item in ordered if item.retrieval_eligible]
    recovered_reference_ids = sorted(
        FINN_INDEXED_REFERENCE_ITEM_IDS.intersection(items)
    )
    rescue_success = len(eligible) >= minimum_specific_items

    return {
        "schema_version": "finn-indexed-listing-rescue-1.0",
        "domain": "CLOTHING_INVENTORY",
        "provider": getattr(provider, "name", provider.__class__.__name__),
        "query_matrix": [query.to_dict() for query in query_list],
        "queries_submitted": len(query_list),
        "hits_received": hits_received,
        "non_finn_item_hits_excluded": non_item_hits,
        "unique_finn_item_urls": len(items),
        "retrieval_eligible_items": len(eligible),
        "minimum_specific_items": minimum_specific_items,
        "rescue_success": rescue_success,
        "reference_item_ids": sorted(FINN_INDEXED_REFERENCE_ITEM_IDS),
        "reference_items_recovered": recovered_reference_ids,
        "reference_recall": (
            len(recovered_reference_ids) / len(FINN_INDEXED_REFERENCE_ITEM_IDS)
        ),
        "errors": errors,
        "items": [item.to_dict() for item in ordered],
        "automatic_contact": False,
        "automatic_purchase_decision": False,
        "page_verification_performed": False,
        "analysis_engine_used": False,
    }
