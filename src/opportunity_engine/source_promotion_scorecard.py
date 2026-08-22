"""Read-only promotion readiness scorecard for learned opportunity sources.

The scorecard may recommend a source for explicit promotion, but it never changes
production configuration or activates a source. Hard safety gates override the
numeric score.
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA_VERSION = "source-promotion-scorecard-1.0"


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _source_candidate(source_candidates: Mapping[str, Any], domain: str) -> Mapping[str, Any] | None:
    rows = source_candidates.get("source_candidates") or []
    if not isinstance(rows, list):
        return None
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if _compact(row.get("source_domain")).casefold().rstrip(".") == domain:
            return row
    return None


def _verified_live_rows(live_proof: Mapping[str, Any], domain: str) -> list[Mapping[str, Any]]:
    rows = live_proof.get("verified_new_opportunities") or []
    if not isinstance(rows, list):
        return []
    return [
        row
        for row in rows
        if isinstance(row, Mapping)
        and _compact(row.get("source_domain")).casefold().rstrip(".") == domain
        and row.get("source_page_verified") is True
    ]


def build_source_promotion_scorecard(
    source_candidates: Mapping[str, Any],
    live_proof: Mapping[str, Any],
    access_proof: Mapping[str, Any],
    *,
    source_domain: str,
    independent_live_discovery_rounds: int,
    live_source_candidate_count: int | None = None,
    minimum_score: float = 85.0,
) -> dict[str, Any]:
    """Build a promotion recommendation from immutable evidence only.

    PROMOTE_CANDIDATE is advisory. Explicit approval and a separate promotion
    mechanism are still required to change production.
    """
    domain = _compact(source_domain).casefold().rstrip(".")
    if not domain:
        raise ValueError("source_domain is required")
    if independent_live_discovery_rounds < 0:
        raise ValueError("independent_live_discovery_rounds must be >= 0")
    if live_source_candidate_count is not None and live_source_candidate_count < 0:
        raise ValueError("live_source_candidate_count must be >= 0")

    candidate = _source_candidate(source_candidates, domain)
    verified_rows = _verified_live_rows(live_proof, domain)
    teaching_contamination = sum(1 for row in verified_rows if row.get("teaching_url") is True)
    production_leak = sum(1 for row in verified_rows if row.get("production_active") is True)
    verified_count = len(verified_rows)

    initial_verified = int((candidate or {}).get("verified_opportunity_count") or 0)
    observed_candidates = verified_count if live_source_candidate_count is None else live_source_candidate_count
    false_positive_count = max(0, observed_candidates - verified_count)
    verification_yield = (verified_count / observed_candidates) if observed_candidates else 0.0
    false_positive_rate = (false_positive_count / observed_candidates) if observed_candidates else 0.0

    access_domain = _compact(access_proof.get("source_domain")).casefold().rstrip(".")
    access_ratio = float(access_proof.get("usable_public_ratio") or 0.0)
    access_blockers = sum(
        int(access_proof.get(key) or 0)
        for key in (
            "blocked_403_count",
            "rate_limited_429_count",
            "challenge_count",
            "login_redirect_count",
            "html_drift_count",
        )
    )
    access_stable = (
        access_domain == domain
        and access_ratio >= 0.95
        and access_blockers == 0
        and _compact(access_proof.get("verdict")) in {"PUBLIC_ACCESS_STABLE", "PUBLIC_ACCESS_STABLE_PARTIAL"}
    )

    evidence_score = min(100.0, initial_verified * 50.0)
    live_recovery_score = min(100.0, verified_count * 20.0)
    verification_score = min(100.0, verification_yield * 100.0)
    access_score = 100.0 if access_stable else max(0.0, min(100.0, access_ratio * 100.0 - access_blockers * 25.0))
    repeatability_score = min(100.0, independent_live_discovery_rounds * 50.0)

    score = round(
        evidence_score * 0.20
        + live_recovery_score * 0.30
        + verification_score * 0.20
        + access_score * 0.20
        + repeatability_score * 0.10,
        2,
    )

    blocking_reasons: list[str] = []
    if candidate is None or _compact(candidate.get("status")) != "VALIDATED_SOURCE" or candidate.get("shadow_eligible") is not True:
        blocking_reasons.append("SOURCE_NOT_VALIDATED_FOR_SHADOW")
    if candidate is not None and candidate.get("production_active") is True:
        blocking_reasons.append("SOURCE_ALREADY_PRODUCTION_ACTIVE")
    if initial_verified < 2:
        blocking_reasons.append("INSUFFICIENT_GROUND_TRUTH_EVIDENCE")
    if verified_count < 3:
        blocking_reasons.append("INSUFFICIENT_VERIFIED_LIVE_RECOVERY")
    if teaching_contamination:
        blocking_reasons.append("NOVELTY_CONTAMINATED_BY_TEACHING_URL")
    if production_leak:
        blocking_reasons.append("SHADOW_PRODUCTION_LEAK")
    if live_proof.get("production_mutation") is True:
        blocking_reasons.append("LIVE_PROOF_MUTATED_PRODUCTION")
    if not access_stable:
        blocking_reasons.append("ACCESS_NOT_STABLE")
    if independent_live_discovery_rounds < 2:
        blocking_reasons.append("NEEDS_SECOND_INDEPENDENT_LIVE_DISCOVERY_ROUND")
    if score < minimum_score:
        blocking_reasons.append("READINESS_SCORE_BELOW_THRESHOLD")

    decision = "PROMOTE_CANDIDATE" if not blocking_reasons else "KEEP_SHADOW"
    source_name = _compact((candidate or {}).get("source_name")) or domain

    return {
        "schema_version": SCHEMA_VERSION,
        "source_name": source_name,
        "source_domain": domain,
        "decision": decision,
        "promotion_readiness_score": score,
        "minimum_promotion_score": minimum_score,
        "blocking_reasons": blocking_reasons,
        "dimensions": {
            "ground_truth_evidence": round(evidence_score, 2),
            "live_recovery": round(live_recovery_score, 2),
            "verification_quality": round(verification_score, 2),
            "access_stability": round(access_score, 2),
            "repeatability": round(repeatability_score, 2),
        },
        "metrics": {
            "initial_verified_opportunity_count": initial_verified,
            "verified_new_opportunity_count": verified_count,
            "live_source_candidate_count": observed_candidates,
            "verification_yield": round(verification_yield, 4),
            "false_positive_count": false_positive_count,
            "false_positive_rate": round(false_positive_rate, 4),
            "teaching_url_recovery_count": teaching_contamination,
            "independent_live_discovery_rounds": independent_live_discovery_rounds,
            "access_round_count": int(access_proof.get("round_count") or 0),
            "access_usable_public_ratio": round(access_ratio, 4),
            "access_blocker_event_count": access_blockers,
        },
        "promotion_requires_explicit_approval": True,
        "production_active": False,
        "production_mutation": False,
        "automatic_source_addition": False,
        "automatic_promotion": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
