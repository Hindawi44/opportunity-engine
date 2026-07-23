"""Guarded activation of external research from the daily pipeline.

The activator selects only a bounded set of priority opportunities, skips execution
when external search is not configured, and isolates per-opportunity failures.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable


@dataclass(frozen=True, slots=True)
class DailyExternalResearchResult:
    enabled: bool
    reason: str
    considered: int
    selected: int
    completed: int
    failed: int
    searches_executed: int
    searches_skipped: int
    cache_hits: int
    errors: tuple[str, ...] = ()


class DailyExternalResearchActivator:
    def __init__(
        self,
        *,
        investment_repository: Any,
        loop_factory: Callable[[], Any],
        max_opportunities: int = 3,
        enabled: bool = True,
        disabled_reason: str = "disabled",
    ) -> None:
        if max_opportunities <= 0:
            raise ValueError("max_opportunities must be positive")
        self.investment_repository = investment_repository
        self.loop_factory = loop_factory
        self.max_opportunities = max_opportunities
        self.enabled = enabled
        self.disabled_reason = disabled_reason

    def run(self, rows: Iterable[dict[str, Any]]) -> DailyExternalResearchResult:
        ranked = self._rank_rows(rows)
        if not self.enabled:
            return DailyExternalResearchResult(False, self.disabled_reason, len(ranked), 0, 0, 0, 0, 0, 0)

        selected = ranked[: self.max_opportunities]
        completed = failed = searches = skipped = 0
        errors: list[str] = []
        loop = self.loop_factory()

        for row in selected:
            opportunity_id = str(row.get("opportunity_id") or "").strip()
            if not opportunity_id:
                continue
            try:
                investment_file = self.investment_repository.load(opportunity_id)
                result = loop.run(investment_file)
                self.investment_repository.save(investment_file)
                completed += 1
                searches += int(getattr(result, "searches_executed", 0))
                skipped += int(getattr(result, "searches_skipped", 0))
                errors.extend(str(item) for item in getattr(result, "errors", ()))
            except Exception as exc:
                failed += 1
                errors.append(f"{opportunity_id}:{exc}")

        usage = getattr(getattr(loop, "search_provider", None), "usage", None)
        cache_hits = int(getattr(usage, "cache_hits", 0)) if usage is not None else 0
        return DailyExternalResearchResult(
            True,
            "enabled",
            len(ranked),
            len(selected),
            completed,
            failed,
            searches,
            skipped,
            cache_hits,
            tuple(errors),
        )

    @staticmethod
    def _rank_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        valid = [row for row in rows if str(row.get("opportunity_id") or "").strip()]
        return sorted(
            valid,
            key=lambda row: (
                -float(row.get("score") or 0),
                str(row.get("opportunity_id") or ""),
            ),
        )
