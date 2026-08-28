"""Fair bounded scheduling for proven-route recovery candidates.

This compatibility layer changes only which remembered route candidates receive the
existing recovery fetch slots when more candidates exist than the current cap.
It does not add search requests, page-fetch budget, providers, sources, markets,
runtimes, agents, qualification evidence, or automatic commercial actions.

The existing recovery loader remains the source of eligible remembered routes.
When that loader exposes more candidates than the requested recovery limit, this
layer groups them by market + host and selects them round-robin. Within each host,
a deterministic rotation keyed by the GitHub run number prevents the same tail
routes from being starved on every checkpoint.

Every selected route is still freshly fetched by the existing verifier and must
pass the unchanged Exact-Lot rules. Memory remains navigation evidence only.
"""
from __future__ import annotations

from collections import defaultdict
import os
from typing import Callable

from opportunity_engine.discovery import provider_unique_page_verification as verifier


VERSION = "FAIR_PROVEN_ROUTE_RECOVERY_V1"
CANDIDATE_POOL_MULTIPLIER = 10
ROTATION_SEED_ENV = "FAIR_PROVEN_ROUTE_RECOVERY_ROTATION_SEED"
SEARCH_REQUESTS_ADDED = 0
PAGE_FETCH_BUDGET_ADDED = 0
_INSTALLED = False
_UPSTREAM_ROUTE_LOADER: Callable[..., list[dict[str, str]]] | None = None


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _rotation_seed() -> int:
    raw = _compact(os.environ.get(ROTATION_SEED_ENV)) or _compact(
        os.environ.get("GITHUB_RUN_NUMBER")
    )
    if not raw:
        return 0
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


def _bucket_key(row: dict[str, str]) -> tuple[str, str]:
    market = _compact(row.get("market_code")).upper()
    host = verifier._normalized_host(row.get("url")) or _compact(row.get("domain")).casefold()
    return market, host or "unknown-host"


def _rotate(rows: list[dict[str, str]], *, seed: int) -> list[dict[str, str]]:
    if len(rows) <= 1:
        return list(rows)
    ordered = sorted(rows, key=lambda row: _compact(row.get("url")))
    offset = seed % len(ordered)
    return [*ordered[offset:], *ordered[:offset]]


def fair_select_recovery_candidates(
    rows: list[dict[str, str]],
    *,
    limit: int,
    seed: int | None = None,
) -> list[dict[str, str]]:
    """Select at most ``limit`` remembered routes without starving one host.

    If the candidate pool fits inside the existing limit, original ordering is
    preserved. Fair scheduling activates only under actual oversubscription.
    """
    if limit <= 0:
        return []

    unique: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for raw in rows:
        row = dict(raw)
        url = _compact(row.get("url"))
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        unique.append(row)

    rotation_seed = _rotation_seed() if seed is None else max(0, int(seed))
    if len(unique) <= limit:
        selected = unique
    else:
        buckets: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
        for row in unique:
            buckets[_bucket_key(row)].append(row)

        bucket_keys = sorted(buckets)
        if bucket_keys:
            bucket_offset = rotation_seed % len(bucket_keys)
            bucket_keys = [*bucket_keys[bucket_offset:], *bucket_keys[:bucket_offset]]

        queues = {
            key: _rotate(buckets[key], seed=rotation_seed)
            for key in bucket_keys
        }
        selected = []
        while len(selected) < limit:
            progressed = False
            for key in bucket_keys:
                queue = queues[key]
                if not queue:
                    continue
                selected.append(queue.pop(0))
                progressed = True
                if len(selected) >= limit:
                    break
            if not progressed:
                break

    pool_size = len(unique)
    bucket_count = len({_bucket_key(row) for row in unique})
    annotated: list[dict[str, str]] = []
    for row in selected:
        annotated.append(
            {
                **row,
                "fair_recovery_scheduler_version": VERSION,
                "fair_recovery_candidate_pool_size": str(pool_size),
                "fair_recovery_bucket_count": str(bucket_count),
                "fair_recovery_rotation_seed": str(rotation_seed),
                "fair_recovery_limit_unchanged": "true",
                "fair_recovery_global_page_fetch_cap_unchanged": "true",
            }
        )
    return annotated


def _fair_route_loader(
    *,
    market: str,
    current_hosts: set[str],
    current_urls: set[str],
    query: str,
    limit: int,
) -> list[dict[str, str]]:
    upstream = _UPSTREAM_ROUTE_LOADER
    if upstream is None or limit <= 0:
        return []

    pool_limit = max(
        limit,
        verifier.MAX_PROVEN_ROUTE_RECOVERY_FETCHES * CANDIDATE_POOL_MULTIPLIER,
    )
    pool = list(
        upstream(
            market=market,
            current_hosts=current_hosts,
            current_urls=current_urls,
            query=query,
            limit=pool_limit,
        )
    )
    return fair_select_recovery_candidates(pool, limit=limit)


def install_fair_proven_route_recovery_v1() -> bool:
    """Wrap the already-installed recovery loader without changing its eligibility rules."""
    global _INSTALLED, _UPSTREAM_ROUTE_LOADER
    if _INSTALLED:
        return False
    _UPSTREAM_ROUTE_LOADER = verifier._load_proven_route_recovery_candidates
    verifier._load_proven_route_recovery_candidates = _fair_route_loader

    # Install the provenance-only compatibility layer after the final recovery
    # loader is in place, so it observes the real provider/recovery truth without
    # changing any search request, page-fetch budget, or Exact-Lot gate.
    from opportunity_engine.discovery.search_provenance_integrity_v1 import (
        install_search_provenance_integrity_v1,
    )

    install_search_provenance_integrity_v1()
    _INSTALLED = True
    return True
