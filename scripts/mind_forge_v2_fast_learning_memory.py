from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.mind_forge_v2_pattern_application import reconcile_pattern_applications
from scripts.mind_forge_v2_pattern_promotion import evaluate_pattern_promotions


_PATTERN_HINTS = {
    "DIRECT_EVIDENCE_CONFIRMED_CLAIM": {
        "action": "PREFER_DIRECT_BEHAVIORAL_EVIDENCE",
        "search_question": (
            "What direct behavioral, procurement, transaction, or operational evidence tests the exact claim?"
        ),
        "required_evidence": (
            "Prefer evidence of concrete behavior tied to the exact claim; source authority alone is not enough."
        ),
    },
    "GENERIC_EVIDENCE_REJECTED": {
        "action": "REQUIRE_EXACT_CLAIM_RELEVANCE",
        "search_question": (
            "Can the exact claim be tested with direct or narrowly adjacent evidence instead of generic background data?"
        ),
        "required_evidence": (
            "Do not treat generic sector statistics, broad policy, or adjacent-domain repair evidence as proof of the exact claim."
        ),
    },
    "ADJACENT_NEGATIVE_SIGNAL": {
        "action": "RESOLVE_NEGATIVE_SIGNAL_WITH_DIRECT_EVIDENCE",
        "search_question": (
            "What direct evidence confirms or falsifies the exact claim after a related negative or mixed signal?"
        ),
        "required_evidence": (
            "Seek direct evidence before promoting the idea; preserve the negative signal until it is specifically resolved."
        ),
    },
    "CONFLICTING_RELEVANT_EVIDENCE": {
        "action": "DISAMBIGUATE_CONFLICT_BEFORE_PROMOTION",
        "search_question": "What direct evidence explains why relevant sources disagree on the exact claim?",
        "required_evidence": (
            "Resolve the conflict with a more specific source or narrower claim before increasing confidence."
        ),
    },
}


def _copy_patterns(prior_memory: dict[str, Any]) -> dict[str, dict[str, Any]]:
    patterns: dict[str, dict[str, Any]] = {}
    for row in prior_memory.get("patterns", []) or []:
        code = str(row.get("pattern_code") or "").strip()
        if not code:
            continue
        patterns[code] = {
            **dict(row),
            "run_ids": list(row.get("run_ids", []) or []),
            "example_idea_ids": list(row.get("example_idea_ids", []) or []),
        }
    return patterns


def _record_pattern(
    found: dict[str, set[str]],
    code: str,
    idea_id: str,
) -> None:
    found.setdefault(code, set()).add(idea_id)


def _extract_pattern_codes(
    reasoning: dict[str, Any],
    evidence: dict[str, Any],
    final_rank: dict[str, Any],
) -> dict[str, set[str]]:
    assessments = {str(row["idea_id"]): row for row in reasoning.get("assessments", []) or []}
    ranking = {str(row["idea_id"]): row for row in final_rank.get("ranking", []) or []}
    by_idea: dict[str, list[dict[str, Any]]] = {}
    for raw in evidence.get("observations", []) or []:
        obs = dict(raw)
        idea_id = str(obs.get("idea_id") or "").strip()
        if not idea_id:
            continue
        by_idea.setdefault(idea_id, []).append(obs)

    if not ranking:
        raise ValueError("fast learning requires a non-empty final ranking")

    found: dict[str, set[str]] = {}
    for idea_id, row in ranking.items():
        if idea_id not in assessments:
            raise ValueError(f"ranked idea missing from reasoning assessments: {idea_id}")
        observations = by_idea.get(idea_id, [])
        evidence_status = str(row.get("evidence_status") or "")
        signal = float(row.get("evidence_signal", 0.0))
        evidence_count = int(row.get("evidence_count", len(observations)))
        relevant_count = int(row.get("relevant_evidence_count", 0))

        direct_support = any(
            str(obs.get("relevance") or "").upper() == "DIRECT"
            and str(obs.get("stance") or "").upper() == "SUPPORTS"
            for obs in observations
        )
        if evidence_status == "SUFFICIENT_RELEVANT_EVIDENCE" and signal > 0 and direct_support:
            _record_pattern(found, "DIRECT_EVIDENCE_CONFIRMED_CLAIM", idea_id)

        rejected_generic = any(
            str(obs.get("relevance") or "").upper() in {"GENERIC", "OFF_DOMAIN"}
            for obs in observations
        )
        if rejected_generic and relevant_count < evidence_count:
            _record_pattern(found, "GENERIC_EVIDENCE_REJECTED", idea_id)

        adjacent_negative = any(
            str(obs.get("relevance") or "").upper() == "ADJACENT"
            and str(obs.get("stance") or "").upper() in {"CONTRADICTS", "MIXED"}
            for obs in observations
        )
        if signal < 0 and adjacent_negative:
            _record_pattern(found, "ADJACENT_NEGATIVE_SIGNAL", idea_id)

        if bool(row.get("conflicting_evidence", False)) and relevant_count > 0:
            _record_pattern(found, "CONFLICTING_RELEVANT_EVIDENCE", idea_id)

    return found


def _pattern_row(
    code: str,
    *,
    run_id: str,
    idea_ids: set[str],
    prior: dict[str, Any] | None,
) -> dict[str, Any]:
    old = dict(prior or {})
    run_ids = list(old.get("run_ids", []) or [])
    if run_id not in run_ids:
        run_ids.append(run_id)
    examples = list(old.get("example_idea_ids", []) or [])
    for idea_id in sorted(idea_ids):
        if idea_id not in examples:
            examples.append(idea_id)
    return {
        "pattern_id": str(old.get("pattern_id") or f"v2-fast-{code.casefold().replace('_', '-') }"),
        "pattern_code": code,
        "truth_status": "EVIDENCE_DERIVED",
        "source": "RUN_EVIDENCE",
        "observation_count": len(run_ids),
        "run_ids": run_ids,
        "example_idea_ids": examples[-10:],
        "last_run_id": run_id,
        "auto_verified": False,
    }


def _adjustment_for(pattern: dict[str, Any]) -> dict[str, Any]:
    code = str(pattern["pattern_code"])
    hint = _PATTERN_HINTS[code]
    return {
        **hint,
        "origin_memory_id": str(pattern["pattern_id"]),
        "mode": "SHADOW_HINT",
        "may_change_search_priority": True,
        "may_auto_reject_ideas": False,
        "pattern_observation_count": int(pattern["observation_count"]),
    }


def learn_from_run(
    reasoning: dict[str, Any],
    evidence: dict[str, Any],
    final_rank: dict[str, Any],
    *,
    run_id: str,
    prior_memory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Extract reusable, experiment-free shadow patterns from a completed run."""

    run_id = str(run_id).strip()
    if not run_id:
        raise ValueError("run_id is required")

    prior_memory = dict(prior_memory or {})
    prior_run_ids = list(prior_memory.get("run_ids", []) or [])
    if run_id in prior_run_ids:
        raise ValueError(f"duplicate run: {run_id}")

    found = _extract_pattern_codes(reasoning, evidence, final_rank)
    prior_patterns = _copy_patterns(prior_memory)
    patterns = dict(prior_patterns)
    for code, idea_ids in found.items():
        patterns[code] = _pattern_row(
            code,
            run_id=run_id,
            idea_ids=idea_ids,
            prior=prior_patterns.get(code),
        )

    run_ids = prior_run_ids + [run_id]
    ordered_patterns = sorted(patterns.values(), key=lambda row: str(row["pattern_code"]))
    max_observations = max((int(row.get("observation_count", 0)) for row in ordered_patterns), default=0)
    if max_observations >= 2:
        activation = "ELIGIBLE_FOR_HUMAN_REVIEW"
    elif ordered_patterns:
        activation = "SHADOW_ONLY"
    else:
        activation = "NO_REUSABLE_PATTERN"

    adjustments = [_adjustment_for(row) for row in ordered_patterns if row["pattern_code"] in _PATTERN_HINTS]
    result = {
        "status": "MIND_FORGE_V2_FAST_CROSS_RUN_MEMORY_COMPLETE",
        "source": "RUN_EVIDENCE",
        "run_ids": run_ids,
        "run_count": len(run_ids),
        "patterns": ordered_patterns,
        "pattern_activation_state": activation,
        "auto_apply_to_production": False,
        "next_cycle_search_adjustments": adjustments,
        "pattern_applications": [dict(row) for row in prior_memory.get("pattern_applications", []) or []],
    }
    promotion = evaluate_pattern_promotions(result)
    result["promotion_evaluation"] = promotion
    if promotion["overall_stage"] == "PRODUCTION_ELIGIBLE":
        result["pattern_activation_state"] = "PROMOTION_ELIGIBLE"
    elif promotion["overall_stage"] == "VALIDATED":
        result["pattern_activation_state"] = "VALIDATED"
    return reconcile_pattern_applications(result)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reasoning_json")
    parser.add_argument("evidence_json")
    parser.add_argument("final_rank_json")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--prior-memory")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    reasoning = json.loads(Path(args.reasoning_json).read_text(encoding="utf-8"))
    evidence = json.loads(Path(args.evidence_json).read_text(encoding="utf-8"))
    final_rank = json.loads(Path(args.final_rank_json).read_text(encoding="utf-8"))
    prior = None
    if args.prior_memory:
        prior = json.loads(Path(args.prior_memory).read_text(encoding="utf-8"))
    result = learn_from_run(
        reasoning,
        evidence,
        final_rank,
        run_id=args.run_id,
        prior_memory=prior,
    )
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "run_count": result["run_count"],
        "pattern_count": len(result["patterns"]),
        "pattern_activation_state": result["pattern_activation_state"],
        "promotion_stage": result["promotion_evaluation"]["overall_stage"],
        "active_pattern_application_count": result.get("active_pattern_application_count", 0),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
