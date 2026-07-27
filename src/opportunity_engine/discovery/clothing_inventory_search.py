"""Discovery-first Clothing Inventory search, qualification, merging and ranking.

This module intentionally stops before financial analysis. It discovers public
commercial signals, preserves incomplete leads, merges multi-source evidence,
and ranks candidates by discovery strength only.
"""
from __future__ import annotations

import html
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider

CONFIRMED_SALE = "CONFIRMED_SALE"
STRONG_LEAD_REQUIRES_VERIFICATION = "STRONG_LEAD_REQUIRES_VERIFICATION"
REJECTED_NOISE = "REJECTED_NOISE"
ACTIVE = "ACTIVE"
ENDED = "ENDED"
UNKNOWN = "UNKNOWN"

_TRACKING_PARAMETERS = {
    "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "referrer", "source",
    "utm_campaign", "utm_content", "utm_medium", "utm_source", "utm_term",
}

_EVENT_TERMS: dict[str, tuple[str, ...]] = {
    "COMPANY_BANKRUPTCY": ("konkursbo", "konkurs", "tvangsavvikling"),
    "STORE_CLOSING": ("opphør", "opphørssalg", "avvikling", "butikk stenger", "butikken stenger"),
    "BRANCH_CLOSURE": ("filial legges ned", "filial stenger", "avdeling stenger"),
    "INVENTORY_LIQUIDATION": ("lager ryddes", "lageravvikling", "tømmesalg", "likvidasjon"),
    "AUCTION": ("auksjon", "nettauksjon", "budrunde"),
    "WAREHOUSE_SURPLUS": ("restlager", "overskuddslager", "overskuddsvarer"),
    "LARGE_LOT_SALE": ("vareparti", "klesparti", "stort parti", "samlet salg"),
}
_EVENT_PRIORITY = {
    "COMPANY_BANKRUPTCY": 25,
    "BRANCH_CLOSURE": 24,
    "STORE_CLOSING": 23,
    "INVENTORY_LIQUIDATION": 22,
    "AUCTION": 21,
    "WAREHOUSE_SURPLUS": 18,
    "LARGE_LOT_SALE": 16,
}
_CLOTHING_TERMS = (
    "klær", "klesbutikk", "kleslager", "sko", "arbeidstøy", "sportsklær",
    "tekstil", "mote", "bekledning", "varelager", "restlager", "klesparti",
)
_INVENTORY_TERMS = (
    "varelager", "hele lageret", "hele varelageret", "komplett lager", "restlager",
    "overskuddslager", "vareparti", "klesparti", "parti med klær", "lagerbeholdning",
)
_SALE_TERMS = (
    "selges", "til salgs", "auksjon", "budrunde", "samlet salg", "hele lageret",
    "overtas", "opphørssalg", "tømmesalg", "pris", "høyeste bud",
)
_BUSINESS_TERMS = (
    "butikk", "klesbutikk", "selskap", "bedrift", "as ", "grossist", "importør",
    "forhandler", "lager", "konkursbo", "filial", "vareparti",
)
_JOB_TERMS = ("ledig stilling", "jobb", "søker medarbeider", "karriere", "stilling ledig")
_GENERIC_INFO_TERMS = ("ordbok", "definisjon", "hva er", "guide", "wikipedia", "podcast")
_ORDINARY_SHOP_TERMS = ("ny kolleksjon", "handle nå", "nettbutikk", "fri frakt", "shop online")
_SINGLE_ITEM_TERMS = ("jakke", "kjole", "bukse", "skjorte", "genser", "frakk", "dress", "skjørt")
_ENDED_TERMS = ("avsluttet", "utløpt", "solgt", "auksjonen er avsluttet", "ended", "expired")
_ACTIVE_TERMS = ("aktiv", "pågående", "til salgs", "selges", "budfrist", "auksjon pågår")
_NORWAY_LOCATION_TERMS = (
    "norge", "trøndelag", "oslo", "bergen", "trondheim", "stavanger", "tromsø",
    "namsos", "kolvereid", "steinkjer", "mo i rana", "kristiansand", "drammen",
)
_ENTITY_STOPWORDS = {
    "as", "asa", "butikk", "butikken", "klesbutikk", "klær", "sko", "varelager",
    "konkurs", "konkursbo", "opphør", "opphørssalg", "avvikling", "selges", "salg",
    "til", "og", "i", "på", "for", "fra", "med", "hele", "lageret", "norge",
    "auksjon", "nettauksjon", "stenger", "legges", "ned", "restlager", "vareparti",
    "klesparti", "stort", "samlet",
}


@dataclass(frozen=True, slots=True)
class DiscoveryQuery:
    query_id: str
    scenario: str
    intent: str
    asset_scope: str
    query: str
    rotation_group: str = "PRIMARY"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


CLOTHING_INVENTORY_QUERY_MATRIX: tuple[DiscoveryQuery, ...] = (
    DiscoveryQuery("sale-01", "INVENTORY_LIQUIDATION", "SALE_INTENT", "CLOTHING_INVENTORY", "klesbutikk varelager selges Norge"),
    DiscoveryQuery("sale-02", "LARGE_LOT_SALE", "SALE_INTENT", "CLOTHING_INVENTORY", "hele lageret klær til salgs Norge"),
    DiscoveryQuery("sale-03", "AUCTION", "SALE_INTENT", "CLOTHING_INVENTORY", "vareparti klær auksjon Norge"),
    DiscoveryQuery("sale-04", "WAREHOUSE_SURPLUS", "SALE_INTENT", "CLOTHING_INVENTORY", "restlager klær selges Norge"),
    DiscoveryQuery("sale-05", "COMPANY_BANKRUPTCY", "SALE_INTENT", "CLOTHING_INVENTORY", "konkursbo klær auksjon Norge"),
    DiscoveryQuery("sale-06", "STORE_CLOSING", "SALE_INTENT", "CLOTHING_INVENTORY", "opphørssalg klesbutikk hele lageret Norge"),
    DiscoveryQuery("lead-01", "COMPANY_BANKRUPTCY", "EVENT_LEAD", "CLOTHING_INVENTORY", "konkurs klesbutikk varelager Norge"),
    DiscoveryQuery("lead-02", "STORE_CLOSING", "EVENT_LEAD", "CLOTHING_INVENTORY", "klesbutikk avvikling Norge"),
    DiscoveryQuery("lead-03", "STORE_CLOSING", "EVENT_LEAD", "CLOTHING_INVENTORY", "butikk stenger klær Norge"),
    DiscoveryQuery("lead-04", "BRANCH_CLOSURE", "EVENT_LEAD", "CLOTHING_INVENTORY", "filial legges ned klesbutikk Norge"),
    DiscoveryQuery("lead-05", "INVENTORY_LIQUIDATION", "EVENT_LEAD", "CLOTHING_INVENTORY", "lager ryddes klesbutikk Norge"),
    DiscoveryQuery("lead-06", "STORE_CLOSING", "EVENT_LEAD", "CLOTHING_INVENTORY", "opphør klesbutikk Trøndelag"),
    DiscoveryQuery("special-01", "INVENTORY_LIQUIDATION", "SPECIALIZED", "CLOTHING_INVENTORY", '"hele varelageret" klær samlet salg Norge', "SECONDARY"),
    DiscoveryQuery("special-02", "LARGE_LOT_SALE", "SPECIALIZED", "CLOTHING_INVENTORY", '"stort klesparti" selges Norge', "SECONDARY"),
    DiscoveryQuery("special-03", "WAREHOUSE_SURPLUS", "SPECIALIZED", "CLOTHING_INVENTORY", '"arbeidstøy" restlager parti Norge', "SECONDARY"),
    DiscoveryQuery("special-04", "COMPANY_BANKRUPTCY", "SPECIALIZED", "CLOTHING_INVENTORY", '"sportsklær" konkursbo varelager Norge', "SECONDARY"),
)


@dataclass(frozen=True, slots=True)
class PageVerification:
    url: str
    title: str | None = None
    text: str | None = None
    company_name: str | None = None
    location: str | None = None
    inventory_type: str | None = None
    price_nok: float | None = None
    quantity: int | None = None
    published_at: str | None = None
    listing_status: str = UNKNOWN
    verified: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PageVerifier(Protocol):
    def __call__(self, url: str) -> PageVerification: ...


@dataclass(slots=True)
class CandidateObservation:
    title: str
    url: str
    canonical_url: str
    description: str
    provider: str
    query: DiscoveryQuery
    scenario: str
    state: str
    reason: str
    signals: tuple[str, ...]
    location: str | None = None
    listing_status: str = UNKNOWN


@dataclass(slots=True)
class MergedCandidate:
    title: str
    scenario: str
    state: str
    reason: str
    source_urls: list[str] = field(default_factory=list)
    canonical_urls: list[str] = field(default_factory=list)
    found_by_queries: list[str] = field(default_factory=list)
    source_providers: list[str] = field(default_factory=list)
    evidence_signals: list[str] = field(default_factory=list)
    descriptions: list[str] = field(default_factory=list)
    company_name: str | None = None
    location: str | None = None
    inventory_type: str | None = None
    price_nok: float | None = None
    quantity: int | None = None
    published_at: str | None = None
    listing_status: str = UNKNOWN
    verification: list[dict[str, Any]] = field(default_factory=list)
    discovery_score: int = 0
    discovery_band: str = "LOW"
    score_breakdown: dict[str, int] = field(default_factory=dict)
    why_opportunity: list[str] = field(default_factory=list)
    confirmed_information: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    next_verification_step: str = ""

    @property
    def duplicate_count(self) -> int:
        return max(0, len(self.source_urls) - 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "scenario": self.scenario,
            "opportunity_state": self.state,
            "reason": self.reason,
            "discovery_score": self.discovery_score,
            "discovery_band": self.discovery_band,
            "score_breakdown": dict(self.score_breakdown),
            "location": self.location,
            "company_name": self.company_name,
            "inventory_type": self.inventory_type,
            "price_nok": self.price_nok,
            "quantity": self.quantity,
            "published_at": self.published_at,
            "listing_status": self.listing_status,
            "source_urls": list(self.source_urls),
            "source_providers": list(self.source_providers),
            "found_by_queries": list(self.found_by_queries),
            "duplicate_count": self.duplicate_count,
            "evidence_signals": list(self.evidence_signals),
            "why_opportunity": list(self.why_opportunity),
            "confirmed_information": list(self.confirmed_information),
            "missing_information": list(self.missing_information),
            "next_verification_step": self.next_verification_step,
            "verification": list(self.verification),
        }


def normalize_public_url(url: str) -> str:
    """Normalize one public HTTPS URL and remove tracking-only parameters."""
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        return ""
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    query = urlencode(sorted(
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_PARAMETERS
    ))
    return urlunparse(("https", host, path, "", query, ""))


def _normalized_text(*values: str | None) -> str:
    return " ".join(" ".join(value.lower().split()) for value in values if value)


def _term_hits(text: str, terms: Sequence[str]) -> tuple[str, ...]:
    return tuple(term for term in terms if term in text)


def _scenario_from_text(text: str, fallback: str) -> tuple[str, tuple[str, ...]]:
    matches: list[tuple[int, str, str]] = []
    for scenario, terms in _EVENT_TERMS.items():
        for term in terms:
            if term in text:
                matches.append((_EVENT_PRIORITY[scenario], scenario, term))
    if not matches:
        return fallback, ()
    _, scenario, _ = max(matches)
    return scenario, tuple(dict.fromkeys(term for _, candidate_scenario, term in matches if candidate_scenario == scenario))


def classify_search_hit(hit: SearchHit, query: DiscoveryQuery) -> CandidateObservation:
    """Classify a search hit into confirmed sale, strong lead, or rejected noise."""
    canonical_url = normalize_public_url(hit.url)
    if not hit.title.strip() or not canonical_url:
        return CandidateObservation(hit.title.strip(), hit.url.strip(), canonical_url, hit.description.strip(), hit.provider, query, query.scenario, REJECTED_NOISE, "missing public title or HTTPS URL", ())

    text = _normalized_text(hit.title, hit.description)
    scenario, event_hits = _scenario_from_text(text, query.scenario)
    clothing_hits = _term_hits(text, _CLOTHING_TERMS)
    inventory_hits = _term_hits(text, _INVENTORY_TERMS)
    sale_hits = _term_hits(text, _SALE_TERMS)
    business_hits = _term_hits(text, _BUSINESS_TERMS)
    has_event = bool(event_hits)
    has_clothing_scope = bool(clothing_hits)
    has_inventory_scope = bool(inventory_hits)
    has_business = bool(business_hits)

    if any(term in text for term in _JOB_TERMS):
        state, reason = REJECTED_NOISE, "job advertisement"
    elif any(term in text for term in _GENERIC_INFO_TERMS) and not (has_event and has_clothing_scope):
        state, reason = REJECTED_NOISE, "informational page without a traceable commercial event"
    elif any(term in text for term in _ORDINARY_SHOP_TERMS) and not has_event and not has_inventory_scope:
        state, reason = REJECTED_NOISE, "ordinary online store"
    else:
        single_item = any(re.search(rf"\b{re.escape(term)}\b", text) for term in _SINGLE_ITEM_TERMS)
        if single_item and not has_inventory_scope and not has_event and not has_business:
            state, reason = REJECTED_NOISE, "ordinary single-item listing"
        elif sale_hits and has_clothing_scope and (has_inventory_scope or has_business or has_event):
            state, reason = CONFIRMED_SALE, "public sale signal with clothing-inventory context"
        elif has_event and has_clothing_scope and (has_inventory_scope or has_business):
            state, reason = STRONG_LEAD_REQUIRES_VERIFICATION, "traceable clothing-business event; sale availability requires verification"
        else:
            state, reason = REJECTED_NOISE, "insufficient clothing-inventory commercial evidence"

    signals = tuple(dict.fromkeys((*event_hits, *clothing_hits, *inventory_hits, *sale_hits)))
    listing_status = ENDED if any(term in text for term in _ENDED_TERMS) else ACTIVE if any(term in text for term in _ACTIVE_TERMS) else UNKNOWN
    return CandidateObservation(
        title=hit.title.strip(),
        url=hit.url.strip(),
        canonical_url=canonical_url,
        description=hit.description.strip(),
        provider=hit.provider.strip(),
        query=query,
        scenario=scenario,
        state=state,
        reason=reason,
        signals=signals,
        location=_extract_location(text),
        listing_status=listing_status,
    )


def _entity_tokens(title: str, description: str = "") -> set[str]:
    text = _normalized_text(title, description)
    tokens = re.findall(r"[a-zæøå0-9]{2,}", text)
    return {token for token in tokens if token not in _ENTITY_STOPWORDS and not token.isdigit()}


def _same_opportunity(left: CandidateObservation, right: CandidateObservation) -> bool:
    if left.canonical_url and left.canonical_url == right.canonical_url:
        return True
    # Use titles for entity identity. Search descriptions are often generic and
    # would otherwise merge unrelated lots that share words such as varelager.
    left_tokens = _entity_tokens(left.title)
    right_tokens = _entity_tokens(right.title)
    overlap = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    jaccard = overlap / union if union else 0.0
    compatible_location = not left.location or not right.location or left.location == right.location
    same_event = left.scenario == right.scenario or {left.scenario, right.scenario} <= {"STORE_CLOSING", "INVENTORY_LIQUIDATION"}
    return compatible_location and same_event and overlap >= 2 and jaccard >= 0.34


def _merge_observations(observations: Sequence[CandidateObservation]) -> list[MergedCandidate]:
    groups: list[list[CandidateObservation]] = []
    for observation in observations:
        for group in groups:
            if any(_same_opportunity(observation, existing) for existing in group):
                group.append(observation)
                break
        else:
            groups.append([observation])

    merged: list[MergedCandidate] = []
    state_priority = {REJECTED_NOISE: 0, STRONG_LEAD_REQUIRES_VERIFICATION: 1, CONFIRMED_SALE: 2}
    for group in groups:
        best = max(group, key=lambda item: (state_priority[item.state], len(item.description), len(item.title)))
        candidate = MergedCandidate(title=best.title, scenario=best.scenario, state=best.state, reason=best.reason)
        for item in group:
            _append_unique(candidate.source_urls, item.url)
            _append_unique(candidate.canonical_urls, item.canonical_url)
            _append_unique(candidate.found_by_queries, item.query.query_id)
            if item.provider:
                _append_unique(candidate.source_providers, item.provider)
            for signal in item.signals:
                _append_unique(candidate.evidence_signals, signal)
            if item.description:
                _append_unique(candidate.descriptions, item.description)
            if not candidate.location and item.location:
                candidate.location = item.location
            if item.listing_status == ENDED:
                candidate.listing_status = ENDED
            elif item.listing_status == ACTIVE and candidate.listing_status == UNKNOWN:
                candidate.listing_status = ACTIVE
        merged.append(candidate)
    return merged


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def _extract_location(text: str) -> str | None:
    for location in _NORWAY_LOCATION_TERMS:
        if location != "norge" and re.search(rf"\b{re.escape(location)}\b", text):
            return location.title()
    return None


def _extract_price(text: str) -> float | None:
    match = re.search(r"(?:kr|nok)\s*([0-9][0-9 .]{2,})|([0-9][0-9 .]{2,})\s*(?:kr|nok)", text, re.I)
    if not match:
        return None
    raw = (match.group(1) or match.group(2)).replace(" ", "").replace(".", "")
    try:
        return float(raw)
    except ValueError:
        return None


def _extract_quantity(text: str) -> int | None:
    match = re.search(r"\b(\d{2,6})\s*(?:stk|plagg|varer|enheter|par)\b", text, re.I)
    return int(match.group(1)) if match else None


def verify_public_page(url: str, *, timeout: float = 12.0) -> PageVerification:
    """Read one public HTTPS page without login or bypass behavior."""
    canonical = normalize_public_url(url)
    if not canonical:
        return PageVerification(url=url, error="non-HTTPS or invalid URL")
    request = Request(canonical, headers={"User-Agent": "OpportunityEngine-Discovery/2.0"})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - validated HTTPS public page
            final_url = normalize_public_url(response.geturl())
            if not final_url:
                return PageVerification(url=url, error="redirected outside HTTPS")
            raw = response.read(1_500_000)
    except Exception as exc:  # public verification failure must remain explicit
        return PageVerification(url=canonical, error=str(exc))

    decoded = raw.decode("utf-8", errors="replace")
    title_match = re.search(r"<title[^>]*>(.*?)</title>", decoded, re.I | re.S)
    title = html.unescape(re.sub(r"\s+", " ", title_match.group(1)).strip()) if title_match else None
    visible = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", decoded, flags=re.I | re.S)
    visible = html.unescape(re.sub(r"<[^>]+>", " ", visible))
    visible = " ".join(visible.split())[:20000]
    normalized = visible.lower()
    listing_status = ENDED if any(term in normalized for term in _ENDED_TERMS) else ACTIVE if any(term in normalized for term in _ACTIVE_TERMS) else UNKNOWN
    inventory_type = next((term for term in _CLOTHING_TERMS if term in normalized), None)
    return PageVerification(
        url=canonical,
        title=title,
        text=visible[:2000] or None,
        location=_extract_location(normalized),
        inventory_type=inventory_type,
        price_nok=_extract_price(visible),
        quantity=_extract_quantity(visible),
        listing_status=listing_status,
        verified=True,
    )


def _apply_verification(candidate: MergedCandidate, result: PageVerification) -> None:
    candidate.verification.append(result.to_dict())
    if not result.verified:
        return
    if result.title and len(result.title) > len(candidate.title):
        candidate.title = result.title
    candidate.company_name = candidate.company_name or result.company_name
    candidate.location = candidate.location or result.location
    candidate.inventory_type = candidate.inventory_type or result.inventory_type
    candidate.price_nok = candidate.price_nok if candidate.price_nok is not None else result.price_nok
    candidate.quantity = candidate.quantity if candidate.quantity is not None else result.quantity
    candidate.published_at = candidate.published_at or result.published_at
    if result.listing_status == ENDED:
        candidate.listing_status = ENDED
    elif result.listing_status == ACTIVE and candidate.listing_status == UNKNOWN:
        candidate.listing_status = ACTIVE
    combined = _normalized_text(result.title, result.text)
    verified_hit = SearchHit(result.title or candidate.title, result.url, result.text or "", "public-page-verification")
    query = DiscoveryQuery("verification", candidate.scenario, "VERIFICATION", "CLOTHING_INVENTORY", "public page")
    classification = classify_search_hit(verified_hit, query)
    if classification.state == CONFIRMED_SALE:
        candidate.state = CONFIRMED_SALE
        candidate.reason = "sale confirmed by public-page evidence"
    elif classification.state == STRONG_LEAD_REQUIRES_VERIFICATION and candidate.state == REJECTED_NOISE:
        candidate.state = STRONG_LEAD_REQUIRES_VERIFICATION
        candidate.reason = "commercial event retained after public-page verification"
    for signal in classification.signals:
        _append_unique(candidate.evidence_signals, signal)
    if any(term in combined for term in _ENDED_TERMS):
        candidate.listing_status = ENDED


def _freshness_points(published_at: str | None, observed_at: datetime) -> int:
    if not published_at:
        return 0
    try:
        published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
    except ValueError:
        return 0
    age_days = max(0, (observed_at - published.astimezone(timezone.utc)).days)
    return 10 if age_days <= 30 else 7 if age_days <= 90 else 3 if age_days <= 365 else 0


def score_discovery_candidate(candidate: MergedCandidate, *, observed_at: datetime | None = None) -> None:
    """Apply the discovery-only 100 point score; never use profit or ROI."""
    observed = observed_at or datetime.now(timezone.utc)
    event_strength = _EVENT_PRIORITY.get(candidate.scenario, 0)
    text = _normalized_text(candidate.title, *candidate.descriptions, " ".join(candidate.evidence_signals))
    inventory_clarity = 20 if any(term in text for term in _INVENTORY_TERMS) and any(term in text for term in _CLOTHING_TERMS) else 12 if any(term in text for term in _CLOTHING_TERMS) else 0
    sale_signal = 20 if candidate.state == CONFIRMED_SALE else 8 if candidate.state == STRONG_LEAD_REQUIRES_VERIFICATION else 0
    traceability = 15 if candidate.source_urls and all(normalize_public_url(url) for url in candidate.source_urls) else 0
    freshness = _freshness_points(candidate.published_at, observed)
    logistics = 5 if candidate.location or any(term in text for term in _NORWAY_LOCATION_TERMS) else 0
    price_or_quantity = 5 if candidate.price_nok is not None or candidate.quantity is not None else 0
    breakdown = {
        "commercial_event_strength": event_strength,
        "clothing_inventory_clarity": inventory_clarity,
        "sale_signal": sale_signal,
        "source_traceability": traceability,
        "freshness": freshness,
        "location_logistics": logistics,
        "price_or_quantity": price_or_quantity,
    }
    candidate.score_breakdown = breakdown
    candidate.discovery_score = sum(breakdown.values())
    candidate.discovery_band = "HIGH" if candidate.discovery_score >= 80 else "REVIEW" if candidate.discovery_score >= 55 else "LOW"
    candidate.why_opportunity = []
    if event_strength:
        candidate.why_opportunity.append(f"commercial event detected: {candidate.scenario}")
    if inventory_clarity:
        candidate.why_opportunity.append("clothing inventory or commercial lot evidence detected")
    if sale_signal == 20:
        candidate.why_opportunity.append("public sale signal detected")
    elif sale_signal:
        candidate.why_opportunity.append("strong event lead retained without requiring a sale word in the search snippet")
    candidate.confirmed_information = [
        f"traceable public sources: {len(candidate.source_urls)}",
        f"discovery state: {candidate.state}",
    ]
    if candidate.location:
        candidate.confirmed_information.append(f"location: {candidate.location}")
    if candidate.price_nok is not None:
        candidate.confirmed_information.append(f"public price: {candidate.price_nok:g} NOK")
    if candidate.quantity is not None:
        candidate.confirmed_information.append(f"public quantity: {candidate.quantity}")
    candidate.missing_information = []
    if not candidate.location:
        candidate.missing_information.append("location")
    if candidate.price_nok is None:
        candidate.missing_information.append("price")
    if candidate.quantity is None:
        candidate.missing_information.append("quantity")
    if candidate.listing_status == UNKNOWN:
        candidate.missing_information.append("active/ended status")
    candidate.next_verification_step = (
        "Open the public source and verify that the inventory is still available."
        if candidate.state == CONFIRMED_SALE
        else "Verify publicly whether the estate, store or liquidator is offering the clothing inventory for sale."
    )


def run_clothing_inventory_discovery(
    provider: SearchProvider,
    *,
    queries: Iterable[DiscoveryQuery] = CLOTHING_INVENTORY_QUERY_MATRIX,
    discovered_at: str | None = None,
    results_per_query: int = 10,
    verifier: PageVerifier | None = None,
    verification_limit: int = 20,
) -> dict[str, Any]:
    """Run structured search and return traceable discovery artifacts in memory."""
    if not 1 <= results_per_query <= 20:
        raise ValueError("results_per_query must be between 1 and 20")
    if verification_limit < 0:
        raise ValueError("verification_limit must not be negative")
    timestamp = discovered_at or datetime.now(timezone.utc).isoformat()
    clean_queries: list[DiscoveryQuery] = []
    seen_query_ids: set[str] = set()
    for query in queries:
        if query.query_id not in seen_query_ids and query.query.strip():
            seen_query_ids.add(query.query_id)
            clean_queries.append(query)

    observations: list[CandidateObservation] = []
    errors: list[dict[str, str]] = []
    hits_received = 0
    domains: set[str] = set()
    for query in clean_queries:
        try:
            hits = provider.search(query.query, count=results_per_query)
        except Exception as exc:
            errors.append({"query_id": query.query_id, "query": query.query, "error": str(exc)})
            continue
        for hit in hits:
            hits_received += 1
            observation = classify_search_hit(hit, query)
            observations.append(observation)
            if observation.canonical_url:
                domains.add(urlparse(observation.canonical_url).netloc)

    unique_urls = {observation.canonical_url for observation in observations if observation.canonical_url}
    merged = _merge_observations(observations)
    non_rejected = [candidate for candidate in merged if candidate.state != REJECTED_NOISE]

    for candidate in non_rejected:
        score_discovery_candidate(candidate)
    verification_targets = sorted(non_rejected, key=lambda item: item.discovery_score, reverse=True)[:verification_limit]
    if verifier:
        for candidate in verification_targets:
            for url in candidate.source_urls[:3]:
                _apply_verification(candidate, verifier(url))
            score_discovery_candidate(candidate)

    for candidate in merged:
        if candidate not in non_rejected:
            score_discovery_candidate(candidate)

    active_candidates = [
        candidate for candidate in merged
        if candidate.state != REJECTED_NOISE and candidate.listing_status != ENDED
    ]
    top5 = sorted(active_candidates, key=lambda item: (item.discovery_score, len(item.source_urls)), reverse=True)[:5]
    all_payload = [candidate.to_dict() for candidate in sorted(merged, key=lambda item: item.discovery_score, reverse=True)]
    top5_payload = [candidate.to_dict() for candidate in top5]
    bands = {"HIGH": 0, "REVIEW": 0, "LOW": 0}
    for candidate in merged:
        bands[candidate.discovery_band] += 1
    report = {
        "schema_version": "clothing-inventory-discovery-search-1.0",
        "domain": "CLOTHING_INVENTORY",
        "discovered_at": timestamp,
        "provider": provider.name,
        "queries_submitted": len(clean_queries),
        "query_matrix": [query.to_dict() for query in clean_queries],
        "hits_received": hits_received,
        "unique_public_urls": len(unique_urls),
        "merged_candidates": len(merged),
        "duplicates_merged": max(0, len(observations) - len(merged)),
        "rejected_results": sum(candidate.state == REJECTED_NOISE for candidate in merged),
        "confirmed_sales": sum(candidate.state == CONFIRMED_SALE and candidate.listing_status != ENDED for candidate in merged),
        "strong_leads_requiring_verification": sum(candidate.state == STRONG_LEAD_REQUIRES_VERIFICATION and candidate.listing_status != ENDED for candidate in merged),
        "ended_or_historical": sum(candidate.listing_status == ENDED for candidate in merged),
        "sources_discovered": len(domains),
        "discovery_bands": bands,
        "verification_attempted": bool(verifier),
        "verification_limit": verification_limit,
        "top5_count": len(top5_payload),
        "errors": errors,
        "status": "PASS" if not errors else "PARTIAL",
        "no_opportunities_found": not top5_payload,
        "automatic_contact": False,
        "automatic_purchase_decision": False,
        "financial_ranking_used": False,
    }
    return {"search_run_report": report, "all_discovered_candidates": all_payload, "discovery_top5": top5_payload}


def write_discovery_artifacts(result: Mapping[str, Any], output_dir: str | Path) -> dict[str, Path]:
    """Write the four approved operator artifacts."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    paths = {
        "search_run_report": destination / "search-run-report.json",
        "all_discovered_candidates": destination / "all-discovered-candidates.json",
        "discovery_top5": destination / "discovery-top5.json",
        "operator_summary": destination / "operator-summary.txt",
    }
    for key in ("search_run_report", "all_discovered_candidates", "discovery_top5"):
        paths[key].write_text(json.dumps(result[key], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = result["search_run_report"]
    top5 = result["discovery_top5"]
    lines = [
        "Clothing Inventory Discovery Search",
        f"Status: {report['status']}",
        f"Queries: {report['queries_submitted']}",
        f"Hits: {report['hits_received']}",
        f"Merged candidates: {report['merged_candidates']}",
        f"Confirmed sales: {report['confirmed_sales']}",
        f"Strong leads requiring verification: {report['strong_leads_requiring_verification']}",
        f"Rejected noise: {report['rejected_results']}",
        f"Top opportunities: {len(top5)}",
    ]
    if not top5:
        lines.append("No active traceable Clothing Inventory opportunity was found in this run.")
    else:
        for index, candidate in enumerate(top5, 1):
            lines.append(f"{index}. [{candidate['opportunity_state']}] {candidate['title']} — discovery score {candidate['discovery_score']}")
    paths["operator_summary"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    return paths
