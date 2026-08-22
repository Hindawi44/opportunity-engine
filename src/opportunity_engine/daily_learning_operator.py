"""Daily bounded operator for missed-opportunity learning.

The operator joins durable missed-opportunity memory with a curated inbox,
proposes search terms only for diagnosed QUERY_GAP cases, shadow-evaluates a
small bounded number of candidates, retains previously proven skills, and marks
cases recovered when hidden-ground-truth replay succeeds.

Network access is injected through a callback. This keeps the learning policy
fully testable and lets the CLI enforce paid-search guards independently.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping, Sequence

from opportunity_engine.adaptive_keyword_learning import (
    KeywordEvaluationResult,
    KeywordLearningCandidate,
    build_keyword_learning_report,
    evaluate_keyword_candidate,
    propose_query_gap_keywords,
)
from opportunity_engine.learned_query_overlay import (
    build_learned_query_overlay,
    merge_learned_query_overlays,
)
from opportunity_engine.missed_opportunity_learning import MissedOpportunityCase


LearningSearch = Callable[[str, str], Sequence[Mapping[str, Any]]]


@dataclass(frozen=True, slots=True)
class DailyLearningPolicy:
    max_candidates_per_run: int = 2
    min_recovered_cases: int = 1
    min_precision: float = 0.20
    max_terms_per_market: int = 5

    def __post_init__(self) -> None:
        if self.max_candidates_per_run < 0:
            raise ValueError("max_candidates_per_run must be >= 0")
        if self.min_recovered_cases < 1:
            raise ValueError("min_recovered_cases must be >= 1")
        if not 0.0 <= self.min_precision <= 1.0:
            raise ValueError("min_precision must be between 0 and 1")
        if self.max_terms_per_market < 1:
            raise ValueError("max_terms_per_market must be >= 1")


@dataclass(frozen=True, slots=True)
class DailyLearningOutcome:
    cases: tuple[MissedOpportunityCase, ...]
    candidates: tuple[KeywordLearningCandidate, ...]
    evaluations: tuple[KeywordEvaluationResult, ...]
    overlay: dict[str, Any]
    report: dict[str, Any]


def merge_case_memory(
    existing_cases: Sequence[MissedOpportunityCase],
    inbox_cases: Sequence[MissedOpportunityCase],
) -> list[MissedOpportunityCase]:
    """Append new ground-truth cases without resetting learned state."""
    merged: dict[str, MissedOpportunityCase] = {}
    for case in existing_cases:
        if case.case_id and case.case_id not in merged:
            merged[case.case_id] = case
    for case in inbox_cases:
        if case.case_id and case.case_id not in merged:
            merged[case.case_id] = case
    return list(merged.values())


def _diagnose_cases(cases: Sequence[MissedOpportunityCase]) -> list[MissedOpportunityCase]:
    return [case if case.root_cause else case.with_diagnosis() for case in cases]


def _existing_overlay_terms(overlay: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(overlay, Mapping):
        return []
    markets = overlay.get("markets")
    if not isinstance(markets, Mapping):
        return []
    terms: list[str] = []
    for rows in markets.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            term = " ".join(str(row.get("term") or "").casefold().split()).strip()
            if term:
                terms.append(term)
    return terms


def _apply_recoveries(
    cases: Sequence[MissedOpportunityCase],
    evaluations: Sequence[KeywordEvaluationResult],
) -> list[MissedOpportunityCase]:
    recovered_terms: dict[str, list[str]] = {}
    for evaluation in evaluations:
        if evaluation.status != "PROVEN":
            continue
        for case_id in evaluation.recovered_case_ids:
            recovered_terms.setdefault(case_id, []).append(evaluation.term)

    updated: list[MissedOpportunityCase] = []
    for case in cases:
        terms = recovered_terms.get(case.case_id) or []
        if not terms:
            updated.append(case)
            continue
        patterns = tuple(dict.fromkeys((*case.learned_patterns, *terms)))
        updated.append(
            replace(
                case,
                learned_patterns=patterns,
                learning_status="RECOVERED",
                repeat_miss=False,
            )
        )
    return updated


def run_daily_learning_cycle(
    *,
    existing_cases: Sequence[MissedOpportunityCase],
    inbox_cases: Sequence[MissedOpportunityCase],
    active_queries: Sequence[str],
    search: LearningSearch,
    existing_overlay: Mapping[str, Any] | None = None,
    policy: DailyLearningPolicy | None = None,
    search_enabled: bool = True,
    search_skip_reason: str | None = None,
) -> DailyLearningOutcome:
    """Run one bounded learning iteration and return state for persistence."""
    active_policy = policy or DailyLearningPolicy()
    cases = _diagnose_cases(merge_case_memory(existing_cases, inbox_cases))

    effective_active_queries = [*active_queries, *_existing_overlay_terms(existing_overlay)]
    candidates = propose_query_gap_keywords(
        cases,
        active_queries=effective_active_queries,
    )

    evaluations: list[KeywordEvaluationResult] = []
    errors: list[dict[str, str]] = []
    search_requests = 0
    if search_enabled and active_policy.max_candidates_per_run > 0:
        for candidate in candidates[: active_policy.max_candidates_per_run]:
            search_requests += 1
            try:
                evaluations.append(
                    evaluate_keyword_candidate(
                        candidate,
                        cases,
                        search,
                        min_recovered_cases=active_policy.min_recovered_cases,
                        min_precision=active_policy.min_precision,
                    )
                )
            except Exception as exc:  # provider boundary; preserve next-day learning
                errors.append(
                    {
                        "term": candidate.term,
                        "market_code": candidate.market_code,
                        "error_type": type(exc).__name__,
                        "error": str(exc)[:500],
                    }
                )

    new_overlay = build_learned_query_overlay(
        evaluations,
        max_terms_per_market=active_policy.max_terms_per_market,
    )
    overlay = merge_learned_query_overlays(
        existing_overlay,
        new_overlay,
        max_terms_per_market=active_policy.max_terms_per_market,
    )
    cases = _apply_recoveries(cases, evaluations)

    if not search_enabled:
        search_status = search_skip_reason or "DISABLED"
    elif not candidates:
        search_status = "NO_CANDIDATES"
    elif active_policy.max_candidates_per_run == 0:
        search_status = "BUDGET_ZERO"
    elif errors and not evaluations:
        search_status = "FAILED"
    elif errors:
        search_status = "PARTIAL"
    else:
        search_status = "SUCCESS"

    keyword_report = build_keyword_learning_report(candidates, evaluations)
    report = {
        "schema_version": "daily-learning-operator-1.0",
        "known_missed_opportunity_count": len(cases),
        "inbox_case_count": len(inbox_cases),
        "candidate_count": len(candidates),
        "evaluated_candidate_count": len(evaluations),
        "learning_search_requests": search_requests,
        "max_candidates_per_run": active_policy.max_candidates_per_run,
        "search_status": search_status,
        "evaluation_errors": errors,
        "proven_term_count_this_run": sum(
            1 for item in evaluations if item.status == "PROVEN"
        ),
        "active_learned_term_count": int(overlay.get("active_term_count") or 0),
        "recovered_case_count": sum(
            1 for case in cases if case.learning_status == "RECOVERED"
        ),
        "keyword_learning": keyword_report,
        "automatic_query_activation": True,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }

    return DailyLearningOutcome(
        cases=tuple(cases),
        candidates=tuple(candidates),
        evaluations=tuple(evaluations),
        overlay=overlay,
        report=report,
    )
