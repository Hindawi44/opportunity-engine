"""Bounded PS Auction source targeting for Swedish Clothing Inventory discovery.

The adapter uses only public Brave-indexed pages and accepts one exact PS Auction
item URL shape. It does not log in, bid, purchase, infer hidden inventory, or
assume an auction is active before the public page verifier confirms it.
"""
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

PSAUCTION_HOST = "psauction.se"
PSAUCTION_ITEM_PATH = re.compile(r"^/item/view/(?P<item_id>\d+)/[^/?#]+/?$", re.I)

# Keep the default eight-query daily budget inventory-first. Exact status-marker
# queries remain in the full matrix for deeper/manual runs, but they must not
# consume half of the normal discovery budget before inventory terms are tried.
PSAUCTION_CLOTHING_QUERY_MATRIX: tuple[DiscoveryQuery, ...] = (
    DiscoveryQuery(
        "se-ps-05",
        "COMPANY_BANKRUPTCY",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        'site:psauction.se/item/view konkursbo kläder parti -fordon -maskin',
    ),
    DiscoveryQuery(
        "se-ps-08",
        "WAREHOUSE_SURPLUS",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        'site:psauction.se/item/view restlager kläder',
    ),
    DiscoveryQuery(
        "se-ps-09",
        "LARGE_LOT_SALE",
        "SPECIALIZED",
        "CLOTHING_INVENTORY",
        'site:psauction.se/item/view lagerparti kläder accessoarer',
        "SECONDARY",
    ),
    DiscoveryQuery(
        "se-ps-14",
        "INVENTORY_LIQUIDATION",
        "SPECIALIZED",
        "CLOTHING_INVENTORY",
        'site:psauction.se/item/view butikslager kläder accessoarer',
        "SECONDARY",
    ),
    DiscoveryQuery(
        "se-ps-11",
        "WAREHOUSE_SURPLUS",
        "SPECIALIZED",
        "CLOTHING_INVENTORY",
        'site:psauction.se/item/view arbetskläder arbetsskor parti',
        "SECONDARY",
    ),
    DiscoveryQuery(
        "se-ps-12",
        "LARGE_LOT_SALE",
        "SPECIALIZED",
        "CLOTHING_INVENTORY",
        'site:psauction.se/item/view skor lager parti konkurs',
        "SECONDARY",
    ),
    DiscoveryQuery(
        "se-ps-15",
        "LARGE_LOT_SALE",
        "SPECIALIZED",
        "CLOTHING_INVENTORY",
        'site:psauction.se/item/view textil kläder parti',
        "SECONDARY",
    ),
    DiscoveryQuery(
        "se-ps-06",
        "LARGE_LOT_SALE",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        'site:psauction.se/item/view "parti med kläder" -fordon',
    ),
    DiscoveryQuery(
        "se-ps-07",
        "INVENTORY_LIQUIDATION",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        'site:psauction.se/item/view "samtliga kläder" butik',
    ),
    DiscoveryQuery(
        "se-ps-10",
        "COMPANY_BANKRUPTCY",
        "SPECIALIZED",
        "CLOTHING_INVENTORY",
        'site:psauction.se/item/view jeans kläder konkursbo',
        "SECONDARY",
    ),
    DiscoveryQuery(
        "se-ps-13",
        "LARGE_LOT_SALE",
        "SPECIALIZED",
        "CLOTHING_INVENTORY",
        'site:psauction.se/item/view modekläder varulager',
        "SECONDARY",
    ),
    DiscoveryQuery(
        "se-ps-01",
        "AUCTION",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        'site:psauction.se/item/view "Auktionen avslutas" kläder parti',
    ),
    DiscoveryQuery(
        "se-ps-02",
        "AUCTION",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        'site:psauction.se/item/view "Auktionen avslutas" arbetskläder sortiment',
    ),
    DiscoveryQuery(
        "se-ps-03",
        "AUCTION",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        'site:psauction.se/item/view "Auktionen avslutas" skor parti',
    ),
    DiscoveryQuery(
        "se-ps-04",
        "AUCTION",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        'site:psauction.se/item/view "Auktionen avslutas" bälten',
    ),
)

_CLOTHING_TITLE_TERMS = (
    "kläder",
    "klädbutik",
    "klädparti",
    "klädesplagg",
    "jeans",
    "byxor",
    "kjolar",
    "klänningar",
    "blusar",
    "skjortor",
    "toppar",
    "arbetskläder",
    "arbetsskor",
    "skor",
    "tofflor",
    "bälten",
    "accessoarer",
    "textil",
    "plagg",
)
_BULK_TERMS = (
    "parti",
    "lager",
    "varulager",
    "restlager",
    "restparti",
    "lagerparti",
    "sortiment",
    "alla kläder",
    "samtliga kläder",
    "hela lagret",
    "hela varulagret",
    "pall",
    "kartong",
    "kartonger",
    " krt ",
)
_BULK_QUANTITY_PATTERN = re.compile(
    r"\b(?:ca\s*)?(\d{2,7})(?:\+)?\s*"
    r"(?:st|par|plagg|artiklar|pall|kartonger?|krt)\b",
    re.I,
)
_ENDED_OR_SOLD_TERMS = (
    "auktionen är avslutad",
    "auktionen avslutad",
    "avslutad",
    "såld",
    "utgången",
    "avbruten",
)
_ENDED_REASON = "specific PS Auction item is ended or sold"


@dataclass(frozen=True, slots=True)
class PSAuctionGateDecision:
    accepted: bool
    canonical_url: str
    item_id: str | None
    reason: str


def build_psauction_clothing_queries(
    query_budget: int = 8,
) -> tuple[DiscoveryQuery, ...]:
    """Return a bounded prefix of the PS Auction query matrix."""
    if not 1 <= query_budget <= len(PSAUCTION_CLOTHING_QUERY_MATRIX):
        raise ValueError(
            "query_budget must be between 1 and "
            f"{len(PSAUCTION_CLOTHING_QUERY_MATRIX)}"
        )
    return PSAUCTION_CLOTHING_QUERY_MATRIX[:query_budget]


def _normalized_host(host: str | None) -> str:
    value = (host or "").casefold()
    return value[4:] if value.startswith("www.") else value


def canonicalize_psauction_item_url(url: str) -> tuple[str, str] | None:
    """Return canonical URL and item ID only for one specific PS Auction item."""
    canonical = normalize_public_url(url)
    if not canonical:
        return None
    parsed = urlparse(canonical)
    if _normalized_host(parsed.hostname) != PSAUCTION_HOST:
        return None
    match = PSAUCTION_ITEM_PATH.fullmatch(parsed.path or "/")
    if match is None:
        return None
    return canonical, match.group("item_id")


def _compact(value: str) -> str:
    return " ".join(value.casefold().split())


def _has_bulk_scope(text: str) -> bool:
    padded = f" {text} "
    if any(term in padded for term in _BULK_TERMS):
        return True
    return any(int(match.group(1)) >= 10 for match in _BULK_QUANTITY_PATTERN.finditer(text))


def psauction_gate_decision(hit: SearchHit) -> PSAuctionGateDecision:
    """Accept only a specific, not-known-ended PS Auction bulk clothing page."""
    canonical = normalize_public_url(hit.url)
    if not canonical:
        return PSAuctionGateDecision(False, "", None, "invalid public HTTPS URL")

    parsed = urlparse(canonical)
    if _normalized_host(parsed.hostname) != PSAUCTION_HOST:
        return PSAuctionGateDecision(False, canonical, None, "not a PS Auction host")

    path_match = PSAUCTION_ITEM_PATH.fullmatch(parsed.path or "/")
    if not path_match:
        return PSAuctionGateDecision(
            False,
            canonical,
            None,
            "PS Auction URL is not one specific item page",
        )

    title = _compact(hit.title)
    combined = _compact(f"{hit.title} {hit.description}")
    if not any(term in title for term in _CLOTHING_TITLE_TERMS):
        return PSAuctionGateDecision(
            False,
            canonical,
            path_match.group("item_id"),
            "specific PS Auction title lacks clothing evidence",
        )
    if not _has_bulk_scope(combined):
        return PSAuctionGateDecision(
            False,
            canonical,
            path_match.group("item_id"),
            "specific clothing item lacks bulk inventory evidence",
        )
    if any(term in combined for term in _ENDED_OR_SOLD_TERMS):
        return PSAuctionGateDecision(
            False,
            canonical,
            path_match.group("item_id"),
            _ENDED_REASON,
        )

    return PSAuctionGateDecision(
        True,
        canonical,
        path_match.group("item_id"),
        "specific PS Auction bulk clothing-inventory item page",
    )


class PSAuctionTargetedSearchProvider:
    """Wrap a provider with registered PS Auction queries and a strict URL gate."""

    name = "PS Auction Sweden source targeting"

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
        if request_budget < 1:
            raise ValueError("request_budget must be positive")
        if request_budget < len(query_list):
            raise ValueError("request_budget must cover every registered query")
        self._provider = provider
        self._queries = {query.query: query for query in query_list}
        if len(self._queries) != len(query_list):
            raise ValueError("query text must be unique")
        self._request_budget = request_budget
        self._requests_made = 0
        self._raw_hits = 0
        self._accepted_hits = 0
        self._rejected_hits = 0
        self._rejection_reasons: Counter[str] = Counter()
        self._accepted_item_ids: list[str] = []
        self._accepted_urls: list[str] = []
        self._historical_item_ids: list[str] = []
        self._accepted_samples: list[dict[str, Any]] = []
        self._rejected_samples: list[dict[str, Any]] = []
        self._query_diagnostics: list[dict[str, Any]] = []

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        discovery_query = self._queries.get(query)
        if discovery_query is None:
            raise ValueError("query is not registered in the PS Auction source policy")
        if self._requests_made >= self._request_budget:
            raise RuntimeError("PS Auction source request budget exhausted")

        self._requests_made += 1
        raw_hits = tuple(self._provider.search(query, count=count))
        self._raw_hits += len(raw_hits)
        accepted: list[SearchHit] = []
        rejected = 0
        for hit in raw_hits:
            decision = psauction_gate_decision(hit)
            sample = {
                "query_id": discovery_query.query_id,
                "title": hit.title,
                "url": hit.url,
                "canonical_url": decision.canonical_url,
                "item_id": decision.item_id,
                "reason": decision.reason,
                "description": hit.description[:500],
            }
            if not decision.accepted:
                rejected += 1
                self._rejected_hits += 1
                self._rejection_reasons[decision.reason] += 1
                if (
                    decision.reason == _ENDED_REASON
                    and decision.item_id
                    and decision.item_id not in self._historical_item_ids
                ):
                    self._historical_item_ids.append(decision.item_id)
                if len(self._rejected_samples) < 20:
                    self._rejected_samples.append(sample)
                continue
            accepted.append(
                SearchHit(
                    title=hit.title,
                    url=decision.canonical_url,
                    description=hit.description,
                    provider=hit.provider or self.name,
                )
            )
            self._accepted_hits += 1
            if len(self._accepted_samples) < 20:
                self._accepted_samples.append(sample)
            if decision.item_id and decision.item_id not in self._accepted_item_ids:
                self._accepted_item_ids.append(decision.item_id)
            if decision.canonical_url not in self._accepted_urls:
                self._accepted_urls.append(decision.canonical_url)

        self._query_diagnostics.append(
            {
                "query_id": discovery_query.query_id,
                "query": discovery_query.query,
                "raw_hits": len(raw_hits),
                "accepted_hits": len(accepted),
                "rejected_hits": rejected,
            }
        )
        return tuple(accepted)

    def diagnostics(self) -> dict[str, Any]:
        return {
            "source": "PS_AUCTION",
            "host": PSAUCTION_HOST,
            "request_budget": self._request_budget,
            "requests_made": self._requests_made,
            "raw_hits": self._raw_hits,
            "accepted_hits": self._accepted_hits,
            "rejected_hits": self._rejected_hits,
            "accepted_item_ids": list(self._accepted_item_ids),
            "accepted_urls": list(self._accepted_urls),
            "historical_item_count": len(self._historical_item_ids),
            "historical_item_ids": list(self._historical_item_ids),
            "accepted_samples": list(self._accepted_samples),
            "rejection_reasons": dict(sorted(self._rejection_reasons.items())),
            "rejected_samples": list(self._rejected_samples),
            "query_diagnostics": list(self._query_diagnostics),
        }
