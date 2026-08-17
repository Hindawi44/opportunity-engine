"""Bounded Sen & Sen targeting for German clothing-inventory liquidation leads.

This adapter uses public search-index results only to locate exact Sen & Sen sale
pages. It does not infer that a sale is active: exact-page verification remains
responsible for lifecycle status. The adapter never logs in, contacts a seller,
submits an offer, buys, or pays.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
from typing import Any, Iterable, Sequence
from urllib.parse import urlparse

from opportunity_engine.discovery.clothing_inventory_search import (
    DiscoveryQuery,
    normalize_public_url,
)
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider


SEN_SEN_HOST = "sen-sen.de"
# Sen & Sen exposes both event pages (/php/t<ID>-...) and specific object/lot
# pages (/php/o<ID>-...). Both are exact public sale-detail surfaces; generic
# dilib.php, PDFs, indexes and other paths remain rejected.
SEN_SEN_DETAIL_PATH = re.compile(
    r"^/php/(?P<detail_kind>[to])(?P<detail_id>\d+)-[^/]+/?$", re.I
)

SEN_SEN_CLOTHING_QUERY_MATRIX: tuple[DiscoveryQuery, ...] = (
    DiscoveryQuery(
        "de-ss-01",
        "INVENTORY_LIQUIDATION",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        'site:sen-sen.de/php "Textil-Warenbestand"',
    ),
    DiscoveryQuery(
        "de-ss-02",
        "COMPANY_BANKRUPTCY",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        'site:sen-sen.de/php Arbeitskleidung Warenbestand Insolvenz',
    ),
    DiscoveryQuery(
        "de-ss-03",
        "INVENTORY_LIQUIDATION",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        'site:sen-sen.de/php Freizeitkleidung Warenbestand Liquidationsverkauf',
    ),
    DiscoveryQuery(
        "de-ss-04",
        "COMPANY_BANKRUPTCY",
        "EVENT_LEAD",
        "CLOTHING_INVENTORY",
        'site:sen-sen.de/php "Liquidationsverkauf aus Insolvenz" Kleidung',
    ),
    DiscoveryQuery(
        "de-ss-05",
        "LARGE_LOT_SALE",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        'site:sen-sen.de/php "Verkauf gegen Gebot" Kleidung Warenbestand',
        "SECONDARY",
    ),
    DiscoveryQuery(
        "de-ss-06",
        "WAREHOUSE_SURPLUS",
        "SPECIALIZED",
        "CLOTHING_INVENTORY",
        'site:sen-sen.de/php Textilien Lagerbestand Restposten Insolvenz',
        "SECONDARY",
    ),
)

_CLOTHING_TERMS = (
    "bekleidung",
    "kleidung",
    "arbeitskleidung",
    "freizeitkleidung",
    "textil-warenbestand",
    "textil warenbestand",
    "textilien",
    "modewaren",
    "jacken",
    "hosen",
    "shirts",
)
_BULK_TERMS = (
    "warenbestand",
    "lagerbestand",
    "warenlager",
    "restposten",
    "sonderposten",
    "posten",
    "gesamtlager",
    "kompletter bestand",
    "teile",
)
_SALE_OR_EVENT_TERMS = (
    "liquidationsverkauf",
    "insolvenzverkauf",
    "aus insolvenz",
    "verkauf gegen gebot",
    "verkauf",
    "auktion",
    "versteigerung",
)
_ENDED_TERMS = (
    "verkauft",
    "beendet",
    "abgeschlossen",
    "zuschlag erteilt",
    "verkauf abgeschlossen",
)
_NOISE_TERMS = (
    "immobilie",
    "grundstück",
    "bungalow",
    "fahrzeug",
    "pkw",
    "e-bike",
    "maschine",
    "werkbank",
    "büromöbel",
    "haushaltsgeräte",
    "videokonferenz",
)
_SOURCE_POLICY_ALIASES = (
    "klær varelager likvidasjon konkurs til salgs budrunde vareparti"
)
_ENDED_REASON = "specific Sen & Sen sale page is explicitly ended or sold"


@dataclass(frozen=True, slots=True)
class SenSenGateDecision:
    accepted: bool
    canonical_url: str
    event_id: str | None
    reason: str


def build_sen_sen_clothing_queries(query_budget: int = 6) -> tuple[DiscoveryQuery, ...]:
    if not 1 <= query_budget <= len(SEN_SEN_CLOTHING_QUERY_MATRIX):
        raise ValueError(
            "query_budget must be between 1 and "
            f"{len(SEN_SEN_CLOTHING_QUERY_MATRIX)}"
        )
    return SEN_SEN_CLOTHING_QUERY_MATRIX[:query_budget]


def _compact(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _host(value: str | None) -> str:
    host = (value or "").casefold()
    return host[4:] if host.startswith("www.") else host


def canonicalize_sen_sen_detail_url(url: str) -> tuple[str, str] | None:
    canonical = normalize_public_url(url)
    if not canonical:
        return None
    parsed = urlparse(canonical)
    if _host(parsed.hostname) != SEN_SEN_HOST:
        return None
    match = SEN_SEN_DETAIL_PATH.fullmatch(parsed.path or "/")
    if match is None:
        return None
    detail_kind = match.group("detail_kind").casefold()
    detail_id = match.group("detail_id")
    # Preserve the legacy numeric identity for t/event pages. Prefix object IDs
    # so an o7580 object can never collide with a hypothetical t7580 event.
    stable_id = detail_id if detail_kind == "t" else f"o{detail_id}"
    return canonical, stable_id


def sen_sen_gate_decision(hit: SearchHit) -> SenSenGateDecision:
    canonical = normalize_public_url(hit.url)
    if not canonical:
        return SenSenGateDecision(False, "", None, "invalid public HTTPS URL")
    parsed = urlparse(canonical)
    if _host(parsed.hostname) != SEN_SEN_HOST:
        return SenSenGateDecision(False, canonical, None, "not a Sen & Sen host")

    identity = canonicalize_sen_sen_detail_url(hit.url)
    if identity is None:
        return SenSenGateDecision(
            False,
            canonical,
            None,
            "Sen & Sen URL is not one specific public sale page",
        )
    exact_url, event_id = identity
    title = _compact(hit.title)
    combined = _compact(f"{hit.title} {hit.description}")

    if any(term in combined for term in _NOISE_TERMS):
        return SenSenGateDecision(
            False, exact_url, event_id, "non-clothing liquidation result"
        )
    if not any(term in title for term in _CLOTHING_TERMS):
        return SenSenGateDecision(
            False, exact_url, event_id, "specific title lacks clothing evidence"
        )
    if not any(term in combined for term in _BULK_TERMS):
        return SenSenGateDecision(
            False, exact_url, event_id, "specific result lacks bulk inventory evidence"
        )
    if not any(term in combined for term in _SALE_OR_EVENT_TERMS):
        return SenSenGateDecision(
            False, exact_url, event_id, "specific result lacks sale or insolvency evidence"
        )
    if any(term in combined for term in _ENDED_TERMS):
        return SenSenGateDecision(False, exact_url, event_id, _ENDED_REASON)
    return SenSenGateDecision(
        True,
        exact_url,
        event_id,
        "specific Sen & Sen clothing-inventory liquidation lead",
    )


class SenSenPrefetchedSearchProvider:
    """Prefetch a bounded source pack and return only strict exact-sale hits."""

    name = "Sen & Sen Germany globally filtered source targeting"

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
        self._accepted_event_ids: list[str] = []
        self._accepted_urls: list[str] = []
        self._historical_event_ids: list[str] = []
        self._accepted_samples: list[dict[str, Any]] = []
        self._rejected_samples: list[dict[str, Any]] = []
        self._rejection_reasons: Counter[str] = Counter()
        self._query_diagnostics: list[dict[str, Any]] = []

    @staticmethod
    def _sample(
        query: DiscoveryQuery,
        hit: SearchHit,
        decision: SenSenGateDecision,
        reason: str,
    ) -> dict[str, Any]:
        return {
            "query_id": query.query_id,
            "title": hit.title,
            "url": hit.url,
            "canonical_url": decision.canonical_url,
            "event_id": decision.event_id,
            "reason": reason,
            "description": hit.description[:500],
        }

    def _prefetch(self, count: int) -> None:
        if self._hits_by_query:
            if count != self._prefetch_count:
                raise ValueError("count must remain stable during one prefetched run")
            return
        if self._requests_made + len(self._query_list) > self._request_budget:
            raise RuntimeError("Sen & Sen source request budget exhausted")

        decisions: dict[str, tuple[tuple[SearchHit, SenSenGateDecision], ...]] = {}
        raw_counts: dict[str, int] = {}
        historical: list[str] = []
        for query in self._query_list:
            raw_hits = tuple(self._provider.search(query.query, count=count))
            self._requests_made += 1
            self._raw_hits += len(raw_hits)
            raw_counts[query.query] = len(raw_hits)
            pairs = tuple((hit, sen_sen_gate_decision(hit)) for hit in raw_hits)
            decisions[query.query] = pairs
            for _, decision in pairs:
                if (
                    decision.reason == _ENDED_REASON
                    and decision.event_id
                    and decision.event_id not in historical
                ):
                    historical.append(decision.event_id)

        self._prefetch_count = count
        self._historical_event_ids = historical
        historical_set = set(historical)
        globally_accepted: set[str] = set()

        for query in self._query_list:
            accepted: list[SearchHit] = []
            rejected_count = 0
            for hit, decision in decisions[query.query]:
                reason = decision.reason
                is_accepted = decision.accepted
                if decision.event_id in historical_set:
                    is_accepted = False
                    reason = _ENDED_REASON
                if decision.canonical_url and decision.canonical_url in globally_accepted:
                    is_accepted = False
                    reason = "duplicate exact Sen & Sen sale page within bounded query pack"
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
                        description=description[:6000],
                        provider=hit.provider or self.name,
                    )
                )
                globally_accepted.add(decision.canonical_url)
                self._accepted_hits += 1
                if decision.event_id and decision.event_id not in self._accepted_event_ids:
                    self._accepted_event_ids.append(decision.event_id)
                if decision.canonical_url not in self._accepted_urls:
                    self._accepted_urls.append(decision.canonical_url)
                if len(self._accepted_samples) < 30:
                    self._accepted_samples.append(sample)

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
            raise ValueError("query is not registered in the Sen & Sen source policy")
        self._prefetch(count)
        return self._hits_by_query[query]

    def diagnostics(self) -> dict[str, Any]:
        return {
            "source": "SEN_SEN",
            "host": SEN_SEN_HOST,
            "prefetched": True,
            "request_budget": self._request_budget,
            "requests_made": self._requests_made,
            "raw_hits": self._raw_hits,
            "accepted_hits": self._accepted_hits,
            "rejected_hits": self._rejected_hits,
            "historical_event_count": len(self._historical_event_ids),
            "historical_event_ids": list(self._historical_event_ids),
            "accepted_event_ids": list(self._accepted_event_ids),
            "accepted_urls": list(self._accepted_urls),
            "accepted_samples": list(self._accepted_samples),
            "rejection_reasons": dict(sorted(self._rejection_reasons.items())),
            "rejected_samples": list(self._rejected_samples),
            "query_diagnostics": list(self._query_diagnostics),
            "automatic_contact": False,
            "automatic_offer": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }
