from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _top_row(final_rank: dict[str, Any]) -> dict[str, Any]:
    ranking = list(final_rank.get("ranking", []) or [])
    if not ranking:
        raise ValueError("final_rank has no ranking rows")
    return dict(ranking[0])


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

    final_rank = json.loads(Path(args.final_rank_json).read_text(encoding="utf-8"))
    reasoning = json.loads(Path(args.reasoning_json).read_text(encoding="utf-8"))
    evidence = json.loads(Path(args.evidence_json).read_text(encoding="utf-8"))
    result = decide_and_design_experiment(final_rank, reasoning, evidence)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "decision": result["decision"], "title": result["title"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
