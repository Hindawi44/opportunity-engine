"""Read-only proof report for promotion-gated QUERY_GAP learning.

This module does not search, learn, promote, or mutate production. It converts
already-durable missed-opportunity evidence plus shadow/active overlays into one
operator-readable answer: did the baseline miss, did shadow prove the learned
pattern by direct replay or independent holdout transfer, how noisy was the
proof, and is the term merely eligible for explicit promotion?

A single hidden holdout proves transfer but is not enough for transfer-based
promotion eligibility. Repeated transfer requires multiple unique independent
holdout cases so repeated recovery of the same case cannot masquerade as
replication.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from opportunity_engine.missed_opportunity_learning import MissedOpportunityCase

SCHEMA_VERSION = "safe-learning-proof-1.1"
DEFAULT_MIN_INDEPENDENT_TRANSFER_CASES = 2


def _rows_for_market(
    overlay: Mapping[str, Any] | None,
    market_code: str,
) -> list[Mapping[str, Any]]:
    if not isinstance(overlay, Mapping):
        return []
    markets = overlay.get("markets")
    if not isinstance(markets, Mapping):
        return []
    rows = markets.get(market_code.upper())
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, Mapping)]


def _ids(value: object) -> list[str]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        return []
    return sorted(
        {
            str(item).strip()
            for item in value
            if str(item).strip()
        }
    )


def _cumulative_evidence_ids(row: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """Return source replay IDs and hidden transfer IDs with old-row fallback."""
    source_replay = _ids(row.get("source_replay_case_ids"))
    transfer_validation = _ids(row.get("transfer_validation_case_ids"))
    if source_replay or transfer_validation:
        return source_replay, transfer_validation

    scope = str(row.get("evaluation_scope") or "SOURCE_CASE_REPLAY").strip().upper()
    recovered = _ids(row.get("recovered_case_ids"))
    if scope == "HOLDOUT_TRANSFER":
        return [], recovered
    return recovered, []


def _matching_shadow_row(
    case: MissedOpportunityCase,
    shadow_overlay: Mapping[str, Any] | None,
) -> tuple[Mapping[str, Any] | None, str | None]:
    for row in _rows_for_market(shadow_overlay, case.market_code):
        if str(row.get("source_verdict") or "").strip().upper() != "PROVEN":
            continue
        source_replay_ids, transfer_validation_ids = _cumulative_evidence_ids(row)
        support_ids = set(_ids(row.get("support_case_ids")))
        if transfer_validation_ids and case.case_id in support_ids:
            return row, "HOLDOUT_TRANSFER"
        if case.case_id in set(source_replay_ids):
            return row, "SOURCE_CASE_REPLAY"
    return None, None


def _proof_row_for_case(
    case: MissedOpportunityCase,
    shadow_overlay: Mapping[str, Any] | None,
    active_overlay: Mapping[str, Any] | None,
    *,
    min_precision: float,
    min_independent_transfer_cases: int,
) -> dict[str, Any]:
    shadow_match, proof_mode = _matching_shadow_row(case, shadow_overlay)

    if shadow_match is None:
        return {
            "case_id": case.case_id,
            "market_code": case.market_code,
            "baseline_missed": True,
            "baseline_root_cause": "QUERY_GAP",
            "shadow_recovered": False,
            "shadow_transfer_proven": False,
            "shadow_proof_mode": None,
            "shadow_term": None,
            "shadow_precision": None,
            "shadow_raw_hit_count": None,
            "shadow_verified_relevant_count": None,
            "shadow_false_positive_count": None,
            "shadow_false_positive_rate": None,
            "shadow_validation_case_ids": [],
            "independent_transfer_case_count": 0,
            "min_independent_transfer_cases": min_independent_transfer_cases,
            "repeated_transfer_proven": False,
            "production_term_active": False,
            "production_unchanged_during_shadow": True,
            "promotion_eligible": False,
            "automatic_promotion": False,
        }

    term = " ".join(str(shadow_match.get("term") or "").casefold().split()).strip()
    precision = float(shadow_match.get("precision") or 0.0)
    raw_count_value = shadow_match.get("raw_hit_count")
    relevant_count_value = shadow_match.get("verified_relevant_count")
    raw_count = int(raw_count_value) if isinstance(raw_count_value, int) else None
    relevant_count = int(relevant_count_value) if isinstance(relevant_count_value, int) else None
    false_positive_count = (
        max(0, raw_count - relevant_count)
        if raw_count is not None and relevant_count is not None
        else None
    )
    false_positive_rate = (
        round(false_positive_count / raw_count, 6)
        if false_positive_count is not None and raw_count and raw_count > 0
        else (0.0 if false_positive_count == 0 and raw_count == 0 else None)
    )

    _source_replay_ids, transfer_validation_ids = _cumulative_evidence_ids(shadow_match)
    validation_case_ids = transfer_validation_ids if proof_mode == "HOLDOUT_TRANSFER" else []
    independent_transfer_case_count = len(set(validation_case_ids))
    repeated_transfer_proven = (
        proof_mode == "HOLDOUT_TRANSFER"
        and independent_transfer_case_count >= min_independent_transfer_cases
    )

    production_active = False
    for row in _rows_for_market(active_overlay, case.market_code):
        active_term = " ".join(str(row.get("term") or "").casefold().split()).strip()
        if active_term != term:
            continue
        if (
            str(row.get("promotion_status") or "").strip().upper() == "PROMOTED"
            and str(row.get("activation_source") or "").strip().upper() == "EXPLICIT_PROMOTION"
        ):
            production_active = True
            break

    precision_passed = bool(term) and precision >= min_precision
    if proof_mode == "HOLDOUT_TRANSFER":
        promotion_eligible = (
            precision_passed and repeated_transfer_proven and not production_active
        )
    else:
        # Preserve the existing direct-replay proof contract. The stricter
        # replication requirement applies only to transfer/generalization claims.
        promotion_eligible = precision_passed and not production_active

    return {
        "case_id": case.case_id,
        "market_code": case.market_code,
        "baseline_missed": True,
        "baseline_root_cause": "QUERY_GAP",
        "shadow_recovered": proof_mode == "SOURCE_CASE_REPLAY",
        "shadow_transfer_proven": proof_mode == "HOLDOUT_TRANSFER",
        "shadow_proof_mode": proof_mode,
        "shadow_term": term,
        "shadow_precision": precision,
        "shadow_raw_hit_count": raw_count,
        "shadow_verified_relevant_count": relevant_count,
        "shadow_false_positive_count": false_positive_count,
        "shadow_false_positive_rate": false_positive_rate,
        "shadow_validation_case_ids": validation_case_ids,
        "independent_transfer_case_count": independent_transfer_case_count,
        "min_independent_transfer_cases": min_independent_transfer_cases,
        "repeated_transfer_proven": repeated_transfer_proven,
        "production_term_active": production_active,
        "production_unchanged_during_shadow": not production_active,
        "promotion_eligible": promotion_eligible,
        "automatic_promotion": False,
    }


def build_query_gap_safe_learning_proof(
    cases: Sequence[MissedOpportunityCase],
    *,
    shadow_overlay: Mapping[str, Any] | None,
    active_overlay: Mapping[str, Any] | None,
    min_precision: float = 0.20,
    min_independent_transfer_cases: int = DEFAULT_MIN_INDEPENDENT_TRANSFER_CASES,
) -> dict[str, Any]:
    """Build a read-only QUERY_GAP proof report from durable source misses."""
    if not 0.0 <= min_precision <= 1.0:
        raise ValueError("min_precision must be between 0 and 1")
    if min_independent_transfer_cases < 1:
        raise ValueError("min_independent_transfer_cases must be >= 1")

    query_cases: list[MissedOpportunityCase] = []
    for raw in cases:
        case = raw if raw.root_cause else raw.with_diagnosis()
        if case.root_cause != "QUERY_GAP" or not case.stock_proven:
            continue
        query_cases.append(case)

    rows = [
        _proof_row_for_case(
            case,
            shadow_overlay,
            active_overlay,
            min_precision=min_precision,
            min_independent_transfer_cases=min_independent_transfer_cases,
        )
        for case in query_cases
    ]
    recovered = [row for row in rows if row["shadow_recovered"]]
    transfer_proven = [row for row in rows if row["shadow_transfer_proven"]]
    repeated_transfer = [row for row in rows if row["repeated_transfer_proven"]]
    proven = [*recovered, *transfer_proven]
    eligible = [row for row in rows if row["promotion_eligible"]]
    promoted = [row for row in rows if row["production_term_active"]]
    noisy = [
        row
        for row in proven
        if float(row.get("shadow_precision") or 0.0) < min_precision
    ]
    pending_replication = [
        row
        for row in transfer_proven
        if float(row.get("shadow_precision") or 0.0) >= min_precision
        and not row["repeated_transfer_proven"]
    ]

    if not query_cases:
        status = "NO_QUERY_GAP_CASES"
    elif promoted:
        status = "PROMOTED_PROOF_EXISTS"
    elif eligible:
        status = "SHADOW_PASSED"
    elif pending_replication:
        status = "SHADOW_TRANSFER_PENDING_REPLICATION"
    elif proven and len(noisy) == len(proven):
        status = (
            "SHADOW_TRANSFER_PROVEN_BUT_NOISY"
            if transfer_proven and not recovered
            else "SHADOW_RECOVERED_BUT_NOISY"
        )
    elif proven:
        status = (
            "SHADOW_TRANSFER_PROVEN_NOT_ELIGIBLE"
            if transfer_proven and not recovered
            else "SHADOW_RECOVERED_NOT_ELIGIBLE"
        )
    else:
        status = "NO_SHADOW_RECOVERY_YET"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "proof_scope": "QUERY_GAP",
        "query_gap_case_count": len(query_cases),
        "shadow_recovered_case_count": len(recovered),
        "shadow_transfer_proven_case_count": len(transfer_proven),
        "repeated_transfer_proven_case_count": len(repeated_transfer),
        "promotion_eligible_count": len(eligible),
        "promoted_proof_count": len(promoted),
        "min_precision": min_precision,
        "min_independent_transfer_cases": min_independent_transfer_cases,
        "production_mutation_performed_by_report": False,
        "automatic_promotion": False,
        "cases": rows,
    }
