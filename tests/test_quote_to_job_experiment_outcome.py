import pytest

from scripts.mind_forge_v2_experiment_outcome import finalize_experiment_outcome


IDEA_ID = "idea-open-f68386fa98a3ff10"


def _form():
    return {
        "status": "COMPLETE",
        "experiment_id": "quote-to-job-pilot-001",
        "idea_id": IDEA_ID,
        "title": "Quote-to-Job Standardizer",
        "contacts": [
            {"contact_id": "c1", "business_type": "plumber", "problem_confirmed": True, "concrete_commitment": True, "fatal_objection": False, "notes": "Sent a real anonymized request for a pilot."},
            {"contact_id": "c2", "business_type": "electrician", "problem_confirmed": True, "concrete_commitment": True, "fatal_objection": False, "notes": "Agreed to test the structured quote."},
            {"contact_id": "c3", "business_type": "painter", "problem_confirmed": True, "concrete_commitment": False, "fatal_objection": False, "notes": "Confirmed scope ambiguity but made no commitment."},
            {"contact_id": "c4", "business_type": "car_repair", "problem_confirmed": False, "concrete_commitment": False, "fatal_objection": False, "notes": "Does not see this as a recurring problem."},
            {"contact_id": "c5", "business_type": "cleaning", "problem_confirmed": False, "concrete_commitment": False, "fatal_objection": False, "notes": "Current process is sufficient."},
        ],
        "lesson": "Two businesses committed to a real pilot after confirming the problem.",
    }


def test_successful_pilot_emits_learning_memory_compatible_passed_outcome():
    result = finalize_experiment_outcome(_form())
    assert result == {
        "experiment_id": "quote-to-job-pilot-001",
        "idea_id": IDEA_ID,
        "outcome": "PASSED",
        "problem_confirmations": 3,
        "concrete_commitments": 2,
        "fatal_objections": 0,
        "observations": [
            "plumber: Sent a real anonymized request for a pilot.",
            "electrician: Agreed to test the structured quote.",
            "painter: Confirmed scope ambiguity but made no commitment.",
            "car_repair: Does not see this as a recurring problem.",
            "cleaning: Current process is sufficient.",
        ],
        "lesson": "Two businesses committed to a real pilot after confirming the problem.",
    }


def test_interest_without_commitments_is_failed():
    form = _form()
    for row in form["contacts"]:
        row["problem_confirmed"] = True
        row["concrete_commitment"] = False
    result = finalize_experiment_outcome(form)
    assert result["outcome"] == "FAILED"
    assert result["problem_confirmations"] == 5
    assert result["concrete_commitments"] == 0


def test_fatal_objection_forces_failure():
    form = _form()
    form["contacts"][0]["fatal_objection"] = True
    result = finalize_experiment_outcome(form)
    assert result["outcome"] == "FAILED"
    assert result["fatal_objections"] == 1


def test_requires_exactly_five_completed_contacts():
    form = _form()
    form["contacts"].pop()
    with pytest.raises(ValueError, match="exactly five"):
        finalize_experiment_outcome(form)


def test_pending_form_cannot_be_finalized():
    form = _form()
    form["status"] = "PENDING"
    with pytest.raises(ValueError, match="COMPLETE"):
        finalize_experiment_outcome(form)
