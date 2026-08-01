"""Bounded public Klaravik targeting for Swedish clothing inventory.

Only exact public product-auction pages are accepted. The adapter never logs in,
bids, contacts a seller, purchases, or bypasses access controls. Item-specific
text is isolated so site-wide bankruptcy wording cannot contaminate scenarios.
"""
from __future__ import annotations

import html
import re
from collections import Counter
from dataclasses import dataclass, replace
from typing import Any, Iterable, Sequence
from urllib.parse import urlparse

import requests

from opportunity_engine.discovery.clothing_inventory_search import (
    ACTIVE,
    ENDED,
    ITEM_LISTING,
    UNKNOWN,
    DiscoveryQuery,
    PageVerification,
    normalize_public_url,
    verify_public_html,
)
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider
from opportunity_engine.discovery.sweden_clothing_inventory import (
    enrich_sweden_page_verification,
)

KLARAVIK_HOST = "klaravik.se"
KLARAVIK_PRODUCT_PATH = re.compile(
    r"^/auktion/produkt/(?P<slug>[a-z0-9][a-z0-9-]*)/?$",
    re.I,
)

KLARAVIK_CLOTHING_QUERY_MATRIX: tuple[DiscoveryQuery, ...] = (
    DiscoveryQuery("se-kl-01", "LARGE_LOT_SALE", "SALE_INTENT", "CLOTHING_INVENTORY", 'site:klaravik.se/auktion/produkt kläder parti -maskin -fordon'),
    DiscoveryQuery("se-kl-02", "LARGE_LOT_SALE", "SALE_INTENT", "CLOTHING_INVENTORY", 'site:klaravik.se/auktion/produkt "kläder och skor" parti'),
    DiscoveryQuery("se-kl-03", "COMPANY_BANKRUPTCY", "SALE_INTENT", "CLOTHING_INVENTORY", 'site:klaravik.se/auktion/produkt konkurs kläder lager'),
    DiscoveryQuery("se-kl-04", "WAREHOUSE_SURPLUS", "SALE_INTENT", "CLOTHING_INVENTORY", 'site:klaravik.se/auktion/produkt restparti kläder'),
    DiscoveryQuery("se-kl-05", "LARGE_LOT_SALE", "SPECIALIZED", "CLOTHING_INVENTORY", 'site:klaravik.se/auktion/produkt arbetskläder skor parti', "SECONDARY"),
    DiscoveryQuery("se-kl-06", "LARGE_LOT_SALE", "SPECIALIZED", "CLOTHING_INVENTORY", 'site:klaravik.se/auktion/produkt damkläder kläder parti', "SECONDARY"),
    DiscoveryQuery("se-kl-07", "LARGE_LOT_SALE", "SPECIALIZED", "CLOTHING_INVENTORY", 'site:klaravik.se/auktion/produkt secondhand kläder skor', "SECONDARY"),
    DiscoveryQuery("se-kl-08", "LARGE_LOT_SALE", "SPECIALIZED", "CLOTHING_INVENTORY", 'site:klaravik.se/auktion/produkt kläder accessoarer lager', "SECONDARY"),
)

_CLOTHING_TERMS = (
    "kläder", "klädparti", "damkläder", "herrkläder", "barnkläder",
    "arbetskläder", "träningskläder", "sportkläder", "arbetsskor", "skor",
    "stövlar", "accessoarer", "plagg", "textil", "jacka", "byxor",
    "tröja", "skjorta", "klänning", "kjol",
)
_BULK_TERMS = (
    "parti", "stort parti", "större parti", "lager", "varulager",
    "restlager", "restparti", "sortiment", "pall", "pallar", "kartong",
    "kartonger", "många plagg",
)
_NON_INVENTORY_EQUIPMENT_TERMS = (
    "butikslarm", "klädlarm", "larmtagg", "larmtaggar", "avlarmningsenhet",
)
_QUANTITY_RE = re.compile(
    r"\b(?:ca\s*)?(?P<count>\d{2,7})\s*(?:st|plagg|artiklar|par)\b",
    re.I,
)
_ENDED_TERMS = (
    "denna auktion är avslutad", "auktionen är avslutad",
    "auktionen avslutad", "avslutad", "såld",
)
_ACTIVE_TERMS = (
    "auktionen avslutas", "nuvarande bud", "lägg ett bud", "budgivning pågår",
)
_BANKRUPTCY_TERMS = (
    "konkursbo", "i konkurs", "företag i konkurs", "butik i konkurs",
    "konkursade bolaget", "konkursförvaltare",
)
_SURPLUS_TERMS = ("restparti", "restlager", "överskottslager")
_LARGE_LOT_TERMS = (
    "stort parti", "större parti", "parti med", "parti kläder",
    "klädparti", "varulager", "helt varulager",
)
_ENDED_REASON = "specific Klaravik product auction is ended or sold"
_EQUIPMENT_REASON = "clothing-related equipment is not clothing inventory"
_SOURCE_POLICY_ALIASES = "klær vareparti auksjon"


@dataclass(frozen=True, slots=True)
class KlaravikGateDecision:
    accepted: bool
    canonical_url: str
    listing_key: str | None
    reason: str


def build_klaravik_clothing_queries(
    query_budget: int = 8,
) -> tuple[DiscoveryQuery, ...]:
    """Return a bounded prefix of the source query matrix."""
    if not 1 <= query_budget <= len(KLARAVIK_CLOTHING_QUERY_MATRIX):
        raise ValueError(
            "query_budget must be between 1 and "
            f"{len(KLARAVIK_CLOTHING_QUERY_MATRIX)}"
        )
    return KLARAVIK_CLOTHING_QUERY_MATRIX[:query_budget]


def _normalized_host(host: str | None) -> str:
    value = (host or "").casefold()
    return value[4:] if value.startswith("www.") else value


def _compact(value: str) -> str:
    return " ".join((value or "").casefold().split())


def canonicalize_klaravik_product_url(url: str) -> tuple[str, str] | None:
    """Return normalized URL and slug for one exact product-auction page."""
    canonical = normalize_public_url(url)
    if not canonical:
        return None
    parsed = urlparse(canonical)
    if _normalized_host(parsed.hostname) != KLARAVIK_HOST:
        return None
    match = KLARAVIK_PRODUCT_PATH.fullmatch(parsed.path or "/")
    if match is None:
        return None
    return canonical, match.group("slug").casefold()


def _has_bulk_scope(text: str) -> bool:
    return any(term in text for term in _BULK_TERMS) or any(
        int(match.group("count")) >= 10 for match in _QUANTITY_RE.finditer(text)
    )


def _is_non_inventory_equipment(text: str) -> bool:
    return any(term in text for term in _NON_INVENTORY_EQUIPMENT_TERMS)


def klaravik_gate_decision(hit: SearchHit) -> KlaravikGateDecision:
    """Accept exact bulk-apparel pages and reject equipment and known history."""
    canonical = normalize_public_url(hit.url)
    if not canonical:
        return KlaravikGateDecision(False, "", None, "invalid public HTTPS URL")
    if _normalized_host(urlparse(canonical).hostname) != KLARAVIK_HOST:
        return KlaravikGateDecision(False, canonical, None, "not a Klaravik host")
    parsed = canonicalize_klaravik_product_url(hit.url)
    if parsed is None:
        return KlaravikGateDecision(
            False,
            canonical,
            None,
            "Klaravik URL is not one specific product-auction page",
        )

    canonical, slug = parsed
    title = _compact(hit.title)
    combined = _compact(f"{hit.title} {hit.description}")
    if _is_non_inventory_equipment(combined):
        return KlaravikGateDecision(False, canonical, slug, _EQUIPMENT_REASON)
    if not any(term in title for term in _CLOTHING_TERMS):
        return KlaravikGateDecision(
            False,
            canonical,
            slug,
            "specific Klaravik title lacks clothing evidence",
        )
    if not _has_bulk_scope(combined):
        return KlaravikGateDecision(
            False,
            canonical,
            slug,
            "specific clothing auction lacks bulk inventory evidence",
        )
    if any(term in combined for term in _ENDED_TERMS):
        return KlaravikGateDecision(False, canonical, slug, _ENDED_REASON)
    return KlaravikGateDecision(
        True,
        canonical,
        slug,
        "specific Klaravik bulk clothing-inventory product auction",
    )


class KlaravikPrefetchedSearchProvider:
    """Prefetch a bounded pack and globally suppress known historical slugs."""

    name = "Klaravik Sweden globally filtered source targeting"

    def __init__(
        self,
        provider: SearchProvider,
        *,
        queries: Iterable[DiscoveryQuery],
        request_budget: int,
    ) -> None:
        query_list = tuple(queries)
        if not query_list:
            raise ValueError("queries must not be empty")
        if request_budget < len(query_list):
            raise ValueError("request_budget must cover every registered query")
        query_map = {query.query: query for query in query_list}
        if len(query_map) != len(query_list):
            raise ValueError("query text must be unique")

        self._provider = provider
        self._query_list = query_list
        self._queries = query_map
        self._request_budget = request_budget
        self._requests_made = 0
        self._prefetch_count: int | None = None
        self._hits_by_query: dict[str, tuple[SearchHit, ...]] = {}
        self._raw_hits = 0
        self._accepted_hits = 0
        self._rejected_hits = 0
        self._historical_keys: list[str] = []
        self._accepted_keys: list[str] = []
        self._accepted_urls: list[str] = []
        self._accepted_samples: list[dict[str, Any]] = []
        self._rejected_samples: list[dict[str, Any]] = []
        self._rejection_reasons: Counter[str] = Counter()
        self._query_diagnostics: list[dict[str, Any]] = []

    @staticmethod
    def _sample(
        query: DiscoveryQuery,
        hit: SearchHit,
        decision: KlaravikGateDecision,
        reason: str,
    ) -> dict[str, Any]:
        return {
            "query_id": query.query_id,
            "title": hit.title,
            "url": hit.url,
            "canonical_url": decision.canonical_url,
            "listing_key": decision.listing_key,
            "reason": reason,
            "description": hit.description[:500],
        }

    def _prefetch(self, count: int) -> None:
        if self._hits_by_query:
            if count != self._prefetch_count:
                raise ValueError("count must remain stable during one prefetched run")
            return
        if self._requests_made + len(self._query_list) > self._request_budget:
            raise RuntimeError("Klaravik source request budget exhausted")

        decisions: dict[str, tuple[tuple[SearchHit, KlaravikGateDecision], ...]] = {}
        raw_counts: dict[str, int] = {}
        historical: list[str] = []
        for query in self._query_list:
            raw_hits = tuple(self._provider.search(query.query, count=count))
            self._requests_made += 1
            self._raw_hits += len(raw_hits)
            raw_counts[query.query] = len(raw_hits)
            pairs = tuple((hit, klaravik_gate_decision(hit)) for hit in raw_hits)
            decisions[query.query] = pairs
            for _, decision in pairs:
                if (
                    decision.reason == _ENDED_REASON
                    and decision.listing_key
                    and decision.listing_key not in historical
                ):
                    historical.append(decision.listing_key)

        self._prefetch_count = count
        self._historical_keys = historical
        historical_set = set(historical)

        for query in self._query_list:
            accepted: list[SearchHit] = []
            rejected_count = 0
            for hit, decision in decisions[query.query]:
                reason = decision.reason
                is_accepted = decision.accepted
                if decision.listing_key in historical_set:
                    is_accepted = False
                    reason = _ENDED_REASON
                sample = self._sample(query, hit, decision, reason)
                if not is_accepted:
                    rejected_count += 1
                    self._rejected_hits += 1
                    self._rejection_reasons[reason] += 1
                    if len(self._rejected_samples) < 30:
                        self._rejected_samples.append(sample)
                    continue

                description = (
                    f"{hit.description} | source policy aliases: "
                    f"{_SOURCE_POLICY_ALIASES}"
                ).strip(" |")
                accepted.append(
                    SearchHit(
                        title=hit.title,
                        url=decision.canonical_url,
                        description=description,
                        provider=hit.provider or self.name,
                    )
                )
                self._accepted_hits += 1
                if len(self._accepted_samples) < 30:
                    self._accepted_samples.append(sample)
                if decision.listing_key and decision.listing_key not in self._accepted_keys:
                    self._accepted_keys.append(decision.listing_key)
                if decision.canonical_url not in self._accepted_urls:
                    self._accepted_urls.append(decision.canonical_url)

            self._hits_by_query[query.query] = tuple(accepted)
            self._query_diagnostics.append(
                {
                    "query_id": query.query_id,
                    "query": query.query,
                    "raw_hits": raw_counts[query.query],
                    "accepted_hits": len(accepted),
                    "rejected_hits": rejected_count,
                }
            )

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        if query not in self._queries:
            raise ValueError("query is not registered in the Klaravik source policy")
        self._prefetch(count)
        return self._hits_by_query[query]

    def diagnostics(self) -> dict[str, Any]:
        return {
            "source": "KLARAVIK",
            "host": KLARAVIK_HOST,
            "prefetched": True,
            "request_budget": self._request_budget,
            "requests_made": self._requests_made,
            "raw_hits": self._raw_hits,
            "accepted_hits": self._accepted_hits,
            "rejected_hits": self._rejected_hits,
            "historical_listing_count": len(self._historical_keys),
            "historical_listing_keys": list(self._historical_keys),
            "accepted_listing_keys": list(self._accepted_keys),
            "accepted_urls": list(self._accepted_urls),
            "accepted_samples": list(self._accepted_samples),
            "rejection_reasons": dict(sorted(self._rejection_reasons.items())),
            "rejected_samples": list(self._rejected_samples),
            "query_diagnostics": list(self._query_diagnostics),
        }


def _strip_html(decoded: str) -> str:
    fragment = re.sub(
        r"<(script|style|noscript)[^>]*>.*?</\1>",
        " ",
        decoded,
        flags=re.I | re.S,
    )
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    return " ".join(html.unescape(fragment).split())


def _source_overview(visible: str) -> str:
    """Select the most item-specific Klaravik overview section."""
    normalized = visible.casefold()
    starts = [match.end() for match in re.finditer(r"\böversikt\b", normalized)]
    candidates: list[str] = []
    for start in starts:
        ends = [
            normalized.find(marker, start)
            for marker in (
                "viktig information", "digital visning", "plats & frakt",
                "kända anmärkningar", "skick",
            )
        ]
        valid_ends = [end for end in ends if end > start]
        end = min(valid_ends) if valid_ends else min(len(visible), start + 6000)
        segment = visible[start:end].strip()
        if segment:
            candidates.append(segment)
    if not candidates:
        return visible[:4000]
    return max(
        candidates,
        key=lambda value: (
            sum(term in value.casefold() for term in (*_CLOTHING_TERMS, *_BULK_TERMS)),
            len(value),
        ),
    )[:6000]


def _scenario_from_item_context(text: str) -> str:
    normalized = _compact(text)
    if any(term in normalized for term in _BANKRUPTCY_TERMS):
        return "COMPANY_BANKRUPTCY"
    if any(term in normalized for term in _SURPLUS_TERMS):
        return "WAREHOUSE_SURPLUS"
    if any(term in normalized for term in _LARGE_LOT_TERMS):
        return "LARGE_LOT_SALE"
    return "AUCTION"


def _inventory_type(text: str) -> str | None:
    normalized = _compact(text)
    if _is_non_inventory_equipment(normalized):
        return None
    if "arbetskläder" in normalized:
        return "workwear_inventory"
    if "träningskläder" in normalized or "sportkläder" in normalized:
        return "sportswear_inventory"
    if "damkläder" in normalized:
        return "womens_clothing"
    if "kläder" in normalized and any(term in normalized for term in ("skor", "stövlar")):
        return "mixed_clothing_and_footwear"
    if any(term in normalized for term in _CLOTHING_TERMS):
        return "mixed_clothing_inventory"
    return None


def _location(decoded: str, visible: str) -> str | None:
    raw_match = re.search(
        r">\s*([A-ZÅÄÖ][^<>]{1,50}),\s*"
        r"([A-ZÅÄÖ][^<>]{2,60}\s+län)\s*<",
        decoded,
    )
    if raw_match:
        city = html.unescape(raw_match.group(1)).strip()
        county = html.unescape(raw_match.group(2)).strip()
        return f"{city}, {county}"

    fallback = re.search(
        r"\b([A-ZÅÄÖ][A-Za-zÅÄÖåäö\-]{1,30}),\s*"
        r"([A-ZÅÄÖ][A-Za-zÅÄÖåäö\- ]{2,60}\s+län)\b",
        visible,
    )
    return f"{fallback.group(1)}, {fallback.group(2).strip()}" if fallback else None


def _quantity(item_context: str) -> int | None:
    match = _QUANTITY_RE.search(item_context)
    return int(match.group("count")) if match else None


def verify_klaravik_public_page(
    url: str,
    *,
    timeout: float = 15.0,
) -> PageVerification:
    """Verify one exact page through the certificate-valid www host."""
    parsed = canonicalize_klaravik_product_url(url)
    if parsed is None:
        return PageVerification(url=url, error="not an exact public Klaravik product URL")
    canonical, _ = parsed
    request_url = canonical.replace(
        "https://klaravik.se/",
        "https://www.klaravik.se/",
        1,
    )
    try:
        response = requests.get(
            request_url,
            timeout=timeout,
            allow_redirects=True,
            headers={"User-Agent": "OpportunityEngine-Discovery/2.1"},
        )
        response.raise_for_status()
    except Exception as exc:
        return PageVerification(url=canonical, verified=False, error=str(exc))

    final = canonicalize_klaravik_product_url(response.url)
    if final is None:
        return PageVerification(
            url=canonical,
            verified=False,
            error="redirected outside an exact Klaravik product page",
        )
    final_url, _ = final
    decoded = response.text
    base = enrich_sweden_page_verification(verify_public_html(final_url, decoded))
    visible = _strip_html(decoded)
    overview = _source_overview(visible)
    item_context = " ".join(value for value in (base.title, overview) if value)
    normalized_item = _compact(item_context)
    normalized_visible = _compact(visible)

    object_match = re.search(r"\bobjekt-id\s*:?\s*(\d+)\b", visible, re.I)
    identity = (
        f"url-id:{object_match.group(1)}"
        if object_match
        else base.opportunity_identity or f"item-url:{final_url}"
    )
    ended = any(term in normalized_visible for term in _ENDED_TERMS)
    active = not ended and any(term in normalized_visible for term in _ACTIVE_TERMS)
    equipment = _is_non_inventory_equipment(normalized_item)
    clothing = (
        not equipment
        and any(term in normalized_item for term in _CLOTHING_TERMS)
    )
    bulk = not equipment and _has_bulk_scope(normalized_item)

    return replace(
        base,
        url=final_url,
        text=overview[:2000] or base.text,
        location=_location(decoded, visible),
        inventory_type=_inventory_type(item_context),
        price_nok=None,
        bid_price_nok=None,
        quantity=_quantity(item_context) if not equipment else None,
        listing_status=ENDED if ended else ACTIVE if active else UNKNOWN,
        page_role=ITEM_LISTING,
        opportunity_identity=identity,
        identity_stable=True,
        clothing_inventory_evidence=clothing and bulk,
        sale_evidence=active and clothing and bulk,
        event_scenario=_scenario_from_item_context(item_context),
        bounded_context=overview[:4000] or base.bounded_context,
        verified=True,
        error=None,
    )
