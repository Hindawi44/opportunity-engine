from __future__ import annotations

from scripts.reconcile_checkpoint_human_reviews import (
    _merge_current_review_transition,
)


def _report() -> dict:
    return {
        "deduplicated_opportunities": [
            {
                "opportunity_identity": "opportunity-1",
                "market_code": "NO",
                "source_names": ["Auksjonen.no"],
            }
        ],
        "lifecycle": {
            "persistence": {
                "sources": [
                    {
                        "market_code": "NO",
                        "source_name": "Auksjonen.no",
                        "lifecycle_events_created_this_run": 0,
                    }
                ]
            },
            "transitions": {
                "events_created_this_run": 0,
                "initial_snapshots_created_this_run": 0,
                "transitions_created_this_run": 0,
                "promoted_count": 0,
                "closed_historical_or_rejected_count": 0,
                "current_run_events": [],
            },
        },
    }


def _verified_payload() -> dict:
    return {
        "lifecycle_transition_created": True,
        "lifecycle_transition": {
            "opportunity_id": "opportunity-1",
            "from_listing_status": "ACTIVE",
            "to_listing_status": "ACTIVE",
            "from_evaluation_status": "REQUIRES_VERIFICATION",
            "to_evaluation_status": "NOT_EVALUATED",
            "from_workflow_status": "REQUIRES_VERIFICATION",
            "to_workflow_status": "ACTIVE_OPPORTUNITY",
            "from_reason_code": "MISSING_REQUIRED_VERIFICATION",
            "to_reason_code": "HUMAN_REVIEW_VERIFIED",
            "source_ref": "github-actions:123",
            "changed_at": "2026-08-03 10:41:00+00:00",
        },
    }


def test_verified_review_is_reported_as_one_promotion() -> None:
    report = _report()
    _merge_current_review_transition(report, _verified_payload())

    transitions = report["lifecycle"]["transitions"]
    assert transitions["events_created_this_run"] == 1
    assert transitions["transitions_created_this_run"] == 1
    assert transitions["promoted_count"] == 1
    assert transitions["closed_historical_or_rejected_count"] == 0
    assert len(transitions["current_run_events"]) == 1
    assert report["lifecycle"]["persistence"]["sources"][0][
        "lifecycle_events_created_this_run"
    ] == 1


def test_current_review_transition_merge_is_idempotent() -> None:
    report = _report()
    payload = _verified_payload()
    _merge_current_review_transition(report, payload)
    _merge_current_review_transition(report, payload)

    transitions = report["lifecycle"]["transitions"]
    assert transitions["events_created_this_run"] == 1
    assert transitions["transitions_created_this_run"] == 1
    assert transitions["promoted_count"] == 1
    assert len(transitions["current_run_events"]) == 1


def test_no_transition_is_added_when_review_did_not_change_state() -> None:
    report = _report()
    _merge_current_review_transition(
        report,
        {"lifecycle_transition_created": False},
    )
    assert report["lifecycle"]["transitions"]["events_created_this_run"] == 0
