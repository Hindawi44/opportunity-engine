from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


_ALLOWED_OUTCOMES = {"PASSED", "FAILED"}


def _validate_outcome(outcome: dict[str, Any], decision: dict[str, Any]) -> None:
    if decision.get("decision") != "EXPERIMENT":
        raise ValueError("learning outcome requires an EXPERIMENT decision")
    if str(outcome.get("idea_id")) != str(decision.get("idea_id")):
        raise ValueError("outcome idea_id does not match decision idea_id")
    if str(outcome.get("outcome")) not in _ALLOWED_OUTCOMES:
        raise ValueError("outcome must be PASSED or FAILED")
    for key in ("problem_confirmations", "concrete_commitments", "fatal_objections"):
        value = outcome.get(key)
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"{key} must be a non-negative integer")
    if int(outcome["problem_confirmations"]) > 5:
        raise ValueError("problem_confirmations cannot exceed target sample of 5")
    if int(outcome["concrete_commitments"]) > 5:
        raise ValueError("concrete_commitments cannot exceed target sample of 5")
    observations = list(outcome.get("observations", []) or [])
    if not observations:
        raise ValueError("real experiment learning requires at least one observation")
    if not all(str(item).strip() for item in observations):
        raise ValueError("experiment observations may not be blank")


def _derive_learning_code(outcome: dict[str, Any]) -> str:
    confirmations = int(outcome["problem_confirmations"])
    commitments = int(outcome["concrete_commitments"])
    blockers = int(outcome["fatal_objections"])
    passed = str(outcome["outcome"]) == "PASSED"

    if blockers >= 1:
        return "FATAL_BLOCKER_OBSERVED"
    if passed and confirmations >= 3 and commitments >= 2:
        return "DEMAND_SIGNAL_CONFIRMED"
    if confirmations < 3:
        return "PROBLEM_NOT_CONFIRMED"
    if commitments < 2:
        return "INTEREST_DID_NOT_CONVERT"
    return "OUTCOME_NEEDS_REVIEW"


def learn_from_experiment(
    decision: dict[str, Any],
    outcome: dict[str, Any],
    *,
    prior_memory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert one real V2 market experiment into observed memory and shadow search hints."""

    _validate_outcome(outcome, decision)
    prior_memory = dict(prior_memory or {})
    records = list(prior_memory.get("records", []) or [])
    idea_id = str(outcome["idea_id"])
    title = str(decision.get("title") or idea_id)
    code = _derive_learning_code(outcome)
    experiment_id = str(outcome.get("experiment_id") or f"exp-{idea_id}")

    if any(str(row.get("experiment_id")) == experiment_id for row in records):
        raise ValueError(f"duplicate experiment outcome: {experiment_id}")

    record = {
        "memory_id": f"v2-observed-{experiment_id}",
        "experiment_id": experiment_id,
        "idea_id": idea_id,
        "title": title,
        "truth_status": "OBSERVED",
        "learning_code": code,
        "outcome": str(outcome["outcome"]),
        "problem_confirmations": int(outcome["problem_confirmations"]),
        "concrete_commitments": int(outcome["concrete_commitments"]),
        "fatal_objections": int(outcome["fatal_objections"]),
        "observations": [str(item).strip() for item in outcome.get("observations", [])],
        "lesson": str(outcome.get("lesson") or "").strip(),
        "source": "REAL_MARKET_EXPERIMENT",
        "auto_verified": False,
    }
    records.append(record)

    independent_matches = sum(
        1 for row in records if row.get("learning_code") == code and row.get("truth_status") == "OBSERVED"
    )
    pattern_state = "ELIGIBLE_FOR_HUMAN_REVIEW" if independent_matches >= 2 else "SHADOW_ONLY"

    if code == "DEMAND_SIGNAL_CONFIRMED":
        hint = {
            "action": "PRIORITIZE_SIMILAR_PAIN_SIGNALS",
            "search_question": f"Where else in Norway do buyers show the same concrete pain behind {title}?",
            "required_evidence": "Look for behavioral demand, transactions, requests, or operational burden; do not count generic interest.",
        }
    elif code == "PROBLEM_NOT_CONFIRMED":
        hint = {
            "action": "FALSIFY_PROBLEM_EARLIER",
            "search_question": f"Is the underlying problem behind {title} actually frequent and costly enough in Norway?",
            "required_evidence": "Require direct signs of recurring pain before generating close variants of this idea.",
        }
    elif code == "INTEREST_DID_NOT_CONVERT":
        hint = {
            "action": "TEST_WILLINGNESS_BEFORE_IDEA_EXPANSION",
            "search_question": f"Do target users take a costly or concrete action to solve the problem behind {title}?",
            "required_evidence": "Prefer payment, pilots, referrals, data access, procurement activity, or switching behavior over compliments.",
        }
    elif code == "FATAL_BLOCKER_OBSERVED":
        hint = {
            "action": "CHECK_BLOCKER_BEFORE_GENERATION",
            "search_question": f"Does the observed blocker make variants of {title} impractical or require a different delivery model?",
            "required_evidence": "Resolve the blocker before promoting similar ideas.",
        }
    else:
        hint = {
            "action": "GATHER_MORE_DISCRIMINATING_EVIDENCE",
            "search_question": f"What evidence would clearly separate demand from noise for {title}?",
            "required_evidence": "Seek evidence that can change the decision, not background information.",
        }

    return {
        "status": "MIND_FORGE_V2_LEARNING_MEMORY_COMPLETE",
        "records": records,
        "latest_learning_code": code,
        "pattern_observation_count": independent_matches,
        "pattern_activation_state": pattern_state,
        "auto_apply_to_production": False,
        "next_cycle_search_adjustments": [
            {
                **hint,
                "origin_memory_id": record["memory_id"],
                "mode": "SHADOW_HINT",
                "may_change_search_priority": True,
                "may_auto_reject_ideas": False,
            }
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("decision_json")
    parser.add_argument("outcome_json")
    parser.add_argument("--prior-memory")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    decision = json.loads(Path(args.decision_json).read_text(encoding="utf-8"))
    outcome = json.loads(Path(args.outcome_json).read_text(encoding="utf-8"))
    prior = None
    if args.prior_memory:
        prior = json.loads(Path(args.prior_memory).read_text(encoding="utf-8"))
    result = learn_from_experiment(decision, outcome, prior_memory=prior)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "learning_code": result["latest_learning_code"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
