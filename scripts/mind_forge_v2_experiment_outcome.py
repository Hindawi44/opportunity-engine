from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXPECTED_IDEA_ID = "idea-open-f68386fa98a3ff10"
EXPECTED_TITLE = "Quote-to-Job Standardizer"


def finalize_experiment_outcome(form: dict[str, Any]) -> dict[str, Any]:
    if form.get("status") != "COMPLETE":
        raise ValueError("experiment form must be marked COMPLETE before finalization")
    if str(form.get("idea_id")) != EXPECTED_IDEA_ID:
        raise ValueError("experiment form idea_id does not match Quote-to-Job Standardizer")
    if str(form.get("title")) != EXPECTED_TITLE:
        raise ValueError("experiment form title does not match Quote-to-Job Standardizer")

    experiment_id = str(form.get("experiment_id") or "").strip()
    if not experiment_id:
        raise ValueError("experiment_id is required")

    contacts = list(form.get("contacts", []) or [])
    if len(contacts) != 5:
        raise ValueError("experiment requires exactly five completed contacts")

    confirmations = 0
    commitments = 0
    blockers = 0
    observations: list[str] = []
    seen_ids: set[str] = set()

    for row in contacts:
        contact_id = str(row.get("contact_id") or "").strip()
        business_type = str(row.get("business_type") or "").strip()
        notes = str(row.get("notes") or "").strip()
        if not contact_id or not business_type or not notes:
            raise ValueError("each contact requires contact_id, business_type, and notes")
        if contact_id in seen_ids:
            raise ValueError(f"duplicate contact_id: {contact_id}")
        seen_ids.add(contact_id)

        for key in ("problem_confirmed", "concrete_commitment", "fatal_objection"):
            if not isinstance(row.get(key), bool):
                raise ValueError(f"{key} must be boolean for contact {contact_id}")

        confirmations += int(row["problem_confirmed"])
        commitments += int(row["concrete_commitment"])
        blockers += int(row["fatal_objection"])
        observations.append(f"{business_type}: {notes}")

    passed = confirmations >= 3 and commitments >= 2 and blockers == 0
    lesson = str(form.get("lesson") or "").strip()
    if not lesson:
        raise ValueError("lesson is required before finalization")

    return {
        "experiment_id": experiment_id,
        "idea_id": EXPECTED_IDEA_ID,
        "outcome": "PASSED" if passed else "FAILED",
        "problem_confirmations": confirmations,
        "concrete_commitments": commitments,
        "fatal_objections": blockers,
        "observations": observations,
        "lesson": lesson,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("form_json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    form = json.loads(Path(args.form_json).read_text(encoding="utf-8"))
    result = finalize_experiment_outcome(form)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": "MIND_FORGE_V2_EXPERIMENT_OUTCOME_FINALIZED",
        "outcome": result["outcome"],
        "problem_confirmations": result["problem_confirmations"],
        "concrete_commitments": result["concrete_commitments"],
        "fatal_objections": result["fatal_objections"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
