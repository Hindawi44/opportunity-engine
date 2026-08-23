from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.mind_forge_v2_pattern_application import reconcile_pattern_applications


def _shadow_hints(prior_memory: dict[str, Any] | None) -> list[dict[str, str]]:
    if not prior_memory:
        return []
    if prior_memory.get("auto_apply_to_production") is True:
        raise ValueError("adaptive memory may not auto-apply to production")

    hints: list[dict[str, str]] = []
    for row in prior_memory.get("next_cycle_search_adjustments", []) or []:
        if str(row.get("mode")) != "SHADOW_HINT":
            continue
        if row.get("may_auto_reject_ideas") is True:
            raise ValueError("shadow memory may not auto-reject ideas")
        question = str(row.get("search_question") or "").strip()
        evidence = str(row.get("required_evidence") or "").strip()
        action = str(row.get("action") or "").strip()
        if not question or not evidence:
            continue
        hints.append({
            "action": action,
            "search_question": question,
            "required_evidence": evidence,
            "origin_memory_id": str(row.get("origin_memory_id") or "").strip(),
        })
    return hints


def _approved_policies(prior_memory: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not prior_memory or not prior_memory.get("pattern_applications"):
        return []
    reconciled = reconcile_pattern_applications(prior_memory)
    policies: list[dict[str, Any]] = []
    for raw in reconciled.get("approved_production_adjustments", []) or []:
        row = dict(raw)
        if str(row.get("mode") or "") != "APPROVED_POLICY_HINT":
            continue
        if row.get("human_approval_recorded") is not True:
            raise ValueError("approved policy is missing explicit human approval")
        if row.get("may_auto_reject_ideas") is True:
            raise ValueError("approved memory policy may not auto-reject ideas")
        question = str(row.get("search_question") or "").strip()
        evidence = str(row.get("required_evidence") or "").strip()
        application_id = str(row.get("application_id") or "").strip()
        if not question or not evidence or not application_id:
            continue
        policies.append({
            "action": str(row.get("action") or "").strip(),
            "search_question": question,
            "required_evidence": evidence,
            "origin_memory_id": str(row.get("origin_memory_id") or "").strip(),
            "application_id": application_id,
            "approved_by": str(row.get("approved_by") or "").strip(),
            "human_approval_recorded": True,
            "mode": "APPROVED_POLICY_HINT",
            "may_auto_reject_ideas": False,
        })
    return policies


def build_top3_research_plan(
    reasoning: dict[str, Any],
    prior_memory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selected = list(reasoning.get("selected_idea_ids", []) or [])
    assessments = {str(row["idea_id"]): row for row in reasoning.get("assessments", []) or []}
    if len(selected) != 3:
        raise ValueError(f"expected exactly 3 selected ideas, got {len(selected)}")

    approved = _approved_policies(prior_memory)
    approved_origins = {str(row.get("origin_memory_id") or "") for row in approved}
    hints = [
        row for row in _shadow_hints(prior_memory)
        if str(row.get("origin_memory_id") or "") not in approved_origins
    ]

    requests: list[dict[str, Any]] = []
    for rank, idea_id in enumerate(selected, start=1):
        idea_id = str(idea_id)
        if idea_id not in assessments:
            raise ValueError(f"selected idea missing from assessments: {idea_id}")
        row = assessments[idea_id]
        critique = row.get("critique", {}) or {}
        assumption = str(critique.get("key_assumption") or "").strip()
        risk = str(critique.get("key_risk") or "").strip()
        title = str(row.get("title") or idea_id)
        if assumption:
            claim = assumption
        elif risk:
            claim = risk
        else:
            claim = f"There is a real, material need in Norway for the mechanism proposed by {title}."
        requests.append({
            "request_id": f"v2-top3-{rank}",
            "idea_id": idea_id,
            "title": title,
            "claim_text": claim,
            "why_material": "This is the single highest-value uncertainty to resolve before final ranking.",
            "route": "WEB",
            "acceptable_source_types": ["official", "public_data", "primary", "academic", "industry", "company"],
            "max_search_operations": 1,
            "max_results": 3,
            "shadow_search_hints": hints,
            "approved_search_policies": approved,
        })

    if approved and hints:
        adaptive_mode = "APPROVED_POLICY_AND_SHADOW"
    elif approved:
        adaptive_mode = "APPROVED_POLICY"
    elif hints:
        adaptive_mode = "SHADOW_ONLY"
    else:
        adaptive_mode = "NONE"

    return {
        "status": "MIND_FORGE_V2_TOP3_RESEARCH_PLAN_READY",
        "candidate_count": 3,
        "request_count": len(requests),
        "max_total_search_operations": 3,
        "max_operations_per_request": 1,
        "uses_mechanism_family_for_routing": False,
        "adaptive_memory_mode": adaptive_mode,
        "adaptive_hint_count": len(hints),
        "approved_policy_count": len(approved),
        "may_auto_reject_ideas_from_memory": False,
        "requests": requests,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reasoning_json")
    parser.add_argument("--prior-memory")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    reasoning = json.loads(Path(args.reasoning_json).read_text(encoding="utf-8"))
    memory = None
    if args.prior_memory:
        memory = json.loads(Path(args.prior_memory).read_text(encoding="utf-8"))
    result = build_top3_research_plan(reasoning, memory)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "request_count": result["request_count"],
        "adaptive_memory_mode": result["adaptive_memory_mode"],
        "adaptive_hint_count": result["adaptive_hint_count"],
        "approved_policy_count": result["approved_policy_count"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
