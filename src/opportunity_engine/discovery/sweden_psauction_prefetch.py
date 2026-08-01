"""Cross-query PS Auction prefetch and global historical filtering.

Brave can return the same PS Auction item with different snippets for different
queries. One snippet may omit its ended status while another clearly says
``Såld`` or ``Avslutad``. This provider executes the bounded query pack once,
collects all item IDs known to be historical, and only then exposes hits to the
discovery engine. Therefore an ended item cannot enter verification through an
earlier, incomplete snippet.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Sequence

from opportunity_engine.discovery.clothing_inventory_search import DiscoveryQuery
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider
from opportunity_engine.discovery.sweden_psauction import (
    PSAUCTION_HOST,
    PSAuctionGateDecision,
    psauction_gate_decision,
)

_ENDED_REASON = "specific PS Auction item is ended or sold"


class PSAuctionPrefetchedSearchProvider:
    """Serve globally filtered PS Auction hits from one bounded prefetch cycle."""

    name = "PS Auction Sweden globally filtered source targeting"

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
        self._historical_item_ids: list[str] = []
        self._accepted_item_ids: list[str] = []
        self._accepted_urls: list[str] = []
        self._accepted_samples: list[dict[str, Any]] = []
        self._rejected_samples: list[dict[str, Any]] = []
        self._rejection_reasons: Counter[str] = Counter()
        self._query_diagnostics: list[dict[str, Any]] = []

    @staticmethod
    def _sample(
        query: DiscoveryQuery,
        hit: SearchHit,
        decision: PSAuctionGateDecision,
        reason: str,
    ) -> dict[str, Any]:
        return {
            "query_id": query.query_id,
            "title": hit.title,
            "url": hit.url,
            "canonical_url": decision.canonical_url,
            "item_id": decision.item_id,
            "reason": reason,
            "description": hit.description[:500],
        }

    def _prefetch(self, count: int) -> None:
        if self._hits_by_query:
            if count != self._prefetch_count:
                raise ValueError("count must remain stable during one prefetched run")
            return
        if self._requests_made + len(self._query_list) > self._request_budget:
            raise RuntimeError("PS Auction source request budget exhausted")

        raw_by_query: dict[str, tuple[SearchHit, ...]] = {}
        decisions_by_query: dict[str, tuple[tuple[SearchHit, PSAuctionGateDecision], ...]] = {}
        historical_ids: list[str] = []
        for query in self._query_list:
            raw_hits = tuple(self._provider.search(query.query, count=count))
            self._requests_made += 1
            self._raw_hits += len(raw_hits)
            raw_by_query[query.query] = raw_hits
            pairs = tuple((hit, psauction_gate_decision(hit)) for hit in raw_hits)
            decisions_by_query[query.query] = pairs
            for _, decision in pairs:
                if (
                    decision.reason == _ENDED_REASON
                    and decision.item_id
                    and decision.item_id not in historical_ids
                ):
                    historical_ids.append(decision.item_id)

        self._prefetch_count = count
        self._historical_item_ids = historical_ids
        historical_set = set(historical_ids)

        for query in self._query_list:
            accepted: list[SearchHit] = []
            rejected_count = 0
            for hit, decision in decisions_by_query[query.query]:
                reason = decision.reason
                accepted_decision = decision.accepted
                if decision.item_id in historical_set:
                    accepted_decision = False
                    reason = _ENDED_REASON

                sample = self._sample(query, hit, decision, reason)
                if not accepted_decision:
                    rejected_count += 1
                    self._rejected_hits += 1
                    self._rejection_reasons[reason] += 1
                    if len(self._rejected_samples) < 20:
                        self._rejected_samples.append(sample)
                    continue

                accepted_hit = SearchHit(
                    title=hit.title,
                    url=decision.canonical_url,
                    description=hit.description,
                    provider=hit.provider or self.name,
                )
                accepted.append(accepted_hit)
                self._accepted_hits += 1
                if len(self._accepted_samples) < 20:
                    self._accepted_samples.append(sample)
                if (
                    decision.item_id
                    and decision.item_id not in self._accepted_item_ids
                ):
                    self._accepted_item_ids.append(decision.item_id)
                if decision.canonical_url not in self._accepted_urls:
                    self._accepted_urls.append(decision.canonical_url)

            self._hits_by_query[query.query] = tuple(accepted)
            self._query_diagnostics.append(
                {
                    "query_id": query.query_id,
                    "query": query.query,
                    "raw_hits": len(raw_by_query[query.query]),
                    "accepted_hits": len(accepted),
                    "rejected_hits": rejected_count,
                }
            )

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        if query not in self._queries:
            raise ValueError("query is not registered in the PS Auction source policy")
        self._prefetch(count)
        return self._hits_by_query[query]

    def diagnostics(self) -> dict[str, Any]:
        return {
            "source": "PS_AUCTION",
            "host": PSAUCTION_HOST,
            "prefetched": True,
            "request_budget": self._request_budget,
            "requests_made": self._requests_made,
            "raw_hits": self._raw_hits,
            "accepted_hits": self._accepted_hits,
            "rejected_hits": self._rejected_hits,
            "historical_item_count": len(self._historical_item_ids),
            "historical_item_ids": list(self._historical_item_ids),
            "accepted_item_ids": list(self._accepted_item_ids),
            "accepted_urls": list(self._accepted_urls),
            "accepted_samples": list(self._accepted_samples),
            "rejection_reasons": dict(sorted(self._rejection_reasons.items())),
            "rejected_samples": list(self._rejected_samples),
            "query_diagnostics": list(self._query_diagnostics),
        }
