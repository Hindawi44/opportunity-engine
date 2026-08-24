from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from typing import Any


_ROUTE_SEED_RE = re.compile(
    r"Improve discovery intelligence for\s+"
    r"(?P<market>[A-Z]{2})\s*/\s*"
    r"(?P<domain>CLOTHING_INVENTORY|FABRIC_PROCUREMENT)\s*/\s*"
    r"(?P<slot>[A-Z_]+)\.",
    re.IGNORECASE,
)


def _top_row(final_rank: dict[str, Any]) -> dict[str, Any]:
    ranking = list(final_rank.get("ranking", []) or [])
    if not ranking:
        raise ValueError("final_rank has no ranking rows")
    return dict(ranking[0])


def _route_teaching_task(seed: str) -> dict[str, Any] | None:
    match = _ROUTE_SEED_RE.search(str(seed or ""))
    if not match:
        return None
    market = match.group("market").upper()
    domain = match.group("domain").upper()
    slot = match.group("slot").upper()
    digest = sha256(f"{market}|{domain}|{slot}".encode("utf-8")).hexdigest()[:20]
    return {
        "task_id": f"mind-forge-route:{digest}",
        "execution_mode": "AI_TEACHING",
        "task_kind": "RESOLVE_ROUTE_GAP",
        "requires_paid_ai": True,
        "context": {
            "market_code": market,
            "project_domain": domain,
            "slot_id": slot,
        },
    }


def _attach_search_experiment_spec(
    *,
    result: dict[str, Any],
    final_rank_path: Path,
) -> dict[str, Any]:
    root = final_rank_path.parent
    creative_path = root / "result.json"
    fast_memory_path = root / "fast_learning_memory.json"
    if not creative_path.exists() or not fast_memory_path.exists():
        return result

    creative = json.loads(creative_path.read_text(encoding="utf-8"))
    seed = str(creative.get("seed") or "")
    task = _route_teaching_task(seed)
    if task is None:
        return result

    repo_root = Path(__file__).resolve().parents[1]
    src = repo_root / "src"
    if src.as_posix() not in sys.path:
        sys.path.insert(0, src.as_posix())
    from opportunity_engine.search_experiment_execution_bridge_v1 import (
        select_search_experiment_spec,
    )

    spec = select_search_experiment_spec(
        teaching_task=task,
        creative_result=creative,
        final_rank=json.loads(final_rank_path.read_text(encoding="utf-8")),
    )
    result["search_experiment_spec"] = spec
    result["search_experiment_bridge"] = (
        "READY_FOR_NEXT_CHECKPOINT"
        if spec.get("status") == "READY"
        else "NO_EXECUTABLE_SEARCH_SPEC"
    )
    if spec.get("status") != "READY":
        return result

    fast_memory = json.loads(fast_memory_path.read_text(encoding="utf-8"))
    if not isinstance(fast_memory, dict):
        raise ValueError("fast learning memory must be a JSON object")
    fast_memory["pending_search_experiment_spec"] = spec
    fast_memory["pending_search_experiment_fingerprint"] = spec[
        "experiment_fingerprint"
    ]
    fast_memory["pending_search_experiment_mode"] = "SHADOW_ONLY"
    fast_memory["auto_apply_to_production"] = False
    fast_memory_path.write_text(
        json.dumps(fast_memory, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def decide_and_design_experiment(
    final_rank: dict[str, Any],
    reasoning: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    top = _top_row(final_rank)
    idea_id = str(top["idea_id"])
    title = str(top.get("title") or idea_id)
    final_score = float(top.get("final_score", 0.0))
    evidence_signal = float(top.get("evidence_signal", 0.0))
    evidence_count = int(top.get("evidence_count", 0))
    conflict = bool(top.get("conflicting_evidence", False))

    relevance_gate_enforced = final_rank.get("evidence_relevance_gate") == "ENFORCED"
    if relevance_gate_enforced:
        evidence_status = str(top.get("evidence_status") or "INSUFFICIENT_EVIDENCE")
        relevant_evidence_count = int(top.get("relevant_evidence_count", 0))
    else:
        evidence_status = str(top.get("evidence_status") or "LEGACY_EVIDENCE")
        relevant_evidence_count = int(top.get("relevant_evidence_count", evidence_count))

    assessments = {str(row["idea_id"]): row for row in reasoning.get("assessments", []) or []}
    if idea_id not in assessments:
        raise ValueError("top-ranked idea missing from reasoning assessments")
    assessment = assessments[idea_id]
    critique = dict(assessment.get("critique", {}) or {})
    key_assumption = str(
        critique.get("key_assumption")
        or "The idea creates enough measurable value for a real user to take a concrete next step."
    ).strip()
    key_risk = str(
        critique.get("key_risk")
        or "Observed interest may not translate into real behavior."
    ).strip()

    observations = [
        dict(row)
        for row in evidence.get("observations", []) or []
        if str(row.get("idea_id")) == idea_id
    ]
    if len(observations) != evidence_count:
        raise ValueError("final_rank evidence_count disagrees with evidence observations")

    if final_score < 0.45 or evidence_signal < -0.35:
        verdict = "REJECT"
        reason = "Top idea is too weak after evidence to justify even a market experiment."
    elif relevance_gate_enforced and (
        evidence_status != "SUFFICIENT_RELEVANT_EVIDENCE" or relevant_evidence_count < 1
    ):
        verdict = "HOLD"
        reason = "Relevant evidence is insufficient; generic or off-domain evidence cannot authorize an experiment."
    elif (
        final_score >= 0.58
        and relevant_evidence_count >= 1
        and evidence_signal > 0
        and not conflict
    ):
        verdict = "EXPERIMENT"
        reason = "Top idea is strong enough after relevant evidence for a small reversible test, not full execution."
    else:
        verdict = "HOLD"
        reason = "Evidence is not yet strong or clean enough to justify a market experiment."

    experiment = None
    if verdict == "EXPERIMENT":
        experiment = {
            "experiment_type": "SMALLEST_REVERSIBLE_MARKET_TEST",
            "hypothesis": key_assumption,
            "risk_being_tested": key_risk,
            "duration_days": 7,
            "max_cash_commitment_nok": 1000,
            "target_responses": 5,
            "procedure": [
                "Create a one-page description of the proposed outcome without building the full service.",
                "Show it to five people or businesses that match the intended user profile.",
                "Ask each for one concrete commitment: pilot, meeting, referral, data access, or willingness to pay.",
                "Record refusals and objections verbatim; do not count compliments as demand.",
            ],
            "success_criteria": {
                "minimum_problem_confirmations": 3,
                "minimum_concrete_commitments": 2,
                "maximum_fatal_objections": 1,
            },
            "failure_rule": (
                "Reject or redesign the idea if fewer than 3 of 5 confirm the problem, fewer than 2 make a "
                "concrete commitment, or a regulatory/operational blocker makes the proposed outcome impractical."
            ),
            "next_state_on_success": "VALIDATED_FOR_NEXT_EXPERIMENT",
            "next_state_on_failure": "REJECT_OR_REWORK",
        }

    return {
        "status": "MIND_FORGE_V2_DECISION_EXPERIMENT_COMPLETE",
        "idea_id": idea_id,
        "title": title,
        "decision": verdict,
        "decision_reason": reason,
        "final_score": round(final_score, 4),
        "evidence_status": evidence_status,
        "evidence_signal": round(evidence_signal, 4),
        "evidence_count": evidence_count,
        "relevant_evidence_count": relevant_evidence_count,
        "evidence_relevance_gate_enforced": relevance_gate_enforced,
        "conflicting_evidence": conflict,
        "uses_mechanism_family_for_decision": False,
        "experiment": experiment,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("final_rank_json")
    parser.add_argument("reasoning_json")
    parser.add_argument("evidence_json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    final_rank_path = Path(args.final_rank_json)
    final_rank = json.loads(final_rank_path.read_text(encoding="utf-8"))
    reasoning = json.loads(Path(args.reasoning_json).read_text(encoding="utf-8"))
    evidence = json.loads(Path(args.evidence_json).read_text(encoding="utf-8"))
    result = decide_and_design_experiment(final_rank, reasoning, evidence)
    result = _attach_search_experiment_spec(
        result=result,
        final_rank_path=final_rank_path,
    )
    Path(args.output).write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "decision": result["decision"],
                "title": result["title"],
                "search_experiment_bridge": result.get("search_experiment_bridge"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
