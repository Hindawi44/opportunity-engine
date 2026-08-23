from __future__ import annotations

from typing import Any


_SAFE_PATTERN_CODES = {
    "DIRECT_EVIDENCE_CONFIRMED_CLAIM",
    "GENERIC_EVIDENCE_REJECTED",
    "ADJACENT_NEGATIVE_SIGNAL",
    "CONFLICTING_RELEVANT_EVIDENCE",
}


def _clean_unique(values: list[Any]) -> tuple[list[str], bool]:
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    return list(dict.fromkeys(cleaned)), len(cleaned) != len(set(cleaned))


def _assess_pattern(pattern: dict[str, Any]) -> dict[str, Any]:
    code = str(pattern.get("pattern_code") or "").strip()
    pattern_id = str(pattern.get("pattern_id") or code).strip()
    blockers: list[str] = []

    run_ids_raw = list(pattern.get("run_ids", []) or [])
    run_ids, duplicate_runs = _clean_unique(run_ids_raw)
    example_ids, _ = _clean_unique(list(pattern.get("example_idea_ids", []) or []))
    claimed_count = pattern.get("observation_count")

    if code not in _SAFE_PATTERN_CODES:
        stage = "UNSAFE_PATTERN_BLOCKED"
        blockers.append("pattern code is not in the reviewed safe promotion allowlist")
    else:
        stage = ""

    integrity_failed = False
    if str(pattern.get("truth_status") or "") != "EVIDENCE_DERIVED":
        blockers.append("truth_status must be EVIDENCE_DERIVED")
        integrity_failed = True
    if str(pattern.get("source") or "") != "RUN_EVIDENCE":
        blockers.append("source must be RUN_EVIDENCE")
        integrity_failed = True
    if duplicate_runs:
        blockers.append("duplicate run ids cannot count as independent observations")
        integrity_failed = True
    if not isinstance(claimed_count, int) or claimed_count < 0:
        blockers.append("observation_count must be a non-negative integer")
        integrity_failed = True
    elif claimed_count != len(run_ids_raw) or claimed_count != len(run_ids):
        blockers.append("observation_count must equal the number of unique run ids")
        integrity_failed = True

    independent_runs = len(run_ids)
    example_count = len(example_ids)

    if integrity_failed:
        stage = "INTEGRITY_BLOCKED"
    elif stage == "UNSAFE_PATTERN_BLOCKED":
        pass
    elif independent_runs >= 3 and example_count < 2:
        stage = "DIVERSITY_BLOCKED"
        blockers.append("validation requires evidence across at least two distinct idea examples")
    elif independent_runs >= 5 and example_count >= 3:
        stage = "PRODUCTION_ELIGIBLE"
    elif independent_runs >= 3 and example_count >= 2:
        stage = "VALIDATED"
    elif independent_runs >= 2:
        stage = "REPEATED"
    else:
        stage = "SHADOW_ONLY"

    validated = stage in {"VALIDATED", "PRODUCTION_ELIGIBLE"}
    production_eligible = stage == "PRODUCTION_ELIGIBLE"
    return {
        "pattern_id": pattern_id,
        "pattern_code": code,
        "stage": stage,
        "truth_status": str(pattern.get("truth_status") or ""),
        "source": str(pattern.get("source") or ""),
        "independent_run_count": independent_runs,
        "example_diversity_count": example_count,
        "validated": validated,
        "production_eligible": production_eligible,
        "human_approval_required": production_eligible,
        "auto_apply_to_production": False,
        "blockers": blockers,
    }


def evaluate_pattern_promotions(memory: dict[str, Any]) -> dict[str, Any]:
    """Evaluate evidence-derived cross-run patterns with fail-closed promotion gates.

    Promotion is intentionally conservative:
    - 1 independent run: SHADOW_ONLY
    - 2 independent runs: REPEATED
    - >=3 runs across >=2 idea examples: VALIDATED
    - >=5 runs across >=3 idea examples: PRODUCTION_ELIGIBLE

    Even a production-eligible pattern is not automatically applied. It requires
    explicit approval in a later gate.
    """

    if memory.get("auto_apply_to_production") is True:
        raise ValueError("pattern promotion refuses memory that claims auto-apply to production")
    if str(memory.get("status") or "") != "MIND_FORGE_V2_FAST_CROSS_RUN_MEMORY_COMPLETE":
        raise ValueError("pattern promotion requires completed fast cross-run memory")
    if str(memory.get("source") or "") != "RUN_EVIDENCE":
        raise ValueError("pattern promotion requires RUN_EVIDENCE memory")

    patterns = [dict(row) for row in memory.get("patterns", []) or []]
    assessments = [_assess_pattern(row) for row in patterns]
    validated_codes = sorted(
        row["pattern_code"] for row in assessments if row["validated"]
    )
    production_codes = sorted(
        row["pattern_code"] for row in assessments if row["production_eligible"]
    )

    if production_codes:
        overall_stage = "PRODUCTION_ELIGIBLE"
    elif validated_codes:
        overall_stage = "VALIDATED"
    elif any(row["stage"] == "REPEATED" for row in assessments):
        overall_stage = "REPEATED"
    elif assessments:
        overall_stage = "SHADOW_ONLY"
    else:
        overall_stage = "NO_PATTERN"

    return {
        "status": "MIND_FORGE_V2_PATTERN_PROMOTION_COMPLETE",
        "overall_stage": overall_stage,
        "assessment_count": len(assessments),
        "validated_pattern_codes": validated_codes,
        "production_eligible_pattern_codes": production_codes,
        "human_approval_required": bool(production_codes),
        "auto_apply_to_production": False,
        "assessments": assessments,
    }
