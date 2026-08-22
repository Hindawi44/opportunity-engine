"""Cost-aware sequential search waterfall for discovery.

The waterfall tries ordered providers one at a time and stops as soon as the
configured amount of accepted evidence has been collected. It is deliberately
provider-neutral so existing Brave and future authorized providers can reuse
it without changing their search contracts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Sequence
from urllib.parse import urlsplit, urlunsplit

from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider


AcceptHit = Callable[[SearchHit], bool]


@dataclass(frozen=True, slots=True)
class AdaptiveWaterfallStep:
    """One ordered provider in the discovery waterfall."""

    name: str
    provider: SearchProvider
    cost_units: int = 0
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("waterfall step name must be non-empty")
        if self.cost_units < 0:
            raise ValueError("cost_units must be >= 0")


@dataclass(frozen=True, slots=True)
class AdaptiveWaterfallPolicy:
    """Bounded execution policy for a single waterfall search."""

    min_accepted_hits: int = 1
    max_total_cost_units: int | None = None
    results_per_source: int = 10
    continue_on_error: bool = True

    def __post_init__(self) -> None:
        if self.min_accepted_hits < 1:
            raise ValueError("min_accepted_hits must be >= 1")
        if self.results_per_source < 1:
            raise ValueError("results_per_source must be >= 1")
        if self.max_total_cost_units is not None and self.max_total_cost_units < 0:
            raise ValueError("max_total_cost_units must be >= 0 or None")


@dataclass(frozen=True, slots=True)
class AdaptiveWaterfallAttempt:
    source: str
    status: str
    cost_units: int
    raw_count: int = 0
    accepted_count: int = 0
    new_unique_count: int = 0
    duplicate_count: int = 0
    rejected_count: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "status": self.status,
            "cost_units": self.cost_units,
            "raw_count": self.raw_count,
            "accepted_count": self.accepted_count,
            "new_unique_count": self.new_unique_count,
            "duplicate_count": self.duplicate_count,
            "rejected_count": self.rejected_count,
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class AdaptiveWaterfallResult:
    query: str
    status: str
    hits: tuple[SearchHit, ...]
    attempts: tuple[AdaptiveWaterfallAttempt, ...]
    total_cost_units: int
    stopped_after: str | None
    min_accepted_hits: int

    @property
    def accepted_hit_count(self) -> int:
        return len(self.hits)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "adaptive-search-waterfall-1.0",
            "query": self.query,
            "status": self.status,
            "accepted_hit_count": self.accepted_hit_count,
            "min_accepted_hits": self.min_accepted_hits,
            "total_cost_units": self.total_cost_units,
            "stopped_after": self.stopped_after,
            "attempts": [item.to_dict() for item in self.attempts],
            "hits": [
                {
                    "title": item.title,
                    "url": item.url,
                    "description": item.description,
                    "provider": item.provider,
                }
                for item in self.hits
            ],
        }


def _canonical_url(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
    except ValueError:
        return raw.casefold()
    scheme = parts.scheme.casefold()
    netloc = parts.netloc.casefold()
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def _default_accept(_: SearchHit) -> bool:
    return True


def _enabled_steps(steps: Iterable[AdaptiveWaterfallStep]) -> list[AdaptiveWaterfallStep]:
    return [step for step in steps if step.enabled]


def run_adaptive_search_waterfall(
    query: str,
    steps: Sequence[AdaptiveWaterfallStep],
    *,
    accept_hit: AcceptHit | None = None,
    policy: AdaptiveWaterfallPolicy | None = None,
) -> AdaptiveWaterfallResult:
    """Run ordered providers until enough unique accepted hits are found.

    The function never calls later providers after the success threshold has
    been met. Cost guards are checked before each provider call. Provider
    failures are recorded and, by default, do not block later fallback steps.
    """

    compact_query = " ".join(str(query or "").split()).strip()
    if not compact_query:
        raise ValueError("query must be non-empty")

    active_policy = policy or AdaptiveWaterfallPolicy()
    predicate = accept_hit or _default_accept
    attempts: list[AdaptiveWaterfallAttempt] = []
    accepted_hits: list[SearchHit] = []
    seen_urls: set[str] = set()
    total_cost = 0

    for step in _enabled_steps(steps):
        if len(accepted_hits) >= active_policy.min_accepted_hits:
            break

        max_cost = active_policy.max_total_cost_units
        if max_cost is not None and total_cost + step.cost_units > max_cost:
            attempts.append(
                AdaptiveWaterfallAttempt(
                    source=step.name,
                    status="SKIPPED_COST_GUARD",
                    cost_units=0,
                )
            )
            continue

        try:
            raw_hits = tuple(
                step.provider.search(
                    compact_query,
                    count=active_policy.results_per_source,
                )
            )
        except Exception as exc:  # provider boundary: record, then optionally continue
            attempts.append(
                AdaptiveWaterfallAttempt(
                    source=step.name,
                    status="ERROR",
                    cost_units=step.cost_units,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            total_cost += step.cost_units
            if active_policy.continue_on_error:
                continue
            return AdaptiveWaterfallResult(
                query=compact_query,
                status="ERROR",
                hits=tuple(accepted_hits),
                attempts=tuple(attempts),
                total_cost_units=total_cost,
                stopped_after=step.name,
                min_accepted_hits=active_policy.min_accepted_hits,
            )

        total_cost += step.cost_units
        accepted_count = 0
        new_unique_count = 0
        duplicate_count = 0
        rejected_count = 0

        for item in raw_hits:
            if not predicate(item):
                rejected_count += 1
                continue
            accepted_count += 1
            key = _canonical_url(item.url)
            if key and key in seen_urls:
                duplicate_count += 1
                continue
            if key:
                seen_urls.add(key)
            accepted_hits.append(item)
            new_unique_count += 1

        satisfied = len(accepted_hits) >= active_policy.min_accepted_hits
        attempts.append(
            AdaptiveWaterfallAttempt(
                source=step.name,
                status="SATISFIED" if satisfied else "INSUFFICIENT",
                cost_units=step.cost_units,
                raw_count=len(raw_hits),
                accepted_count=accepted_count,
                new_unique_count=new_unique_count,
                duplicate_count=duplicate_count,
                rejected_count=rejected_count,
            )
        )

        if satisfied:
            return AdaptiveWaterfallResult(
                query=compact_query,
                status="SATISFIED",
                hits=tuple(accepted_hits),
                attempts=tuple(attempts),
                total_cost_units=total_cost,
                stopped_after=step.name,
                min_accepted_hits=active_policy.min_accepted_hits,
            )

    return AdaptiveWaterfallResult(
        query=compact_query,
        status="EXHAUSTED",
        hits=tuple(accepted_hits),
        attempts=tuple(attempts),
        total_cost_units=total_cost,
        stopped_after=None,
        min_accepted_hits=active_policy.min_accepted_hits,
    )
