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

PSAUCTION_CLOTHING_QUERY_MATRIX: tuple[DiscoveryQuery, ...] = (
    DiscoveryQuery(
        "se-ps-01",
        "COMPANY_BANKRUPTCY",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        'site:psauction.se/item/view konkursbo kläder parti -fordon -maskin',
    ),
    DiscoveryQuery(
        "se-ps-02",
        "LARGE_LOT_SALE",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        'site:psauction.se/item/view "parti med kläder" -fordon',
    ),
    DiscoveryQuery(
        "se-ps-03",
        "INVENTORY_LIQUIDATION",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        'site:psauction.se/item/view "samtliga kläder" butik',
    ),
    DiscoveryQuery(
        "se-ps-04",
        "STORE_CLOSING",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        'site:psauction.se/item/view klädbutik konkurs lager',
    ),
    DiscoveryQuery(
        "se-ps-05",
        "WAREHOUSE_SURPLUS",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        'site:psauction.se/item/view restlager kläder',
    ),
    DiscoveryQuery(
        "se-ps-06",
        "LARGE_LOT_SALE",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        'site:psauction.se/item/view lagerparti kläder accessoarer',
    ),
    DiscoveryQuery(
        "se-ps-07",
        "COMPANY_BANKRUPTCY",
        "SPECIALIZED",
        "CLOTHING_INVENTORY",
        'site:psauction.se/item/view jeans kläder konkursbo',
        "SECONDARY",
    ),
    DiscoveryQuery(
        "se-ps-08",
        "WAREHOUSE_SURPLUS",
        "SPECIALIZED",
        "CLOTHING_INVENTORY",
        'site:psauction.se/item/view arbetskläder arbetsskor parti',
        "SECONDARY",
    ),
    DiscoveryQuery(
        "se-ps-09",
        "LARGE_LOT_SALE",
        "SPECIALIZED",
        "CLOTHING_INVENTORY",
        'site:psauction.se/item/view skor lager parti konkurs',
        "SECONDARY",
    ),
    DiscoveryQuery(
        "se-ps-10",
        "LARGE_LOT_SALE",
        "SPECIALIZED",
        "CLOTHING_INVENTORY",
        'site:psauction.se/item/view modekläder varulager',
        "SECONDARY",
    ),
    DiscoveryQuery(
        "se-ps-11",
        "INVENTORY_LIQUIDATION",
        "SPECIALIZED",
        "CLOTHING_INVENTORY",
        'site:psauction.se/item/view butikslager kläder accessoarer',
        "SECONDARY",
    ),
    DiscoveryQuery(
        "se-ps-12",
        "LARGE_LOT_SALE",
        "SPECIALIZED",
        "CLOTHING_INVENTORY",
        'site:psauction.se/item/view textil kläder parti',
        "SECONDARY",
    ),
)

_CLOTHING_TERMS = (
    "kläder",
    "kläd",
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
    "accessoarer",
    "textil",
    "plagg",
)
_INVENTORY_OR_SALE_TERMS = (
    "parti",
    "lager",
    "varulager",
    "butik",
    "konkurs",
    "konkursbo",
    "auktion",
    "bud",
    "försäljning",
    "samtliga",
    "restlager",
    "utförsäljning",
)


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


def _compact_text(hit: SearchHit) -> str:
    return " ".join(f"{hit.title} {hit.description}".casefold().split())


def psauction_gate_decision(hit: SearchHit) -> PSAuctionGateDecision:
    """Accept only a specific public PS Auction item page with clothing evidence."""
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

    text = _compact_text(hit)
    if not any(term in text for term in _CLOTHING_TERMS):
        return PSAuctionGateDecision(
            False,
            canonical,
            path_match.group("item_id"),
            "specific PS Auction item lacks clothing evidence",
        )
    if not any(term in text for term in _INVENTORY_OR_SALE_TERMS):
        return PSAuctionGateDecision(
            False,
            canonical,
            path_match.group("item_id"),
            "specific clothing item lacks lot, inventory, sale, or bankruptcy evidence",
        )

    return PSAuctionGateDecision(
        True,
        canonical,
        path_match.group("item_id"),
        "specific PS Auction clothing-inventory item page",
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
            if not decision.accepted:
                rejected += 1
                self._rejected_hits += 1
                self._rejection_reasons[decision.reason] += 1
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
            "rejection_reasons": dict(sorted(self._rejection_reasons.items())),
            "query_diagnostics": list(self._query_diagnostics),
        }
