"""Discovery-first Clothing Inventory search, verification and ranking.

This module intentionally stops before financial analysis. It discovers public
commercial signals, preserves incomplete leads, fails closed during public-page
verification, and ranks only specific traceable opportunities.
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

ITEM_LISTING = "ITEM_LISTING"
CATEGORY_INDEX = "CATEGORY_INDEX"
SOURCE_CHANNEL = "SOURCE_CHANNEL"
ORDINARY_STORE = "ORDINARY_STORE"
ARTICLE_OR_INFO = "ARTICLE_OR_INFO"
UNRESOLVED_SOURCE = "UNRESOLVED_SOURCE"
UNVERIFIED_EVENT = "UNVERIFIED_EVENT"

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
    "LARGE_LOT_SALE": ("vareparti", "klesparti", "partisalg", "stort parti", "samlet salg"),
}
_EVENT_PRIORITY = {
    "COMPANY_BANKRUPTCY": 25,
    "BRANCH_CLOSURE": 24,
    "STORE_CLOSING": 23,
    "INVENTORY_LIQUIDATION": 22,
    "AUCTION": 21,
    "WAREHOUSE_SURPLUS": 18,
    "LARGE_LOT_SALE": 16,
    UNVERIFIED_EVENT: 0,
}
_CLOTHING_TERMS = (
    "klær", "klesbutikk", "kleslager", "sko", "arbeidstøy", "sportsklær",
    "tekstil", "mote", "bekledning", "klesparti", "klesmerke", "plagg",
    "arbeidsjakke", "strømpebukse", "skjorte", "hettegenser", "genser", "joggebukse",
)
_INVENTORY_TERMS = (
    "varelager", "hele lageret", "hele varelageret", "komplett lager", "restlager",
    "overskuddslager", "vareparti", "klesparti", "parti med klær", "lagerbeholdning",
    "partisalg",
)
_STRONG_SALE_TERMS = (
    "selges", "til salgs", "budrunde", "samlet salg", "hele lageret",
    "overtas", "opphørssalg", "tømmesalg", "høyeste bud", "gi bud",
)
_AUCTION_TERMS = ("auksjon", "nettauksjon", "budfrist", "høyeste bud", "gi bud")
_BUSINESS_TERMS = (
    "butikk", "klesbutikk", "selskap", "bedrift", "as ", "grossist", "importør",
    "forhandler", "lager", "konkursbo", "filial", "vareparti",
)
_JOB_TERMS = ("ledig stilling", "jobb", "søker medarbeider", "karriere", "stilling ledig")
_GENERIC_INFO_TERMS = ("ordbok", "definisjon", "hva er", "guide", "wikipedia", "podcast")
_ORDINARY_SHOP_TERMS = (
    "ny kolleksjon", "handle nå", "nettbutikk", "fri frakt", "shop online",
    "åpent kjøp", "legg i handlekurv", "leveringstid", "klubbkolleksjon",
)
_SOURCE_CHANNEL_TERMS = (
    "vi kjøper ditt varelager", "tipse oss om et konkursbo", "oppkjøpte varelager",
    "varer fra konkursbo", "konkursbo, partivare", "partivare, restlager",
)
_CATEGORY_TERMS = (
    "filter", "sortering", "sorter", "treff", "fjern valg", "kategorier",
    "alle auksjoner", "nyeste auksjoner", "laveste bud", "høyeste bud",
    "filtre", "pris, lav til høy", "pris, høy til lav",
    "mest populære i kategorien", "side 1 av", "side1 av",
)
_RETAIL_CHECKOUT_TERMS = ("handlekurv", "til kassen", "fri frakt")
_SINGLE_ITEM_TERMS = ("jakke", "kjole", "bukse", "skjorte", "genser", "frakk", "dress", "skjørt")
_ENDED_TERMS = ("avsluttet", "utløpt", "solgt", "auksjonen er avsluttet", "ended", "expired")
_UNAVAILABLE_TERMS = (
    "auksjon ikke tilgjengelig",
    "auksjonen er ikke tilgjengelig",
    "annonsen er ikke tilgjengelig",
    "objektet er ikke tilgjengelig",
)
_ACTIVE_TERMS = ("aktiv", "pågående", "til salgs", "selges", "budfrist", "auksjon pågår", "gi bud")
_SHELL_TERMS = (
    "javascript må være aktivert", "enable javascript", "prøv nå", "gå tilbake til gammelt design",
)
_CART_CONTEXT_TERMS = (
    "kurv", "handlekurv", "cart", "subtotal", "delsum", "frakt", "checkout",
)
_NORWAY_LOCATION_TERMS = (
    "norge", "trøndelag", "oslo", "bergen", "trondheim", "stavanger", "tromsø",
    "namsos", "kolvereid", "steinkjer", "mo i rana", "kristiansand", "drammen",
    "støren", "ytre enebakk", "strømmen", "tolvsrød", "stathelle", "lierstranda",
)
_ENTITY_STOPWORDS = {
    "as", "asa", "butikk", "butikken", "klesbutikk", "klær", "sko", "varelager",
    "konkurs", "konkursbo", "opphør", "opphørssalg", "avvikling", "selges", "salg",
    "til", "og", "i", "på", "for", "fra", "med", "hele", "lageret", "norge",
    "auksjon", "nettauksjon", "stenger", "legges", "ned", "restlager", "vareparti",
    "klesparti", "stort", "samlet",
}
_GENERIC_TITLES = (
    "forside", "om oss", "torget", "vareparti-og-konkursbo", "alle produkter",
    "auksjon - konkursbo", "konkursbo, partivare, restlager",
)
_LISTING_PATH_TERMS = (
    "/lot/", "/listing/", "/item/", "/product/", "/produkt/", "/annonse/",
    "/auksjon/", "/auction/",
)


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
    bid_price_nok: float | None = None
    quantity: int | None = None
    published_at: str | None = None
    listing_status: str = UNKNOWN
    page_role: str = UNRESOLVED_SOURCE
    opportunity_identity: str | None = None
    identity_stable: bool = False
    clothing_inventory_evidence: bool = False
    sale_evidence: bool = False
    event_scenario: str = UNVERIFIED_EVENT
    bounded_context: str | None = None
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
    identity_stable: bool = False
    opportunity_identity: str | None = None
    page_role_hint: str = UNRESOLVED_SOURCE


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
    bid_price_nok: float | None = None
    quantity: int | None = None
    published_at: str | None = None
    listing_status: str = UNKNOWN
    page_role: str = UNRESOLVED_SOURCE
    opportunity_identity: str | None = None
    identity_stable: bool = False
    verification: list[dict[str, Any]] = field(default_factory=list)
    verification_succeeded: bool = False
    false_positive_guard_triggered: bool = False
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

    @property
    def top5_eligible(self) -> bool:
        return (
            self.page_role == ITEM_LISTING
            and self.identity_stable
            and self.listing_status in {ACTIVE, UNKNOWN}
            and self.state in {CONFIRMED_SALE, STRONG_LEAD_REQUIRES_VERIFICATION}
            and bool(self.source_urls)
            and all(normalize_public_url(url) for url in self.source_urls)
            and not (self.listing_status == UNKNOWN and self.state == CONFIRMED_SALE)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "scenario": self.scenario,
            "opportunity_state": self.state,
            "reason": self.reason,
            "page_role": self.page_role,
            "opportunity_identity": self.opportunity_identity,
            "identity_stable": self.identity_stable,
            "top5_eligible": self.top5_eligible,
            "discovery_score": self.discovery_score,
            "discovery_band": self.discovery_band,
            "score_breakdown": dict(self.score_breakdown),
            "location": self.location,
            "company_name": self.company_name,
            "inventory_type": self.inventory_type,
            "price_nok": self.price_nok,
            "bid_price_nok": self.bid_price_nok,
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


def _scenario_from_text(text: str) -> tuple[str, tuple[str, ...]]:
    matches: list[tuple[int, str, str]] = []
    for scenario, terms in _EVENT_TERMS.items():
        for term in terms:
            if term in text:
                matches.append((_EVENT_PRIORITY[scenario], scenario, term))
    if not matches:
        return UNVERIFIED_EVENT, ()
    _, scenario, _ = max(matches)
    return scenario, tuple(
        dict.fromkeys(term for _, candidate_scenario, term in matches if candidate_scenario == scenario)
    )


def _generic_title(title: str) -> bool:
    normalized = _normalized_text(title)
    return not normalized or any(normalized == term or normalized.startswith(f"{term} |") for term in _GENERIC_TITLES)


def _stable_identity(url: str, title: str, text: str = "") -> tuple[bool, str | None]:
    canonical = normalize_public_url(url)
    if not canonical or _generic_title(title):
        return False, None
    parsed = urlparse(canonical)
    path = parsed.path.lower()
    id_match = re.search(r"(?:^|[/_-])(\d{3,})(?:$|[/_-])", path)
    listing_path = any(term in path for term in _LISTING_PATH_TERMS)
    title_tokens = _entity_tokens(title)
    specific_title = len(title_tokens) >= 2 and not any(
        generic in _normalized_text(title) for generic in ("alle produkter", "kategorier", "om oss")
    )
    if id_match:
        return True, f"url-id:{id_match.group(1)}"
    if listing_path and specific_title:
        return True, f"item-url:{canonical}"
    event_scenario, event_hits = _scenario_from_text(_normalized_text(title, text))
    if specific_title and event_hits and any(term in _normalized_text(title, text) for term in _INVENTORY_TERMS):
        return True, f"event-title:{' '.join(sorted(title_tokens))}"
    return False, None


def classify_search_hit(hit: SearchHit, query: DiscoveryQuery) -> CandidateObservation:
    """Classify search evidence conservatively; search snippets never confirm a sale."""
    canonical_url = normalize_public_url(hit.url)
    if not hit.title.strip() or not canonical_url:
        return CandidateObservation(
            hit.title.strip(), hit.url.strip(), canonical_url, hit.description.strip(),
            hit.provider, query, UNVERIFIED_EVENT, REJECTED_NOISE,
            "missing public title or HTTPS URL", (),
        )

    text = _normalized_text(hit.title, hit.description)
    scenario, event_hits = _scenario_from_text(text)
    clothing_hits = _term_hits(text, _CLOTHING_TERMS)
    inventory_hits = _term_hits(text, _INVENTORY_TERMS)
    sale_hits = _term_hits(text, (*_STRONG_SALE_TERMS, *_AUCTION_TERMS))
    business_hits = _term_hits(text, _BUSINESS_TERMS)
    has_event = bool(event_hits)
    has_clothing_scope = bool(clothing_hits)
    has_inventory_scope = bool(inventory_hits)
    has_business = bool(business_hits)
    identity_stable, opportunity_identity = _stable_identity(canonical_url, hit.title, hit.description)
    parsed_path = urlparse(canonical_url).path.lower()
    page_role_hint = ITEM_LISTING if identity_stable and (
        any(term in parsed_path for term in _LISTING_PATH_TERMS)
        or bool(re.search(r"(?:^|[/_-])\d{3,}(?:$|[/_-])", parsed_path))
    ) else UNRESOLVED_SOURCE

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
        elif has_clothing_scope and (has_inventory_scope or has_business or has_event) and (sale_hits or has_event):
            state = STRONG_LEAD_REQUIRES_VERIFICATION
            reason = "specific commercial signal retained pending bounded public-page verification"
        else:
            state, reason = REJECTED_NOISE, "insufficient clothing-inventory commercial evidence"

    signals = tuple(dict.fromkeys((*event_hits, *clothing_hits, *inventory_hits, *sale_hits)))
    listing_status = ENDED if any(term in text for term in _ENDED_TERMS) else UNKNOWN
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
        location=None,
        listing_status=listing_status,
        identity_stable=identity_stable,
        opportunity_identity=opportunity_identity,
        page_role_hint=page_role_hint,
    )


def _entity_tokens(title: str, description: str = "") -> set[str]:
    text = _normalized_text(title, description)
    tokens = re.findall(r"[a-zæøå0-9]{2,}", text)
    return {token for token in tokens if token not in _ENTITY_STOPWORDS and not token.isdigit()}


def _same_opportunity(left: CandidateObservation, right: CandidateObservation) -> bool:
    if left.canonical_url and left.canonical_url == right.canonical_url:
        return True
    if (
        left.identity_stable
        and right.identity_stable
        and left.opportunity_identity != right.opportunity_identity
    ):
        return False
    left_tokens = _entity_tokens(left.title)
    right_tokens = _entity_tokens(right.title)
    overlap = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    jaccard = overlap / union if union else 0.0
    same_identity = (
        left.opportunity_identity
        and right.opportunity_identity
        and left.opportunity_identity == right.opportunity_identity
    )
    same_event = (
        left.scenario == right.scenario
        or UNVERIFIED_EVENT in {left.scenario, right.scenario}
        or {left.scenario, right.scenario} <= {"STORE_CLOSING", "INVENTORY_LIQUIDATION"}
    )
    return bool(same_identity or (same_event and overlap >= 2 and jaccard >= 0.34))


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
        candidate = MergedCandidate(
            title=best.title,
            scenario=best.scenario,
            state=best.state,
            reason=best.reason,
            page_role=best.page_role_hint,
            opportunity_identity=best.opportunity_identity,
            identity_stable=best.identity_stable,
        )
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
            if not candidate.identity_stable and item.identity_stable:
                candidate.identity_stable = True
                candidate.opportunity_identity = item.opportunity_identity
                candidate.page_role = item.page_role_hint
            if item.listing_status == ENDED:
                candidate.listing_status = ENDED
        merged.append(candidate)
    return merged


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def _extract_location(text: str) -> str | None:
    for location in _NORWAY_LOCATION_TERMS:
        if location != "norge" and re.search(rf"\b{re.escape(location)}\b", text, re.I):
            return location.title()
    return None


def _parse_money(raw: str) -> float | None:
    normalized = raw.replace("\xa0", " ").strip()
    normalized = re.sub(r"[^0-9,.\s]", "", normalized)
    if not normalized:
        return None
    normalized = normalized.replace(" ", "")
    if "," in normalized and "." in normalized:
        decimal_separator = (
            "," if normalized.rfind(",") > normalized.rfind(".") else "."
        )
        thousands_separator = "." if decimal_separator == "," else ","
        decimal_digits = len(normalized.rsplit(decimal_separator, 1)[-1])
        if decimal_digits <= 2:
            normalized = normalized.replace(thousands_separator, "")
            normalized = normalized.replace(decimal_separator, ".")
        else:
            normalized = normalized.replace(",", "").replace(".", "")
    elif "," in normalized:
        pieces = normalized.split(",")
        normalized = (
            "".join(pieces[:-1]) + "." + pieces[-1]
            if len(pieces[-1]) <= 2
            else "".join(pieces)
        )
    elif "." in normalized:
        pieces = normalized.split(".")
        normalized = (
            "".join(pieces[:-1]) + "." + pieces[-1]
            if len(pieces[-1]) <= 2
            else "".join(pieces)
        )
    try:
        value = float(normalized)
    except ValueError:
        return None
    return value if value > 0 else None


def _extract_price(text: str, *, bid: bool = False) -> float | None:
    patterns = (
        (r"(?:høyeste bud|bud)\s*(?:kr|nok)?\s*([0-9][0-9\s.,]*)",)
        if bid
        else (
            r"(?:pris|fastpris|kjøpesum)\s*[:\-]?\s*(?:kr|nok)?\s*([0-9][0-9\s.,]*)",
            r"(?:kr|nok)\s*([0-9][0-9\s.,]*)",
            r"([0-9][0-9\s.,]*)\s*(?:kr|nok)",
        )
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            start, end = match.span()
            context = _normalized_text(text[max(0, start - 80): min(len(text), end + 80)])
            if any(term in context for term in _CART_CONTEXT_TERMS):
                continue
            value = _parse_money(match.group(1))
            if value is not None:
                return value
    return None


def _extract_quantity(text: str) -> int | None:
    match = re.search(r"\b(\d{2,6})\s*(?:stk|plagg|varer|enheter|par)\b", text, re.I)
    return int(match.group(1)) if match else None


def _strip_html(fragment: str) -> str:
    fragment = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", fragment, flags=re.I | re.S)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def _extract_title(decoded: str) -> str | None:
    for pattern in (
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']',
        r'<meta[^>]+content=["\'](.*?)["\'][^>]+property=["\']og:title["\']',
        r"<title[^>]*>(.*?)</title>",
    ):
        match = re.search(pattern, decoded, re.I | re.S)
        if match:
            return html.unescape(re.sub(r"\s+", " ", match.group(1)).strip())
    return None


def _extract_meta_description(decoded: str) -> str | None:
    for pattern in (
        r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\'](.*?)["\']',
        r'<meta[^>]+content=["\'](.*?)["\'][^>]+(?:name|property)=["\'](?:description|og:description)["\']',
    ):
        match = re.search(pattern, decoded, re.I | re.S)
        if match:
            return html.unescape(re.sub(r"\s+", " ", match.group(1)).strip())
    return None


def _json_ld_objects(decoded: str) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for raw in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        decoded,
        flags=re.I | re.S,
    ):
        try:
            value = json.loads(html.unescape(raw).strip())
        except (json.JSONDecodeError, TypeError):
            continue
        queue = value if isinstance(value, list) else [value]
        for item in queue:
            if isinstance(item, dict) and isinstance(item.get("@graph"), list):
                queue.extend(node for node in item["@graph"] if isinstance(node, dict))
            if isinstance(item, dict):
                objects.append(item)
    return objects


def _structured_listing_context(decoded: str) -> tuple[str | None, dict[str, Any] | None, bool]:
    products: list[dict[str, Any]] = []
    for obj in _json_ld_objects(decoded):
        object_type = obj.get("@type")
        types = {str(value).lower() for value in object_type} if isinstance(object_type, list) else {str(object_type).lower()}
        if types & {"product", "offer", "auction", "event"}:
            products.append(obj)
    if len(products) != 1:
        return None, None, len(products) > 1
    obj = products[0]
    offer = obj.get("offers") if isinstance(obj.get("offers"), dict) else obj
    parts = [
        str(obj.get("name") or ""),
        str(obj.get("description") or ""),
        str(offer.get("name") or ""),
        str(offer.get("description") or ""),
    ]
    context = " ".join(part for part in parts if part).strip()
    return context or None, obj, False


def _single_container_context(decoded: str) -> tuple[str | None, bool]:
    containers: list[str] = []
    for tag in ("article", "main"):
        matches = re.findall(rf"<{tag}\b[^>]*>(.*?)</{tag}>", decoded, re.I | re.S)
        containers.extend(_strip_html(match) for match in matches if _strip_html(match))
    card_count = len(re.findall(
        r'class=["\'][^"\']*(?:product-card|listing-card|auction-card|search-result|lot-card)[^"\']*["\']',
        decoded,
        re.I,
    ))
    if card_count > 1:
        return None, True
    distinct = [item for item in containers if len(item) >= 40]
    if len(distinct) == 1:
        return distinct[0], False
    return None, len(distinct) > 1


def _page_role(
    canonical_url: str,
    title: str | None,
    visible: str,
    decoded: str,
    *,
    multiple_structured_items: bool,
    multiple_containers: bool,
) -> str:
    normalized = _normalized_text(title, visible)
    path = urlparse(canonical_url).path.lower()
    currency_count = len(re.findall(r"(?:kr|nok)\s*[0-9]|[0-9]\s*(?:kr|nok)", visible, re.I))
    quantity_count = len(re.findall(r"\b\d{2,6}\s*(?:stk|plagg|varer|enheter|par)\b", visible, re.I))
    category_hits = sum(term in normalized for term in _CATEGORY_TERMS)
    retail_checkout_hits = sum(term in normalized for term in _RETAIL_CHECKOUT_TERMS)
    if multiple_structured_items or multiple_containers or (
        category_hits >= 2 and (currency_count >= 2 or quantity_count >= 2)
    ) or (
        currency_count >= 2 and category_hits >= 1 and retail_checkout_hits >= 1
    ):
        return CATEGORY_INDEX
    event_scenario, event_hits = _scenario_from_text(normalized)
    has_event = bool(event_hits)
    has_inventory = any(term in normalized for term in _INVENTORY_TERMS)
    if any(term in normalized for term in _SOURCE_CHANNEL_TERMS):
        return SOURCE_CHANNEL
    if path in {"", "/"} and has_inventory and (
        "konkursbo" in normalized or "vareparti" in normalized
    ) and not _stable_identity(canonical_url, title or "", visible)[0]:
        return SOURCE_CHANNEL
    if any(term in normalized for term in _ORDINARY_SHOP_TERMS) and not has_event:
        return ORDINARY_STORE
    if any(term in normalized for term in _GENERIC_INFO_TERMS) and not has_event:
        return ARTICLE_OR_INFO
    visible_normalized = _normalized_text(visible)
    if len(visible) < 80 or (
        any(term in visible_normalized for term in _SHELL_TERMS)
        and (
            len(visible) < 300
            or not any(term in visible_normalized for term in (*_STRONG_SALE_TERMS, *_CLOTHING_TERMS))
        )
    ):
        return UNRESOLVED_SOURCE
    identity_stable, _ = _stable_identity(canonical_url, title or "", visible)
    if identity_stable:
        return ITEM_LISTING
    if path in {"", "/"} or _generic_title(title or ""):
        return SOURCE_CHANNEL
    return ARTICLE_OR_INFO


def verify_public_html(url: str, decoded: str) -> PageVerification:
    """Verify deterministic public HTML using bounded listing evidence."""
    canonical = normalize_public_url(url)
    if not canonical:
        return PageVerification(url=url, error="non-HTTPS or invalid URL")
    title = _extract_title(decoded)
    meta_description = _extract_meta_description(decoded)
    visible = _strip_html(decoded)[:20000]
    unavailable_text = _normalized_text(title, visible)
    listing_id = re.search(
        r"(?:^|[/_-])(\d{3,})(?:$|[/_-])",
        urlparse(canonical).path.lower(),
    )
    if listing_id and any(term in unavailable_text for term in _UNAVAILABLE_TERMS):
        return PageVerification(
            url=canonical,
            title=title,
            text=visible[:1000],
            listing_status=ENDED,
            page_role=ITEM_LISTING,
            opportunity_identity=f"url-id:{listing_id.group(1)}",
            identity_stable=True,
            verified=True,
            error="listing unavailable",
        )
    structured_context, structured_obj, multiple_structured = _structured_listing_context(decoded)
    container_context, multiple_containers = _single_container_context(decoded)
    role = _page_role(
        canonical,
        title,
        visible,
        decoded,
        multiple_structured_items=multiple_structured,
        multiple_containers=multiple_containers,
    )
    identity_stable, identity = _stable_identity(canonical, title or "", meta_description or visible)
    bounded_context = structured_context or container_context
    if role == ITEM_LISTING and bounded_context is None:
        bounded_context = " ".join(part for part in (title, meta_description) if part).strip() or visible[:4000]
    if role != ITEM_LISTING:
        bounded_context = None

    context_normalized = _normalized_text(bounded_context)
    scenario, event_hits = _scenario_from_text(context_normalized)
    clothing_evidence = bool(_term_hits(context_normalized, _CLOTHING_TERMS))
    inventory_evidence = bool(_term_hits(context_normalized, _INVENTORY_TERMS))
    sale_hits = _term_hits(context_normalized, (*_STRONG_SALE_TERMS, *_AUCTION_TERMS))
    sale_evidence = bool(sale_hits) and (inventory_evidence or clothing_evidence)
    listing_status = (
        ENDED if any(term in context_normalized for term in _ENDED_TERMS)
        else ACTIVE if any(term in context_normalized for term in _ACTIVE_TERMS)
        else UNKNOWN
    )

    offer: Mapping[str, Any] = {}
    if structured_obj:
        candidate_offer = structured_obj.get("offers")
        offer = candidate_offer if isinstance(candidate_offer, dict) else structured_obj
        availability = _normalized_text(str(offer.get("availability") or ""))
        if "outofstock" in availability or "discontinued" in availability:
            listing_status = ENDED
        elif "instock" in availability or "limitedavailability" in availability:
            listing_status = ACTIVE

    price_nok = None
    bid_price_nok = None
    quantity = None
    location = None
    inventory_type = None
    if bounded_context:
        price_value = offer.get("price") if offer else None
        if price_value is not None:
            price_nok = _parse_money(str(price_value))
        if price_nok is None:
            price_nok = _extract_price(bounded_context)
        bid_price_nok = _extract_price(bounded_context, bid=True)
        quantity = _extract_quantity(bounded_context)
        location = _extract_location(bounded_context)
        inventory_type = next((term for term in _CLOTHING_TERMS if term in context_normalized), None)

    if role in {CATEGORY_INDEX, SOURCE_CHANNEL, ORDINARY_STORE, ARTICLE_OR_INFO, UNRESOLVED_SOURCE}:
        price_nok = None
        bid_price_nok = None
        quantity = None
        location = None
        inventory_type = None
        sale_evidence = False
        clothing_evidence = False
        listing_status = UNKNOWN
        if role in {ORDINARY_STORE, SOURCE_CHANNEL, CATEGORY_INDEX, ARTICLE_OR_INFO}:
            scenario = UNVERIFIED_EVENT

    return PageVerification(
        url=canonical,
        title=title,
        text=bounded_context[:2000] if bounded_context else visible[:1000] or None,
        location=location,
        inventory_type=inventory_type,
        price_nok=price_nok,
        bid_price_nok=bid_price_nok,
        quantity=quantity,
        listing_status=listing_status,
        page_role=role,
        opportunity_identity=identity,
        identity_stable=identity_stable,
        clothing_inventory_evidence=clothing_evidence and inventory_evidence,
        sale_evidence=sale_evidence,
        event_scenario=scenario,
        bounded_context=bounded_context[:4000] if bounded_context else None,
        verified=role != UNRESOLVED_SOURCE,
        error=None if role != UNRESOLVED_SOURCE else "insufficient public listing content",
    )


def verify_public_page(url: str, *, timeout: float = 12.0) -> PageVerification:
    """Read one public HTTPS page without login or bypass behavior."""
    canonical = normalize_public_url(url)
    if not canonical:
        return PageVerification(url=url, error="non-HTTPS or invalid URL")
    request = Request(canonical, headers={"User-Agent": "OpportunityEngine-Discovery/2.1"})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - validated HTTPS public page
            final_url = normalize_public_url(response.geturl())
            if not final_url:
                return PageVerification(url=url, error="redirected outside HTTPS")
            raw = response.read(1_500_000)
    except Exception as exc:
        return PageVerification(
            url=canonical,
            page_role=UNRESOLVED_SOURCE,
            verified=False,
            error=str(exc),
        )
    return verify_public_html(final_url, raw.decode("utf-8", errors="replace"))


def _complete_verification_defaults(result: PageVerification) -> PageVerification:
    if not result.verified or result.page_role != UNRESOLVED_SOURCE:
        return result
    synthetic = " ".join(part for part in (result.title, result.text) if part)
    stable, identity = _stable_identity(result.url, result.title or "", result.text or "")
    normalized = _normalized_text(synthetic)
    scenario, _ = _scenario_from_text(normalized)
    role = ITEM_LISTING if stable else UNRESOLVED_SOURCE
    clothing = bool(_term_hits(normalized, _CLOTHING_TERMS)) and bool(_term_hits(normalized, _INVENTORY_TERMS))
    sale = bool(_term_hits(normalized, (*_STRONG_SALE_TERMS, *_AUCTION_TERMS))) and clothing
    return PageVerification(
        url=result.url,
        title=result.title,
        text=result.text,
        company_name=result.company_name,
        location=result.location if role == ITEM_LISTING else None,
        inventory_type=result.inventory_type if role == ITEM_LISTING else None,
        price_nok=result.price_nok if result.price_nok and result.price_nok > 0 and role == ITEM_LISTING else None,
        bid_price_nok=result.bid_price_nok if result.bid_price_nok and result.bid_price_nok > 0 and role == ITEM_LISTING else None,
        quantity=result.quantity if role == ITEM_LISTING else None,
        published_at=result.published_at,
        listing_status=result.listing_status,
        page_role=role,
        opportunity_identity=result.opportunity_identity or identity,
        identity_stable=result.identity_stable or stable,
        clothing_inventory_evidence=result.clothing_inventory_evidence or clothing,
        sale_evidence=result.sale_evidence or sale,
        event_scenario=result.event_scenario if result.event_scenario != UNVERIFIED_EVENT else scenario,
        bounded_context=result.bounded_context or result.text,
        verified=result.verified,
        error=result.error,
    )


def _apply_verification(candidate: MergedCandidate, raw_result: PageVerification) -> None:
    result = _complete_verification_defaults(raw_result)
    candidate.verification.append(result.to_dict())
    if not result.verified:
        if candidate.page_role != ITEM_LISTING or not candidate.identity_stable:
            candidate.state = REJECTED_NOISE
            candidate.reason = "unresolved source without independently proven item-listing identity"
            candidate.page_role = UNRESOLVED_SOURCE
            candidate.false_positive_guard_triggered = True
            candidate.scenario = UNVERIFIED_EVENT
        else:
            candidate.state = STRONG_LEAD_REQUIRES_VERIFICATION
            candidate.reason = "specific listing identity retained; public sale status remains unresolved"
        return

    candidate.verification_succeeded = True
    candidate.page_role = result.page_role
    candidate.identity_stable = result.identity_stable
    candidate.opportunity_identity = result.opportunity_identity
    if result.title and result.page_role == ITEM_LISTING and len(result.title) > len(candidate.title):
        candidate.title = result.title

    if result.page_role != ITEM_LISTING:
        candidate.state = REJECTED_NOISE
        candidate.reason = f"{result.page_role.lower()} is not one specific inventory opportunity"
        candidate.false_positive_guard_triggered = True
        candidate.scenario = UNVERIFIED_EVENT
        candidate.location = None
        candidate.inventory_type = None
        candidate.price_nok = None
        candidate.bid_price_nok = None
        candidate.quantity = None
        candidate.listing_status = ENDED if result.listing_status == ENDED else UNKNOWN
        return

    candidate.company_name = candidate.company_name or result.company_name
    candidate.location = result.location
    candidate.inventory_type = result.inventory_type
    candidate.price_nok = result.price_nok if result.price_nok and result.price_nok > 0 else None
    candidate.bid_price_nok = result.bid_price_nok if result.bid_price_nok and result.bid_price_nok > 0 else None
    candidate.quantity = result.quantity
    candidate.published_at = result.published_at
    candidate.listing_status = result.listing_status
    candidate.scenario = result.event_scenario if result.event_scenario != UNVERIFIED_EVENT else UNVERIFIED_EVENT

    if result.listing_status == ENDED:
        candidate.state = STRONG_LEAD_REQUIRES_VERIFICATION
        candidate.reason = "specific listing is ended and retained as historical evidence only"
    elif (
        result.identity_stable
        and result.clothing_inventory_evidence
        and result.sale_evidence
        and result.listing_status == ACTIVE
    ):
        candidate.state = CONFIRMED_SALE
        candidate.reason = "specific active sale confirmed by bounded public-page evidence"
    elif result.identity_stable and result.clothing_inventory_evidence:
        candidate.state = STRONG_LEAD_REQUIRES_VERIFICATION
        candidate.reason = "specific clothing-inventory listing retained; sale or active status requires verification"
    else:
        candidate.state = REJECTED_NOISE
        candidate.reason = "item page lacks bounded clothing-inventory evidence"
        candidate.false_positive_guard_triggered = True

    for signal in _term_hits(
        _normalized_text(result.title, result.bounded_context),
        (*_CLOTHING_TERMS, *_INVENTORY_TERMS, *_STRONG_SALE_TERMS, *_AUCTION_TERMS),
    ):
        _append_unique(candidate.evidence_signals, signal)


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
    inventory_clarity = (
        20 if candidate.page_role == ITEM_LISTING and candidate.inventory_type
        else 12 if candidate.identity_stable and any(term in text for term in _CLOTHING_TERMS)
        else 0
    )
    sale_signal = 20 if candidate.state == CONFIRMED_SALE else 8 if candidate.state == STRONG_LEAD_REQUIRES_VERIFICATION else 0
    traceability = 15 if candidate.source_urls and all(normalize_public_url(url) for url in candidate.source_urls) else 0
    freshness = _freshness_points(candidate.published_at, observed)
    logistics = 5 if candidate.location else 0
    price_or_quantity = 5 if candidate.price_nok is not None or candidate.bid_price_nok is not None or candidate.quantity is not None else 0
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
        candidate.why_opportunity.append("specific clothing-inventory evidence detected")
    if sale_signal == 20:
        candidate.why_opportunity.append("specific active sale confirmed")
    elif sale_signal:
        candidate.why_opportunity.append("specific listing retained pending further verification")
    candidate.confirmed_information = [
        f"traceable public sources: {len(candidate.source_urls)}",
        f"discovery state: {candidate.state}",
        f"page role: {candidate.page_role}",
    ]
    if candidate.location:
        candidate.confirmed_information.append(f"location: {candidate.location}")
    if candidate.price_nok is not None:
        candidate.confirmed_information.append(f"public price: {candidate.price_nok:g} NOK")
    if candidate.bid_price_nok is not None:
        candidate.confirmed_information.append(f"public bid: {candidate.bid_price_nok:g} NOK")
    if candidate.quantity is not None:
        candidate.confirmed_information.append(f"public quantity: {candidate.quantity}")
    candidate.missing_information = []
    if not candidate.location:
        candidate.missing_information.append("location")
    if candidate.price_nok is None and candidate.bid_price_nok is None:
        candidate.missing_information.append("price")
    if candidate.quantity is None:
        candidate.missing_information.append("quantity")
    if candidate.listing_status == UNKNOWN:
        candidate.missing_information.append("active/ended status")
    candidate.next_verification_step = (
        "Review the bounded listing evidence before dossier intake."
        if candidate.state == CONFIRMED_SALE
        else "Verify publicly that this specific listing remains active and offered for sale."
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
    successful_queries = 0
    for query in clean_queries:
        try:
            hits = provider.search(query.query, count=results_per_query)
            successful_queries += 1
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

    eligible_candidates = [
        candidate for candidate in merged
        if candidate.top5_eligible and candidate.listing_status != ENDED
    ]
    top5 = sorted(
        eligible_candidates,
        key=lambda item: (item.discovery_score, len(item.source_urls)),
        reverse=True,
    )[:5]
    all_payload = [candidate.to_dict() for candidate in sorted(merged, key=lambda item: item.discovery_score, reverse=True)]
    top5_payload = [candidate.to_dict() for candidate in top5]
    bands = {"HIGH": 0, "REVIEW": 0, "LOW": 0}
    for candidate in merged:
        bands[candidate.discovery_band] += 1

    execution_status = "FAIL" if clean_queries and successful_queries == 0 else "PARTIAL" if errors else "PASS"
    confirmed_top = sum(candidate.state == CONFIRMED_SALE for candidate in top5)
    opportunity_quality_status = (
        "NO_VALID_OPPORTUNITIES" if not top5
        else "PASS" if confirmed_top
        else "REVIEW_REQUIRED"
    )
    generic_roles = {CATEGORY_INDEX, SOURCE_CHANNEL, ORDINARY_STORE, ARTICLE_OR_INFO, UNRESOLVED_SOURCE}
    verification_failures = sum(
        1
        for candidate in merged
        for item in candidate.verification
        if not item.get("verified", False)
    )
    report = {
        "schema_version": "clothing-inventory-discovery-search-1.1",
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
        "top5_eligible_count": len(eligible_candidates),
        "generic_pages_excluded": sum(candidate.page_role in generic_roles for candidate in merged),
        "verification_failures": verification_failures,
        "false_positive_guard_triggered": sum(candidate.false_positive_guard_triggered for candidate in merged),
        "errors": errors,
        "execution_status": execution_status,
        "opportunity_quality_status": opportunity_quality_status,
        "status": execution_status,
        "no_opportunities_found": not top5_payload,
        "automatic_contact": False,
        "automatic_purchase_decision": False,
        "financial_ranking_used": False,
    }
    return {
        "search_run_report": report,
        "all_discovered_candidates": all_payload,
        "discovery_top5": top5_payload,
    }


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
        paths[key].write_text(
            json.dumps(result[key], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    report = result["search_run_report"]
    top5 = result["discovery_top5"]
    lines = [
        "Clothing Inventory Discovery Search",
        f"Execution status: {report['execution_status']}",
        f"Opportunity quality: {report['opportunity_quality_status']}",
        f"Queries: {report['queries_submitted']}",
        f"Hits: {report['hits_received']}",
        f"Merged candidates: {report['merged_candidates']}",
        f"Confirmed sales: {report['confirmed_sales']}",
        f"Strong leads requiring verification: {report['strong_leads_requiring_verification']}",
        f"Rejected noise: {report['rejected_results']}",
        f"Generic pages excluded: {report['generic_pages_excluded']}",
        f"Top opportunities: {len(top5)}",
    ]
    if not top5:
        lines.append("No valid specific Clothing Inventory opportunity was found in this run.")
    else:
        for index, candidate in enumerate(top5, 1):
            lines.append(
                f"{index}. [{candidate['opportunity_state']}] "
                f"{candidate['title']} — discovery score {candidate['discovery_score']}"
            )
    paths["operator_summary"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    return paths
