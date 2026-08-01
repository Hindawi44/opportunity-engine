"""Bounded public Blinto targeting for Swedish clothing inventory.

Only exact public auction pages are accepted. The adapter never logs in, bids,
contacts a seller, purchases, or bypasses access controls. Blinto object IDs and
auction-occurrence IDs are kept separate because one object can be re-listed in
a later auction occurrence.
"""
from __future__ import annotations

import html
import re
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping, Sequence
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

BLINTO_HOST = "blinto.se"
BLINTO_AUCTION_PATH = re.compile(
    r"^/auction/(?P<slug>[A-Za-z0-9][A-Za-z0-9_-]*)/?$",
    re.I,
)
_BLINTO_ID_SUFFIX = re.compile(
    r"-(?P<object_id>\d{4,})-(?P<occurrence_id>\d{4,})$",
    re.I,
)

BLINTO_CLOTHING_QUERY_MATRIX: tuple[DiscoveryQuery, ...] = (
    DiscoveryQuery("se-bl-01", "LARGE_LOT_SALE", "SALE_INTENT", "CLOTHING_INVENTORY", 'site:blinto.se/auction "parti med arbetskläder"'),
    DiscoveryQuery("se-bl-02", "LARGE_LOT_SALE", "SALE_INTENT", "CLOTHING_INVENTORY", 'site:blinto.se/auction "parti med kläder" -klädskåp'),
    DiscoveryQuery("se-bl-03", "WAREHOUSE_SURPLUS", "SALE_INTENT", "CLOTHING_INVENTORY", 'site:blinto.se/auction "överskott av nya kläder"'),
    DiscoveryQuery("se-bl-04", "WAREHOUSE_SURPLUS", "SALE_INTENT", "CLOTHING_INVENTORY", 'site:blinto.se/auction varulager kläder överskott'),
    DiscoveryQuery("se-bl-05", "INVENTORY_LIQUIDATION", "SALE_INTENT", "CLOTHING_INVENTORY", 'site:blinto.se/auction utförsäljning parti kläder'),
    DiscoveryQuery("se-bl-06", "LARGE_LOT_SALE", "SPECIALIZED", "CLOTHING_INVENTORY", 'site:blinto.se/auction parti arbetsskor arbetsbyxor', "SECONDARY"),
    DiscoveryQuery("se-bl-07", "LARGE_LOT_SALE", "SPECIALIZED", "CLOTHING_INVENTORY", 'site:blinto.se/auction varselkläder parti totalt', "SECONDARY"),
    DiscoveryQuery("se-bl-08", "LARGE_LOT_SALE", "SPECIALIZED", "CLOTHING_INVENTORY", 'site:blinto.se/auction secondhand kläder parti', "SECONDARY"),
)

_CLOTHING_TERMS = (
    "kläder", "klädesplagg", "arbetskläder", "yrkeskläder", "varselkläder",
    "skyddskläder", "damkläder", "herrkläder", "barnkläder", "sportkläder",
    "träningskläder", "arbetsbyxor", "byxor", "jackor", "jacka", "tröjor",
    "t-shirts", "piké", "skjortor", "shorts", "västar", "overaller",
    "regnkläder", "arbetsskor", "skyddsskor", "skor", "stövlar", "plagg",
)
_BULK_TERMS = (
    "parti", "stort parti", "större parti", "varulager", "restlager",
    "restparti", "överskott", "utförsäljning", "sortiment", "hela lagret",
    "pall", "pallar", "kartong", "kartonger", "många plagg",
)
_NOISE_TERMS = (
    "klädskåp", "kldskp", "klädställ", "klädvagn", "vagn för kläder",
    "butikslarm", "klädlarm", "larmtagg", "larmtaggar", "avlarmning",
    "galgar", "tvättmaskin", "torkskåp", "tryckpress", "textilpress",
    "värmepress", "transfer press", "press för kläder",
)
_QUANTITY_RE = re.compile(
    r"\b(?:ca\s*)?(?P<count>\d{1,7})\s*"
    r"(?:st|stycken|plagg|artiklar|enheter|delar|överdelar|byxor|par)\b",
    re.I,
)
_TOTAL_RE = re.compile(
    r"\b(?:totalt|sammanlagt)\s*:?\s*(?P<count>\d{1,7})\s*"
    r"(?:st|stycken|plagg|artiklar|enheter|delar|överdelar|byxor|par)?\b",
    re.I,
)
_ANTAL_RE = re.compile(r"\bantal\s*:?\s*(?P<count>\d{1,7})\s*(?:st|par)?\b", re.I)
_ENDED_TERMS = (
    "auktionen är avslutad", "auktionen har avslutats", "avslutad",
    "vinnande bud", "såld", "the auction has ended", "winning bid", "sold back",
)
_ACTIVE_TERMS = (
    "auktionen avslutas", "högsta bud", "lägg bud", "budgivning",
    "reservation price", "highest bid", "ends ",
)
_BANKRUPTCY_TERMS = (
    "konkursbo", "konkursförvaltare", "företag i konkurs", "butik i konkurs",
)
_SURPLUS_TERMS = ("överskott", "restlager", "restparti", "varulager & överskott")
_LIQUIDATION_TERMS = ("utförsäljning", "avveckling", "hela lagret säljs")
_LARGE_LOT_TERMS = (
    "parti med", "stort parti", "större parti", "varulager",
    "parti arbetsbyxor", "parti kläder/skor", "utrustningsparti",
)
_ENDED_REASON = "specific Blinto auction occurrence is ended or sold"
_NOISE_REASON = "clothing-related equipment is not clothing inventory"
_SOURCE_POLICY_ALIASES = "klær vareparti auksjon"


@dataclass(frozen=True, slots=True)
class BlintoAuctionIdentity:
    canonical_url: str
    slug: str
    object_id: str | None
    occurrence_id: str | None

    @property
    def listing_key(self) -> str:
        return self.occurrence_id or self.slug.casefold()


@dataclass(frozen=True, slots=True)
class BlintoGateDecision:
    accepted: bool
    canonical_url: str
    listing_key: str | None
    object_id: str | None
    occurrence_id: str | None
    reason: str


def build_blinto_clothing_queries(query_budget: int = 8) -> tuple[DiscoveryQuery, ...]:
    """Return a bounded prefix of the Blinto query matrix."""
    if not 1 <= query_budget <= len(BLINTO_CLOTHING_QUERY_MATRIX):
        raise ValueError(
            "query_budget must be between 1 and "
            f"{len(BLINTO_CLOTHING_QUERY_MATRIX)}"
        )
    return BLINTO_CLOTHING_QUERY_MATRIX[:query_budget]


def _normalized_host(host: str | None) -> str:
    value = (host or "").casefold()
    return value[4:] if value.startswith("www.") else value


def _compact(value: str) -> str:
    return " ".join((value or "").casefold().split())


def canonicalize_blinto_auction_url(url: str) -> BlintoAuctionIdentity | None:
    """Return exact public auction identity without collapsing re-listings."""
    canonical = normalize_public_url(url)
    if not canonical:
        return None
    parsed = urlparse(canonical)
    if _normalized_host(parsed.hostname) != BLINTO_HOST:
        return None
    match = BLINTO_AUCTION_PATH.fullmatch(parsed.path or "/")
    if match is None:
        return None
    slug = match.group("slug")
    suffix = _BLINTO_ID_SUFFIX.search(slug)
    return BlintoAuctionIdentity(
        canonical_url=canonical,
        slug=slug,
        object_id=suffix.group("object_id") if suffix else None,
        occurrence_id=suffix.group("occurrence_id") if suffix else None,
    )


def _has_bulk_scope(text: str) -> bool:
    return any(term in text for term in _BULK_TERMS) or any(
        int(match.group("count")) >= 10 for match in _QUANTITY_RE.finditer(text)
    )


def _is_noise(text: str) -> bool:
    return any(term in text for term in _NOISE_TERMS)


def blinto_gate_decision(hit: SearchHit) -> BlintoGateDecision:
    """Accept exact bulk-apparel auctions and reject equipment and history."""
    canonical = normalize_public_url(hit.url)
    if not canonical:
        return BlintoGateDecision(False, "", None, None, None, "invalid public HTTPS URL")
    if _normalized_host(urlparse(canonical).hostname) != BLINTO_HOST:
        return BlintoGateDecision(False, canonical, None, None, None, "not a Blinto host")
    identity = canonicalize_blinto_auction_url(hit.url)
    if identity is None:
        return BlintoGateDecision(
            False, canonical, None, None, None,
            "Blinto URL is not one specific auction page",
        )

    title = _compact(hit.title)
    combined = _compact(f"{hit.title} {hit.description}")
    if _is_noise(combined):
        return BlintoGateDecision(
            False, identity.canonical_url, identity.listing_key,
            identity.object_id, identity.occurrence_id, _NOISE_REASON,
        )
    if not any(term in title for term in _CLOTHING_TERMS):
        return BlintoGateDecision(
            False, identity.canonical_url, identity.listing_key,
            identity.object_id, identity.occurrence_id,
            "specific Blinto title lacks clothing evidence",
        )
    if not _has_bulk_scope(combined):
        return BlintoGateDecision(
            False, identity.canonical_url, identity.listing_key,
            identity.object_id, identity.occurrence_id,
            "specific clothing auction lacks bulk inventory evidence",
        )
    if any(term in combined for term in _ENDED_TERMS):
        return BlintoGateDecision(
            False, identity.canonical_url, identity.listing_key,
            identity.object_id, identity.occurrence_id, _ENDED_REASON,
        )
    return BlintoGateDecision(
        True, identity.canonical_url, identity.listing_key,
        identity.object_id, identity.occurrence_id,
        "specific Blinto bulk clothing-inventory auction",
    )


class BlintoPrefetchedSearchProvider:
    """Prefetch a bounded pack and suppress only known historical occurrences."""

    name = "Blinto Sweden globally filtered source targeting"

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
        self._accepted_object_ids: list[str] = []
        self._accepted_occurrence_ids: list[str] = []
        self._accepted_urls: list[str] = []
        self._accepted_samples: list[dict[str, Any]] = []
        self._rejected_samples: list[dict[str, Any]] = []
        self._rejection_reasons: Counter[str] = Counter()
        self._query_diagnostics: list[dict[str, Any]] = []

    @staticmethod
    def _sample(
        query: DiscoveryQuery,
        hit: SearchHit,
        decision: BlintoGateDecision,
        reason: str,
    ) -> dict[str, Any]:
        return {
            "query_id": query.query_id,
            "title": hit.title,
            "url": hit.url,
            "canonical_url": decision.canonical_url,
            "listing_key": decision.listing_key,
            "object_id": decision.object_id,
            "occurrence_id": decision.occurrence_id,
            "reason": reason,
            "description": hit.description[:500],
        }

    def _prefetch(self, count: int) -> None:
        if self._hits_by_query:
            if count != self._prefetch_count:
                raise ValueError("count must remain stable during one prefetched run")
            return
        if self._requests_made + len(self._query_list) > self._request_budget:
            raise RuntimeError("Blinto source request budget exhausted")

        decisions: dict[str, tuple[tuple[SearchHit, BlintoGateDecision], ...]] = {}
        raw_counts: dict[str, int] = {}
        historical: list[str] = []
        for query in self._query_list:
            raw_hits = tuple(self._provider.search(query.query, count=count))
            self._requests_made += 1
            self._raw_hits += len(raw_hits)
            raw_counts[query.query] = len(raw_hits)
            pairs = tuple((hit, blinto_gate_decision(hit)) for hit in raw_hits)
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
                if decision.object_id and decision.object_id not in self._accepted_object_ids:
                    self._accepted_object_ids.append(decision.object_id)
                if decision.occurrence_id and decision.occurrence_id not in self._accepted_occurrence_ids:
                    self._accepted_occurrence_ids.append(decision.occurrence_id)
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
            raise ValueError("query is not registered in the Blinto source policy")
        self._prefetch(count)
        return self._hits_by_query[query]

    def diagnostics(self) -> dict[str, Any]:
        return {
            "source": "BLINTO",
            "host": BLINTO_HOST,
            "prefetched": True,
            "request_budget": self._request_budget,
            "requests_made": self._requests_made,
            "raw_hits": self._raw_hits,
            "accepted_hits": self._accepted_hits,
            "rejected_hits": self._rejected_hits,
            "historical_listing_count": len(self._historical_keys),
            "historical_listing_keys": list(self._historical_keys),
            "accepted_listing_keys": list(self._accepted_keys),
            "accepted_object_ids": list(self._accepted_object_ids),
            "accepted_occurrence_ids": list(self._accepted_occurrence_ids),
            "accepted_urls": list(self._accepted_urls),
            "accepted_samples": list(self._accepted_samples),
            "rejection_reasons": dict(sorted(self._rejection_reasons.items())),
            "rejected_samples": list(self._rejected_samples),
            "query_diagnostics": list(self._query_diagnostics),
        }


def _strip_html(decoded: str) -> str:
    fragment = re.sub(
        r"<(script|style|noscript)[^>]*>.*?</\1>",
        " ", decoded, flags=re.I | re.S,
    )
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    return " ".join(html.unescape(fragment).split())


def _description_section(visible: str) -> str:
    """Select the most item-specific Blinto description section."""
    normalized = visible.casefold()
    starts: list[int] = []
    for marker in ("beskrivning", "description"):
        starts.extend(match.end() for match in re.finditer(rf"\b{marker}\b", normalized))
    candidates: list[str] = []
    end_markers = (
        "kontakta kundtjänst", "contact customer service", "viktig info",
        "important info", "karta", "map", "har du också något att sälja",
    )
    for start in starts:
        ends = [normalized.find(marker, start) for marker in end_markers]
        valid = [end for end in ends if end > start]
        end = min(valid) if valid else min(len(visible), start + 7000)
        segment = visible[start:end].strip()
        if segment:
            candidates.append(segment)
    if not candidates:
        return visible[:5000]
    return max(
        candidates,
        key=lambda value: (
            sum(term in value.casefold() for term in (*_CLOTHING_TERMS, *_BULK_TERMS)),
            len(value),
        ),
    )[:7000]


def _scenario_from_item_context(text: str) -> str:
    normalized = _compact(text)
    if any(term in normalized for term in _BANKRUPTCY_TERMS):
        return "COMPANY_BANKRUPTCY"
    if any(term in normalized for term in _LIQUIDATION_TERMS):
        return "INVENTORY_LIQUIDATION"
    if any(term in normalized for term in _SURPLUS_TERMS):
        return "WAREHOUSE_SURPLUS"
    if any(term in normalized for term in _LARGE_LOT_TERMS):
        return "LARGE_LOT_SALE"
    return "AUCTION"


def _inventory_type(text: str) -> str | None:
    normalized = _compact(text)
    if _is_noise(normalized):
        return None
    if "varselkläder" in normalized:
        return "high_visibility_workwear"
    if "mc-kläder" in normalized or "mc kläder" in normalized or "skinnbyxor" in normalized:
        return "motorcycle_clothing_and_accessories"
    if any(
        term in normalized
        for term in ("arbetskläder", "yrkeskläder", "skyddskläder", "arbetsbyxor")
    ):
        if any(term in normalized for term in ("arbetsskor", "skyddsskor", "skor")):
            return "workwear_and_work_shoes"
        return "workwear_inventory"
    if "damkläder" in normalized:
        return "womens_clothing"
    if any(term in normalized for term in ("sportkläder", "träningskläder")):
        return "sportswear_inventory"
    if "kläder" in normalized and "skor" in normalized:
        return "mixed_clothing_and_footwear"
    if any(term in normalized for term in _CLOTHING_TERMS):
        return "mixed_clothing_inventory"
    return None


def _location(visible: str, object_id: str | None) -> str | None:
    map_match = re.search(
        r"\bKarta\s+över\s+([A-ZÅÄÖ][A-Za-zÅÄÖåäö\- ]{1,60})\b",
        visible,
    )
    if map_match:
        candidate = map_match.group(1).strip()
        candidate = re.split(
            r"\s+(?:Auktionen|The\s+auction|Högsta|Highest|Vinnande|Winning|"
            r"Objekt|Item|Varulager|Kontakta)\b",
            candidate,
            maxsplit=1,
            flags=re.I,
        )[0].strip(" ,.-")
        if candidate:
            return candidate.title()
    if object_id:
        near_id = re.search(
            rf"\b([A-ZÅÄÖ][A-Za-zÅÄÖåäö\-]{{1,30}})\s+{re.escape(object_id)}\b",
            visible,
        )
        if near_id:
            return near_id.group(1).strip()
    return None


def _quantity(item_context: str) -> int | None:
    total = _TOTAL_RE.search(item_context)
    if total:
        return int(total.group("count"))
    direct_counts = [
        int(match.group("count")) for match in _QUANTITY_RE.finditer(item_context)
    ]
    if len(direct_counts) >= 2:
        return sum(direct_counts)
    if direct_counts:
        return direct_counts[0]
    counts = [int(match.group("count")) for match in _ANTAL_RE.finditer(item_context)]
    if len(counts) >= 2:
        return sum(counts)
    return counts[0] if counts else None


def _parse_sek(text: str, labels: tuple[str, ...]) -> int | None:
    normalized = _compact(text)
    label_pattern = "|".join(re.escape(label) for label in labels)
    patterns = (
        rf"(?:{label_pattern})\s*(?:på|ca|:)?\s*([0-9][0-9 .]*)\s*(?:sek|kr|:-)?",
        rf"([0-9][0-9 .]*)\s*(?:sek|kr)\s*(?:{label_pattern})",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized, re.I)
        if not match:
            continue
        digits = re.sub(r"[^0-9]", "", match.group(1))
        if digits:
            value = int(digits)
            if value > 0:
                return value
    return None


def _commercial_summary(visible: str) -> str:
    phrases: list[str] = []
    normalized = _compact(visible)
    for term in (*_ENDED_TERMS, *_ACTIVE_TERMS):
        if term in normalized:
            phrases.append(term)
    bid = _parse_sek(visible, ("vinnande bud", "högsta bud", "winning bid", "highest bid"))
    reference = _parse_sek(visible, ("marknadsvärde", "butikspris", "market value", "retail price"))
    if bid is not None:
        phrases.append(f"source bid value: {bid} SEK")
    if reference is not None:
        phrases.append(f"source reference value: {reference} SEK")
    if "lasthjälp finns ej" in normalized or "loading assistance is not available" in normalized:
        phrases.append("loading assistance: unavailable")
    elif "lasthjälp finns" in normalized or "loading assistance is available" in normalized:
        phrases.append("loading assistance: available")
    if "ansvarar själv för hämtning och frakt" in normalized or "responsible for pickup and transportation" in normalized:
        phrases.append("buyer responsible for pickup and transport")
    return " | ".join(dict.fromkeys(phrases))


def verify_blinto_public_page(url: str, *, timeout: float = 15.0) -> PageVerification:
    """Verify one exact public Blinto auction page without login."""
    identity = canonicalize_blinto_auction_url(url)
    if identity is None:
        return PageVerification(url=url, error="not an exact public Blinto auction URL")
    request_url = identity.canonical_url.replace(
        "https://blinto.se/", "https://www.blinto.se/", 1
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
        return PageVerification(url=identity.canonical_url, verified=False, error=str(exc))

    final_identity = canonicalize_blinto_auction_url(response.url)
    if final_identity is None:
        return PageVerification(
            url=identity.canonical_url,
            verified=False,
            error="redirected outside an exact Blinto auction page",
        )

    decoded = response.text
    base = enrich_sweden_page_verification(
        verify_public_html(final_identity.canonical_url, decoded)
    )
    visible = _strip_html(decoded)
    description = _description_section(visible)
    item_context = " ".join(value for value in (base.title, description) if value)
    normalized_item = _compact(item_context)
    normalized_visible = _compact(visible)

    ended = any(term in normalized_visible for term in _ENDED_TERMS)
    active = not ended and any(term in normalized_visible for term in _ACTIVE_TERMS)
    noise = _is_noise(normalized_item)
    clothing = not noise and any(term in normalized_item for term in _CLOTHING_TERMS)
    bulk = not noise and _has_bulk_scope(normalized_item)
    occurrence_identity = (
        f"blinto-auction:{final_identity.object_id}:{final_identity.occurrence_id}"
        if final_identity.object_id and final_identity.occurrence_id
        else f"item-url:{final_identity.canonical_url}"
    )
    summary = _commercial_summary(visible)
    bounded = " | ".join(value for value in (description, summary) if value)

    return replace(
        base,
        url=final_identity.canonical_url,
        text=description[:2000] or base.text,
        location=_location(visible, final_identity.object_id),
        inventory_type=_inventory_type(item_context),
        price_nok=None,
        bid_price_nok=None,
        quantity=_quantity(item_context) if not noise else None,
        listing_status=ENDED if ended else ACTIVE if active else UNKNOWN,
        page_role=ITEM_LISTING,
        opportunity_identity=occurrence_identity,
        identity_stable=True,
        clothing_inventory_evidence=clothing and bulk,
        sale_evidence=active and clothing and bulk,
        event_scenario=_scenario_from_item_context(item_context),
        bounded_context=bounded[:5000] or base.bounded_context,
        verified=True,
        error=None,
    )


def enrich_blinto_discovery_result(result: Mapping[str, Any]) -> dict[str, Any]:
    """Attach source-native IDs and SEK values without altering lifecycle gates."""
    enriched = deepcopy(dict(result))
    enriched_count = 0
    bid_count = 0
    reference_count = 0
    for key in ("all_discovered_candidates", "discovery_top5"):
        for candidate in enriched.get(key) or ():
            source_urls = candidate.get("source_urls") or ()
            identity = next(
                (
                    parsed
                    for parsed in (
                        canonicalize_blinto_auction_url(str(url)) for url in source_urls
                    )
                    if parsed is not None
                ),
                None,
            )
            if identity is None:
                continue
            candidate["source_object_id"] = identity.object_id
            candidate["auction_occurrence_id"] = identity.occurrence_id
            candidate["duplicate_count"] = max(
                int(candidate.get("duplicate_count") or 0),
                max(0, len(candidate.get("found_by_queries") or ()) - 1),
            )
            verification = next(iter(candidate.get("verification") or ()), {})
            context = str(verification.get("bounded_context") or verification.get("text") or "")
            bid = _parse_sek(context, ("source bid value", "vinnande bud", "högsta bud"))
            reference = _parse_sek(
                context,
                ("source reference value", "marknadsvärde", "butikspris"),
            )
            confirmed = list(candidate.get("confirmed_information") or ())
            if bid is not None:
                candidate["bid_price_sek"] = bid
                candidate["bid_price_currency"] = "SEK"
                candidate["bid_price_is_nok"] = False
                text = f"public Blinto bid value: {bid} SEK"
                if text not in confirmed:
                    confirmed.append(text)
            if reference is not None:
                candidate["reference_value_sek"] = reference
                candidate["reference_value_kind"] = "market_or_retail_reference"
                candidate["reference_value_is_current_sale_price"] = False
                text = f"public Blinto reference value: {reference} SEK (not current sale price)"
                if text not in confirmed:
                    confirmed.append(text)
            compact_context = _compact(context)
            if "loading assistance: available" in compact_context:
                candidate["loading_assistance_available"] = True
            elif "loading assistance: unavailable" in compact_context:
                candidate["loading_assistance_available"] = False
            if "buyer responsible for pickup and transport" in compact_context:
                candidate["buyer_responsible_for_pickup_and_transport"] = True
            candidate["confirmed_information"] = confirmed
            if key == "all_discovered_candidates":
                enriched_count += 1
                bid_count += int(bid is not None)
                reference_count += int(reference is not None)

    report = enriched.get("search_run_report")
    if isinstance(report, dict):
        report["source_page_enrichment"] = {
            "source": "BLINTO",
            "candidates_enriched": enriched_count,
            "sek_bid_values_extracted": bid_count,
            "sek_reference_values_extracted": reference_count,
            "nok_price_fields_written": False,
            "listing_status_changed": False,
            "top5_eligibility_changed": False,
        }
    return enriched
