"""Shared current-first retrieval for Sweden's indexed auction sources.

The policy changes retrieval priority only. It does not increase Brave requests,
weaken exact-page ACTIVE/ENDED verification, or change commercial eligibility.
Current-window search hits are hints, never ACTIVE proof, so unrelated fallback
identities must remain available until exact source-page verification decides
lifecycle state. Blinto keeps auction-occurrence identity and Klaravik keeps
exact product-slug identity.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable, Iterable, Sequence
from zoneinfo import ZoneInfo

from opportunity_engine.discovery.clothing_inventory_search import DiscoveryQuery
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider
from opportunity_engine.discovery.sweden_blinto import (
    BLINTO_CLOTHING_QUERY_MATRIX,
    BlintoPrefetchedSearchProvider,
    canonicalize_blinto_auction_url,
)
from opportunity_engine.discovery.sweden_klaravik import (
    KLARAVIK_CLOTHING_QUERY_MATRIX,
    KlaravikPrefetchedSearchProvider,
    canonicalize_klaravik_product_url,
)

_STOCKHOLM_TZ = ZoneInfo("Europe/Stockholm")
_SWEDISH_MONTHS = (
    "januari",
    "februari",
    "mars",
    "april",
    "maj",
    "juni",
    "juli",
    "augusti",
    "september",
    "oktober",
    "november",
    "december",
)
BLINTO_CURRENT_QUERY_IDS = frozenset({"se-bl-current-01", "se-bl-current-02"})
KLARAVIK_CURRENT_QUERY_IDS = frozenset({"se-kl-current-01", "se-kl-current-02"})


def _stockholm_now(now: datetime | None = None) -> datetime:
    local_now = now or datetime.now(_STOCKHOLM_TZ)
    if local_now.tzinfo is None:
        return local_now.replace(tzinfo=_STOCKHOLM_TZ)
    return local_now.astimezone(_STOCKHOLM_TZ)


def _swedish_current_window(now: datetime | None = None) -> str:
    local_now = _stockholm_now(now)
    return f"{_SWEDISH_MONTHS[local_now.month - 1]} {local_now.year}"


def _compose_current_first(
    current: Sequence[DiscoveryQuery],
    fallback: Sequence[DiscoveryQuery],
    query_budget: int,
) -> tuple[DiscoveryQuery, ...]:
    max_budget = len(fallback)
    if not 1 <= query_budget <= max_budget:
        raise ValueError(f"query_budget must be between 1 and {max_budget}")
    return tuple((*current, *fallback)[:query_budget])


def build_blinto_current_first_queries(
    query_budget: int = 8,
    *,
    now: datetime | None = None,
) -> tuple[DiscoveryQuery, ...]:
    """Lead with Swedish retail-liquidation language inside the same budget."""
    window = _swedish_current_window(now)
    current = (
        DiscoveryQuery(
            "se-bl-current-01",
            "INVENTORY_LIQUIDATION",
            "SALE_INTENT",
            "CLOTHING_INVENTORY",
            (
                "site:blinto.se/auction "
                "(klädbutik OR modebutik OR butikslager) "
                f"(kläder OR skor OR accessoarer) \"{window}\""
            ),
        ),
        DiscoveryQuery(
            "se-bl-current-02",
            "INVENTORY_LIQUIDATION",
            "SALE_INTENT",
            "CLOTHING_INVENTORY",
            (
                "site:blinto.se/auction "
                "(utförsäljning OR avveckling OR konkurs OR restlager) "
                f"(kläder OR mode OR skor) \"{window}\""
            ),
        ),
    )
    return _compose_current_first(current, BLINTO_CLOTHING_QUERY_MATRIX, query_budget)


def build_klaravik_current_first_queries(
    query_budget: int = 8,
    *,
    now: datetime | None = None,
) -> tuple[DiscoveryQuery, ...]:
    """Lead with Swedish retail-liquidation language inside the same budget."""
    window = _swedish_current_window(now)
    current = (
        DiscoveryQuery(
            "se-kl-current-01",
            "INVENTORY_LIQUIDATION",
            "SALE_INTENT",
            "CLOTHING_INVENTORY",
            (
                "site:klaravik.se/auktion/produkt "
                "(klädbutik OR modebutik OR butikslager) "
                f"(kläder OR skor OR accessoarer) \"{window}\""
            ),
        ),
        DiscoveryQuery(
            "se-kl-current-02",
            "INVENTORY_LIQUIDATION",
            "SALE_INTENT",
            "CLOTHING_INVENTORY",
            (
                "site:klaravik.se/auktion/produkt "
                "(utförsäljning OR avveckling OR konkurs OR restlager) "
                f"(kläder OR mode OR skor) \"{window}\""
            ),
        ),
    )
    return _compose_current_first(current, KLARAVIK_CLOTHING_QUERY_MATRIX, query_budget)


def _blinto_identity(hit: SearchHit) -> str:
    parsed = canonicalize_blinto_auction_url(hit.url)
    if parsed is None:
        return hit.url
    # occurrence_id is intentionally preferred: the same object may be relisted
    # in a later auction occurrence and must not be collapsed into old history.
    return parsed.listing_key


def _klaravik_identity(hit: SearchHit) -> str:
    parsed = canonicalize_klaravik_product_url(hit.url)
    return parsed[1] if parsed is not None else hit.url


class _CurrentFirstWrapper:
    """Expose current-window identities first without hiding unverified fallback."""

    def __init__(
        self,
        delegate: SearchProvider,
        *,
        queries: Iterable[DiscoveryQuery],
        current_query_ids: frozenset[str],
        identity: Callable[[SearchHit], str],
        source: str,
    ) -> None:
        self._delegate = delegate
        self._query_list = tuple(queries)
        if not self._query_list:
            raise ValueError("queries must not be empty")
        self._queries = {query.query: query for query in self._query_list}
        if len(self._queries) != len(self._query_list):
            raise ValueError("query text must be unique")
        self._current_query_ids = current_query_ids
        self._identity = identity
        self._source = source
        self._prefetch_count: int | None = None
        self._hits_by_query: dict[str, tuple[SearchHit, ...]] = {}
        self._current_identities: list[str] = []
        self._current_priority_applied = False
        self._generic_preserved_count = 0
        self._duplicate_count = 0
        self._query_diagnostics: list[dict[str, object]] = []

    def _prefetch(self, count: int) -> None:
        if self._hits_by_query:
            if count != self._prefetch_count:
                raise ValueError("count must remain stable during one current-first run")
            return

        # The source delegate prefetches its complete bounded query pack on the
        # first call. Reading every registered query here therefore consumes no
        # requests beyond the delegate's existing fixed budget.
        raw_by_query = {
            query.query: tuple(self._delegate.search(query.query, count=count))
            for query in self._query_list
        }
        self._prefetch_count = count

        current: list[str] = []
        for query in self._query_list:
            if query.query_id not in self._current_query_ids:
                continue
            for hit in raw_by_query[query.query]:
                key = self._identity(hit)
                if key not in current:
                    current.append(key)
        self._current_identities = current
        self._current_priority_applied = bool(current)

        # Current queries are already first in the query pack, so their unique
        # identities are exposed first. Generic identities stay available: an
        # indexed "current" hit is not allowed to suppress them before exact-page
        # ACTIVE/ENDED verification. Cross-query duplicates are still collapsed.
        seen: set[str] = set()
        for query in self._query_list:
            exposed: list[SearchHit] = []
            duplicates = 0
            is_current_query = query.query_id in self._current_query_ids
            preserved_generic = 0
            for hit in raw_by_query[query.query]:
                key = self._identity(hit)
                if key in seen:
                    duplicates += 1
                    self._duplicate_count += 1
                    continue
                seen.add(key)
                exposed.append(hit)
                if not is_current_query:
                    preserved_generic += 1
                    self._generic_preserved_count += 1
            self._hits_by_query[query.query] = tuple(exposed)
            self._query_diagnostics.append(
                {
                    "query_id": query.query_id,
                    "query": query.query,
                    "current_window_query": is_current_query,
                    "delegate_hits": len(raw_by_query[query.query]),
                    "exposed_hits": len(exposed),
                    "deferred_generic_hits": 0,
                    "preserved_generic_hits": preserved_generic,
                    "duplicate_hits": duplicates,
                }
            )

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        if query not in self._queries:
            raise ValueError("query is not registered in the current-first source policy")
        self._prefetch(count)
        return self._hits_by_query[query]

    def diagnostics(self) -> dict[str, object]:
        diagnostics_method = getattr(self._delegate, "diagnostics", None)
        base = dict(diagnostics_method() if callable(diagnostics_method) else {})
        base.update(
            {
                "current_first_policy": "SWEDEN_CURRENT_FIRST_V2_VERIFY_BEFORE_SUPPRESS",
                "current_first_source": self._source,
                "current_window_identity_count": len(self._current_identities),
                "current_window_identities": list(self._current_identities),
                "current_window_priority_applied": self._current_priority_applied,
                # Kept for report compatibility. V2 never defers unrelated fallback
                # on search-snippet evidence alone.
                "generic_fallback_deferred_count": 0,
                "generic_fallback_preserved_count": self._generic_preserved_count,
                "current_first_duplicate_count": self._duplicate_count,
                "current_first_query_diagnostics": list(self._query_diagnostics),
                "current_window_is_active_proof": False,
                "active_state_still_requires_exact_page_verification": True,
                "fallback_suppression_requires_verified_active": True,
            }
        )
        return base


class BlintoCurrentFirstPrefetchedSearchProvider(_CurrentFirstWrapper):
    name = "Blinto Sweden current-first globally filtered source targeting"

    def __init__(
        self,
        provider: SearchProvider,
        *,
        queries: Iterable[DiscoveryQuery],
        request_budget: int,
    ) -> None:
        query_list = tuple(queries)
        super().__init__(
            BlintoPrefetchedSearchProvider(
                provider,
                queries=query_list,
                request_budget=request_budget,
            ),
            queries=query_list,
            current_query_ids=BLINTO_CURRENT_QUERY_IDS,
            identity=_blinto_identity,
            source="BLINTO",
        )


class KlaravikCurrentFirstPrefetchedSearchProvider(_CurrentFirstWrapper):
    name = "Klaravik Sweden current-first globally filtered source targeting"

    def __init__(
        self,
        provider: SearchProvider,
        *,
        queries: Iterable[DiscoveryQuery],
        request_budget: int,
    ) -> None:
        query_list = tuple(queries)
        super().__init__(
            KlaravikPrefetchedSearchProvider(
                provider,
                queries=query_list,
                request_budget=request_budget,
            ),
            queries=query_list,
            current_query_ids=KLARAVIK_CURRENT_QUERY_IDS,
            identity=_klaravik_identity,
            source="KLARAVIK",
        )
