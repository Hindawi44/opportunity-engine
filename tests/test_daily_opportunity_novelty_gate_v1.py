from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "reconcile_checkpoint_human_reviews.py"
OPPORTUNITY_ID = "https://example.test/active-lot"


def _module():
    spec = spec_from_file_location("reconcile_checkpoint_human_reviews", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _report(*, restored: bool = True, events: list[dict] | None = None, scope: str = "SINCE_PREVIOUS_SUCCESSFUL_CHECKPOINT") -> dict:
    return {
        "deduplicated_opportunities": [
            {
                "opportunity_identity": OPPORTUNITY_ID,
                "title": "Verified active clothing lot",
                "listing_status": "ACTIVE",
                "workflow_status": "ACTIVE_OPPORTUNITY",
                "analysis_eligible": True,
                "top5_eligible": True,
                "discovery_score": 90,
                "source_names": ["Auksjonen.no"],
            }
        ],
        "next_human_action": {
            "action": "REVIEW_ONE_OPPORTUNITY",
            "opportunity_identity": OPPORTUNITY_ID,
        },
        "lifecycle": {
            "persistence": {
                "comparison_scope": scope,
                "sources": [
                    {
                        "source_name": "Auksjonen.no",
                        "previous_state_restored": restored,
                    }
                ],
            },
            "transitions": {
                "current_run_events": list(events or []),
            },
        },
    }


def test_unchanged_active_opportunity_becomes_carryover_not_daily_selection() -> None:
    module = _module()
    report = _report(events=[])

    novelty = module._apply_daily_novelty_gate(report)
    view = module._daily_analysis_checkpoint_view(report, novelty)

    assert novelty["gate_applied"] is True
    assert novelty["novel_active_count"] == 0
    assert novelty["carryover_active_count"] == 1
    assert novelty["carryover_active_opportunity_ids"] == [OPPORTUNITY_ID]
    assert report["next_human_action"]["action"] == "NO_IMMEDIATE_ACTION"
    assert report["next_human_action"]["opportunity_identity"] is None
    assert view["deduplicated_opportunities"] == []


def test_real_lifecycle_change_allows_active_opportunity_once() -> None:
    module = _module()
    report = _report(
        events=[
            {
                "opportunity_id": OPPORTUNITY_ID,
                "source_name": "Auksjonen.no",
                "initial_snapshot": False,
                "from_workflow_status": "REQUIRES_VERIFICATION",
                "to_workflow_status": "ACTIVE_OPPORTUNITY",
            }
        ]
    )

    novelty = module._apply_daily_novelty_gate(report)
    view = module._daily_analysis_checkpoint_view(report, novelty)

    assert novelty["novel_active_count"] == 1
    assert novelty["carryover_active_count"] == 0
    assert report["next_human_action"]["action"] == "REVIEW_ONE_OPPORTUNITY"
    assert report["next_human_action"]["opportunity_identity"] == OPPORTUNITY_ID
    assert len(view["deduplicated_opportunities"]) == 1


def test_unrestored_initial_snapshot_is_not_treated_as_proven_new() -> None:
    module = _module()
    report = _report(
        restored=False,
        events=[
            {
                "opportunity_id": OPPORTUNITY_ID,
                "source_name": "Auksjonen.no",
                "initial_snapshot": True,
                "from_workflow_status": None,
                "to_workflow_status": "ACTIVE_OPPORTUNITY",
            }
        ],
    )

    novelty = module._apply_daily_novelty_gate(report)

    assert novelty["novel_active_count"] == 0
    assert novelty["carryover_active_count"] == 1
    assert report["next_human_action"]["action"] == "NO_IMMEDIATE_ACTION"


def test_first_checkpoint_baseline_keeps_existing_selection_behavior() -> None:
    module = _module()
    report = _report(scope="CURRENT_RUN_INITIALIZATION")

    novelty = module._apply_daily_novelty_gate(report)
    view = module._daily_analysis_checkpoint_view(report, novelty)

    assert novelty["gate_applied"] is False
    assert novelty["reason"] == "NO_PREVIOUS_SUCCESSFUL_CHECKPOINT_BASELINE"
    assert report["next_human_action"]["opportunity_identity"] == OPPORTUNITY_ID
    assert len(view["deduplicated_opportunities"]) == 1
