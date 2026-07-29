"""Bounded source and URL gate for Brave Clothing Inventory retrieval."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Sequence
from urllib.parse import urlparse

from opportunity_engine.discovery.clothing_inventory_search import (
    DiscoveryQuery,
    normalize_public_url,
)
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider

SALE_SOURCE_HOSTS = frozenset({
    "auksjonen.no",
    "finn.no",
    "norskavvikling.no",
    "stadssalg.no",
})
EVENT_SOURCE_HOSTS = frozenset({
    "forvalt.no",
    "konkurs.app",
    "virksomhet.brreg.no",
})
ALLOWED_SOURCE_HOSTS = SALE_SOURCE_HOSTS | EVENT_SOURCE_HOSTS

_BAD_PATH_TERMS = (
    "/nyheter",
    "/news",
    "/blogg",
    "/blog/",
    "/artikkel",
    "/magasin",
    "/om-oss",
    "/kontakt",
    "/faq",
    "/personvern",
    "/vilkar",
)
_FINN_ITEM_PATH = re.compile(r"^/recommerce/forsale/item/\d+/?$", re.I)
_BRREG_ENTITY_PATH = re.compile(
    r"^/(?:nb|nn|en)?/?oppslag/(?:enheter|underenheter)/\d+/?$",
    re.I,
)
_COMMERCIAL_TERMS = (
    "konkurssalg",
    "konkursbo",
    "varelager",
    "hele lageret",
    "restlager",
    "vareparti",
    "til salgs",
    "selges",
    "auksjon",
)
_CLOTHING_TERMS = (
    "klær",
    "klesbutikk",
    "bekledning",
    "sport og fritid",
    "sportsklær",
    "arbeidstøy",
    "sko",
    "barneklær",
)

_REFERENCE_MARKERS: dict[str, tuple[tuple[str, ...], ...]] = {
    "axl-sport-og-fritid": (
        ("axl sport og fritid", "kolvereid"),
        ("axl", "konkurssalg", "kolvereid"),
    ),
    "by-fiona": (
        ("anna j as", "namsos"),
        ("by fiona", "namsos"),
        ("989324217",),
    ),
    "tommeliten-barneklaer": (
        ("tommeliten barneklær",),
        ("tommeliten barneklaer",),
        ("932113309",),
    ),
}


@dataclass(frozen=True, slots=True)
class SourceGateDecision:
    accepted: bool
    canonical_url: str
    host: str
    source_class: str
    reason: str


def _normalized_host(host: str | None) -> str:
    value = (host or "").casefold()
    return value[4:] if value.startswith("www.") else value


def _compact_text(*values: str) -> str:
    text = " ".join(" ".join(value.casefold().split()) for value in values if value)
    digits = re.sub(r"\D", "", text)
    return f"{text} {digits}".strip()


def _declared_site(query_text: str) -> str:
    match = re.search(r"(?<!\S)site:([^\s]+)", query_text, flags=re.I)
    return match.group(1).casefold().rstrip("/") if match else ""


def _host_matches_site(host: str, path: str, declared_site: str) -> bool:
    if not declared_site:
        return False
    site_host, _, site_path = declared_site.partition("/")
    site_host = _normalized_host(site_host)
    if host != site_host:
        return False
    return not site_path or path.casefold().startswith(f"/{site_path}")


def _looks_commercial_and_clothing(hit: SearchHit) -> bool:
    text = _compact_text(hit.title, hit.description)
    return (
        any(term in text for term in _COMMERCIAL_TERMS)
        and any(term in text for term in _CLOTHING_TERMS)
    )


def source_gate_decision(hit: SearchHit, query: DiscoveryQuery) -> SourceGateDecision:
    """Fail closed before classification when a hit is outside approved sources."""
    canonical = normalize_public_url(hit.url)
    if not canonical:
        return SourceGateDecision(False, "", "", "REJECTED", "invalid public HTTPS URL")

    parsed = urlparse(canonical)
    host = _normalized_host(parsed.hostname)
    path = parsed.path or "/"
    declared_site = _declared_site(query.query)
    if not _host_matches_site(host, path, declared_site):
        return SourceGateDecision(
            False,
            canonical,
            host,
            "REJECTED",
            "result does not match the query site restriction",
        )
    if host not in ALLOWED_SOURCE_HOSTS:
        return SourceGateDecision(False, canonical, host, "REJECTED", "unapproved source host")
    if any(term in path.casefold() for term in _BAD_PATH_TERMS):
        return SourceGateDecision(False, canonical, host, "REJECTED", "editorial or generic path")

    if host == "finn.no":
        if not _FINN_ITEM_PATH.fullmatch(path):
            return SourceGateDecision(
                False,
                canonical,
                host,
                "REJECTED",
                "FINN URL is not one specific public item page",
            )
        return SourceGateDecision(True, canonical, host, "SALE_LISTING_SOURCE", "specific FINN item URL")

    if host == "virksomhet.brreg.no":
        if not _BRREG_ENTITY_PATH.fullmatch(path):
            return SourceGateDecision(
                False,
                canonical,
                host,
                "REJECTED",
                "Brønnøysund URL is not one specific organisation page",
            )
        return SourceGateDecision(True, canonical, host, "EVENT_REGISTRY_SOURCE", "specific organisation page")

    if host == "forvalt.no":
        if "/konkurs" not in path.casefold():
            return SourceGateDecision(
                False,
                canonical,
                host,
                "REJECTED",
                "Forvalt URL is outside the bankruptcy register",
            )
        return SourceGateDecision(True, canonical, host, "EVENT_REGISTRY_SOURCE", "bankruptcy register page")

    if host == "konkurs.app":
        if path == "/" and not _looks_commercial_and_clothing(hit):
            return SourceGateDecision(
                False,
                canonical,
                host,
                "REJECTED",
                "generic bankruptcy portal page",
            )
        return SourceGateDecision(True, canonical, host, "EVENT_REGISTRY_SOURCE", "bankruptcy event source")

    if host == "norskavvikling.no":
        if path == "/" or path.casefold().startswith("/aktive-salg"):
            if not _looks_commercial_and_clothing(hit):
                return SourceGateDecision(
                    False,
                    canonical,
                    host,
                    "REJECTED",
                    "generic liquidation source page without clothing event evidence",
                )
            return SourceGateDecision(
                True,
                canonical,
                host,
                "SALE_CHANNEL_SOURCE",
                "bounded active-sale channel evidence",
            )
        return SourceGateDecision(True, canonical, host, "SALE_LISTING_SOURCE", "liquidation sale page")

    if host in {"auksjonen.no", "stadssalg.no"}:
        if path == "/":
            return SourceGateDecision(False, canonical, host, "REJECTED", "generic auction homepage")
        return SourceGateDecision(True, canonical, host, "SALE_LISTING_SOURCE", "auction or clearance page")

    return SourceGateDecision(False, canonical, host, "REJECTED", "source policy fallthrough")


def _matching_references(hit: SearchHit) -> set[str]:
    text = _compact_text(hit.title, hit.description, hit.url)
    matched: set[str] = set()
    for reference_id, alternatives in _REFERENCE_MARKERS.items():
        if any(all(marker in text for marker in marker_set) for marker_set in alternatives):
            matched.add(reference_id)
    return matched


class SourceTargetedSearchProvider:
    """Wrap a search provider with a strict request budget and URL gate."""

    def __init__(
        self,
        provider: SearchProvider,
        *,
        queries: Iterable[DiscoveryQuery],
        request_budget: int,
    ) -> None:
        if request_budget < 1:
            raise ValueError("request_budget must be positive")
        query_list = tuple(queries)
        if not query_list:
            raise ValueError("queries must not be empty")
        self._provider = provider
        self._query_by_text = {query.query: query for query in query_list}
        if len(self._query_by_text) != len(query_list):
            raise ValueError("query text must be unique")
        self._request_budget = request_budget
        self._requests_made = 0
        self._raw_hits = 0
        self._accepted_hits = 0
        self._rejected_hits = 0
        self._rejection_reasons: Counter[str] = Counter()
        self._accepted_hosts: Counter[str] = Counter()
        self._recovered_references: set[str] = set()
        self._accepted_urls: list[str] = []
        self._query_diagnostics: dict[str, dict[str, Any]] = {}
        self.name = f"{getattr(provider, 'name', provider.__class__.__name__)} + Source Targeting"

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        discovery_query = self._query_by_text.get(query)
        if discovery_query is None:
            raise ValueError("query is not registered in the source-targeted policy")
        if self._requests_made >= self._request_budget:
            raise RuntimeError("source-targeted Brave request budget exhausted")

        self._requests_made += 1
        stats = {
            "query_id": discovery_query.query_id,
            "query": query,
            "raw_hits": 0,
            "accepted_hits": 0,
            "rejected_hits": 0,
            "error": None,
        }
        self._query_diagnostics[discovery_query.query_id] = stats
        try:
            hits = self._provider.search(query, count=count)
        except Exception as exc:
            stats["error"] = str(exc)
            raise

        stats["raw_hits"] = len(hits)
        self._raw_hits += len(hits)
        accepted: list[SearchHit] = []
        for hit in hits:
            decision = source_gate_decision(hit, discovery_query)
            if not decision.accepted:
                stats["rejected_hits"] += 1
                self._rejected_hits += 1
                self._rejection_reasons[decision.reason] += 1
                continue
            accepted_hit = SearchHit(
                title=hit.title,
                url=decision.canonical_url,
                description=hit.description,
                provider=hit.provider or getattr(self._provider, "name", ""),
            )
            accepted.append(accepted_hit)
            stats["accepted_hits"] += 1
            self._accepted_hits += 1
            self._accepted_hosts[decision.host] += 1
            if decision.canonical_url not in self._accepted_urls:
                self._accepted_urls.append(decision.canonical_url)
            self._recovered_references.update(_matching_references(accepted_hit))
        return accepted

    def diagnostics(self) -> dict[str, Any]:
        return {
            "request_budget": self._request_budget,
            "requests_made": self._requests_made,
            "raw_hits": self._raw_hits,
            "accepted_hits": self._accepted_hits,
            "rejected_hits": self._rejected_hits,
            "zero_raw_hits": self._raw_hits == 0,
            "rejection_reasons": dict(sorted(self._rejection_reasons.items())),
            "accepted_hosts": dict(sorted(self._accepted_hosts.items())),
            "accepted_urls": list(self._accepted_urls),
            "query_diagnostics": [
                dict(self._query_diagnostics[query_id])
                for query_id in self._query_diagnostics
            ],
            "reference_cases": sorted(_REFERENCE_MARKERS),
            "reference_cases_recovered": sorted(self._recovered_references),
            "reference_recall": (
                len(self._recovered_references) / len(_REFERENCE_MARKERS)
            ),
            "playwright_used": False,
            "page_verification_performed_by_gate": False,
        }
