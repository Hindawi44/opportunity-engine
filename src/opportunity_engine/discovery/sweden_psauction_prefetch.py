"""Cross-query PS Auction prefetch and global historical filtering.

Brave can return the same PS Auction item with different snippets for different
queries. One snippet may omit its ended status while another clearly says
``Såld`` or ``Avslutad``. This provider executes the bounded query pack once,
collects all item IDs known to be historical, and only then exposes hits to the
discovery engine. Therefore an ended item cannot enter verification through an
earlier, incomplete snippet.

The daily PS Auction query pack may also contain bounded current-window hints.
When at least one non-historical current-window candidate survives the global
filter, unrelated generic indexed candidates are deferred for that run so the
fixed verification budget is spent on the freshest evidence first. This is only
retrieval priority: exact-page verification remains authoritative for ACTIVE.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Sequence

from opportunity_engine.discovery.clothing_inventory_search import DiscoveryQuery
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider
from opportunity_engine.discovery.sweden_psauction import (
    PSAUCTION_CURRENT_QUERY_IDS,
    PSAUCTION_HOST,
    PSAuctionGateDecision,
    psauction_gate_decision,
)

_ENDED_REASON = "specific PS Auction item is ended or sold"
_CURRENT_WINDOW_DEFER_REASON = (
    "generic indexed fallback deferred because current-window candidates exist"
)


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
        self._current_window_item_ids: list[str] = []
        self._current_window_priority_applied = False
        self._generic_fallback_deferred_count = 0

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
        decisions_by_query: dict[
            str,
            tuple[tuple[SearchHit, PSAuctionGateDecision], ...],
        ] = {}
        historical_ids: list[str] = []
        current_window_ids: list[str] = []

        # Pass 1 fetches the complete bounded pack before releasing a result.
        # This preserves the existing global historical veto and also tells us
        # whether the current-window lane has a candidate worth prioritizing.
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
                if (
                    query.query_id in PSAUCTION_CURRENT_QUERY_IDS
                    and decision.accepted
                    and decision.item_id
                    and decision.item_id not in current_window_ids
                ):
                    current_window_ids.append(decision.item_id)

        self._prefetch_count = count
        self._historical_item_ids = historical_ids
        historical_set = set(historical_ids)
        surviving_current_ids = [
            item_id for item_id in current_window_ids if item_id not in historical_set
        ]
        current_window_set = set(surviving_current_ids)
        self._current_window_item_ids = surviving_current_ids
        self._current_window_priority_applied = bool(current_window_set)

        globally_accepted_urls: set[str] = set()
        for query in self._query_list:
            accepted: list[SearchHit] = []
            rejected_count = 0
            deferred_count = 0
            for hit, decision in decisions_by_query[query.query]:
                reason = decision.reason
                accepted_decision = decision.accepted

                # Any explicit ended/sold evidence anywhere in the bounded pack
                # wins over an incomplete snippet everywhere else.
                if decision.item_id in historical_set:
                    accepted_decision = False
                    reason = _ENDED_REASON

                # If a current-window candidate survives that veto, reserve the
                # fixed downstream verification capacity for current-window
                # identities. Generic search remains available as fallback only
                # when the current-window lane yields nothing.
                if (
                    accepted_decision
                    and current_window_set
                    and query.query_id not in PSAUCTION_CURRENT_QUERY_IDS
                    and decision.item_id not in current_window_set
                ):
                    accepted_decision = False
                    reason = _CURRENT_WINDOW_DEFER_REASON
                    deferred_count += 1
                    self._generic_fallback_deferred_count += 1

                # A current-window identity repeated by a generic query is not a
                # second candidate. Keep the first exact URL only.
                if (
                    accepted_decision
                    and decision.canonical_url
                    and decision.canonical_url in globally_accepted_urls
                ):
                    accepted_decision = False
                    reason = "duplicate exact PS Auction item within bounded query pack"

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
                globally_accepted_urls.add(decision.canonical_url)
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
                    "deferred_generic_hits": deferred_count,
                    "current_window_query": query.query_id in PSAUCTION_CURRENT_QUERY_IDS,
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
            "current_window_item_ids": list(self._current_window_item_ids),
            "current_window_candidate_count": len(self._current_window_item_ids),
            "current_window_priority_applied": self._current_window_priority_applied,
            "generic_fallback_deferred_count": self._generic_fallback_deferred_count,
            "current_window_is_active_proof": False,
        }
