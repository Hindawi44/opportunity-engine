"""Daily bounded operator for missed-opportunity learning.

The operator joins durable missed-opportunity memory with a curated inbox,
proposes search terms only for diagnosed QUERY_GAP cases, shadow-evaluates a
small bounded number of candidates, retains previously proven shadow skills,
and records whether proof came from direct replay or an independent hidden
holdout transfer case.

PROVEN is not production-active. An exact explicit promotion decision is
required before a proven shadow term can enter the active runtime overlay.

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
from opportunity_engine.learning_promotion_gate import select_promoted_query_overlay
from opportunity_engine.missed_opportunity_learning import MissedOpportunityCase
from opportunity_engine.safe_learning_proof import (
    DEFAULT_MIN_INDEPENDENT_TRANSFER_CASES,
)


LearningSearch = Callable[[str, str], Sequence[Mapping[str, Any]]]
PromotionDecisions = Mapping[tuple[str, str], str]


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
    shadow_overlay: dict[str, Any]
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
    """Return Shadow terms that should block fresh candidate generation.

    A transfer-proven term with fewer than the required number of unique hidden
    holdouts is intentionally *not* treated as active coverage yet. That lets a
    later bounded run gather independent replication. Once the threshold is met
    (or the term is explicitly promoted), it blocks re-proposal and stops
    consuming learning budget.
    """
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
            if not term:
                continue

            promoted = (
                str(row.get("promotion_status") or "").strip().upper() == "PROMOTED"
                or str(row.get("activation_source") or "").strip().upper()
                == "EXPLICIT_PROMOTION"
            )
            if promoted:
                terms.append(term)
                continue

            raw_transfer_ids = row.get("transfer_validation_case_ids")
            transfer_ids = {
                str(item).strip()
                for item in raw_transfer_ids
                if str(item).strip()
            } if isinstance(raw_transfer_ids, (list, tuple, set, frozenset)) else set()

            scopes = {
                str(item).strip().upper()
                for item in (row.get("evaluation_scopes") or [])
                if str(item).strip()
            } if isinstance(row.get("evaluation_scopes"), (list, tuple, set, frozenset)) else set()
            scope = str(row.get("evaluation_scope") or "").strip().upper()
            if scope:
                scopes.add(scope)
            if transfer_ids:
                scopes.add("HOLDOUT_TRANSFER")

            count_value = row.get("independent_transfer_case_count")
            stored_count = count_value if isinstance(count_value, int) else 0
            transfer_count = max(len(transfer_ids), stored_count)
            pending_transfer_replication = (
                "HOLDOUT_TRANSFER" in scopes
                and transfer_count < DEFAULT_MIN_INDEPENDENT_TRANSFER_CASES
            )
            if pending_transfer_replication:
                continue
            terms.append(term)
    return terms


def _apply_learning_results(
    cases: Sequence[MissedOpportunityCase],
    evaluations: Sequence[KeywordEvaluationResult],
) -> list[MissedOpportunityCase]:
    """Apply proof to source misses without mixing holdouts into durable memory.

    Direct replay marks the exact missed case RECOVERED. Holdout transfer proof
    instead marks the source miss TRANSFER_PROVEN: the original historical page
    was not necessarily rediscovered, but a pattern learned from it independently
    recovered a hidden relevant case that was not used to generate the pattern.
    """
    direct_terms: dict[str, list[str]] = {}
    transfer_terms: dict[str, list[str]] = {}
    for evaluation in evaluations:
        if evaluation.status != "PROVEN":
            continue
        if evaluation.evaluation_scope == "HOLDOUT_TRANSFER":
            for case_id in evaluation.support_case_ids:
                transfer_terms.setdefault(case_id, []).append(evaluation.term)
        else:
            for case_id in evaluation.recovered_case_ids:
                direct_terms.setdefault(case_id, []).append(evaluation.term)

    updated: list[MissedOpportunityCase] = []
    for case in cases:
        direct = direct_terms.get(case.case_id) or []
        transfer = transfer_terms.get(case.case_id) or []
        terms = [*direct, *transfer]
        if not terms:
            updated.append(case)
            continue
        patterns = tuple(dict.fromkeys((*case.learned_patterns, *terms)))
        status = "RECOVERED" if direct else "TRANSFER_PROVEN"
        updated.append(
            replace(
                case,
                learned_patterns=patterns,
                learning_status=status,
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
    validation_cases: Sequence[MissedOpportunityCase] | None = None,
    existing_overlay: Mapping[str, Any] | None = None,
    existing_shadow_overlay: Mapping[str, Any] | None = None,
    promotion_decisions: PromotionDecisions | None = None,
    policy: DailyLearningPolicy | None = None,
    search_enabled: bool = True,
    search_skip_reason: str | None = None,
) -> DailyLearningOutcome:
    """Run one bounded learning iteration and return state for persistence.

    Candidate generation always uses the real missed-opportunity memory. If
    ``validation_cases`` are supplied, they are a hidden holdout set used only
    for evaluation; they never enter candidate generation or durable miss memory.
    This prevents a candidate from being rewarded for merely memorizing the case
    that generated it.

    ``existing_overlay`` is treated as legacy learned state and migrated into
    shadow knowledge. It is never trusted as production-active unless the exact
    term is present in ``promotion_decisions`` with status PROMOTED.
    """
    active_policy = policy or DailyLearningPolicy()
    cases = _diagnose_cases(merge_case_memory(existing_cases, inbox_cases))
    holdouts = list(validation_cases or [])

    # Migrate any pre-gate active overlay into shadow evidence. This is fail-safe:
    # legacy auto-activated terms stop influencing production until explicitly
    # promoted, but their evidence is retained and not re-learned every day.
    known_shadow_overlay = merge_learned_query_overlays(
        existing_shadow_overlay,
        existing_overlay,
        max_terms_per_market=active_policy.max_terms_per_market,
    )
    effective_active_queries = [
        *active_queries,
        *_existing_overlay_terms(known_shadow_overlay),
    ]
    candidates = propose_query_gap_keywords(
        cases,
        active_queries=effective_active_queries,
    )

    evaluation_targets = holdouts if holdouts else cases
    evaluation_scope = "HOLDOUT_TRANSFER" if holdouts else "SOURCE_CASE_REPLAY"
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
                        evaluation_targets,
                        search,
                        min_recovered_cases=active_policy.min_recovered_cases,
                        min_precision=active_policy.min_precision,
                        evaluation_scope=evaluation_scope,
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

    new_shadow_overlay = build_learned_query_overlay(
        evaluations,
        max_terms_per_market=active_policy.max_terms_per_market,
    )
    shadow_overlay = merge_learned_query_overlays(
        known_shadow_overlay,
        new_shadow_overlay,
        max_terms_per_market=active_policy.max_terms_per_market,
    )
    overlay = select_promoted_query_overlay(
        shadow_overlay,
        promotion_decisions,
        max_terms_per_market=active_policy.max_terms_per_market,
    )
    cases = _apply_learning_results(cases, evaluations)

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
    active_count = int(overlay.get("active_term_count") or 0)
    shadow_count = int(shadow_overlay.get("active_term_count") or 0)
    report = {
        "schema_version": "daily-learning-operator-1.1",
        "known_missed_opportunity_count": len(cases),
        "inbox_case_count": len(inbox_cases),
        "validation_case_count": len(holdouts),
        "evaluation_scope": evaluation_scope,
        "candidate_count": len(candidates),
        "evaluated_candidate_count": len(evaluations),
        "learning_search_requests": search_requests,
        "max_candidates_per_run": active_policy.max_candidates_per_run,
        "search_status": search_status,
        "evaluation_errors": errors,
        "proven_term_count_this_run": sum(
            1 for item in evaluations if item.status == "PROVEN"
        ),
        "shadow_proven_term_count": shadow_count,
        "active_learned_term_count": active_count,
        "promoted_term_count": active_count,
        "promotion_decision_count": len(promotion_decisions or {}),
        "recovered_case_count": sum(
            1 for case in cases if case.learning_status == "RECOVERED"
        ),
        "transfer_proven_case_count": sum(
            1 for case in cases if case.learning_status == "TRANSFER_PROVEN"
        ),
        "keyword_learning": keyword_report,
        "promotion_gate_enforced": True,
        "automatic_query_activation": False,
        "production_query_activation_requires_explicit_promotion": True,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }

    return DailyLearningOutcome(
        cases=tuple(cases),
        candidates=tuple(candidates),
        evaluations=tuple(evaluations),
        shadow_overlay=shadow_overlay,
        overlay=overlay,
        report=report,
    )
