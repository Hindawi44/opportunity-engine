from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path("scripts/mind_forge_scheduled_teaching_selector.py")
WORKFLOW = Path(".github/workflows/mind-forge-live-research-launcher.yaml")


def _load_module():
    spec = importlib.util.spec_from_file_location("scheduled_teaching_selector", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _queue(*tasks):
    return {
        "schema_version": "ai-teaching-gate-1.0",
        "status": "SUCCESS",
        "project_domain_gate_enforced": True,
        "automatic_query_activation": False,
        "automatic_provider_activation": False,
        "automatic_source_promotion": False,
        "automatic_code_change": False,
        "production_query_mutation": False,
        "production_mutation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
        "ai_teaching_tasks": list(tasks),
    }


def _task(task_id="task-a", priority=90, *, evidence_count=0, domain="CLOTHING_INVENTORY"):
    return {
        "task_id": task_id,
        "execution_mode": "AI_TEACHING",
        "task_kind": "DISCOVER_NEW_ROUTE",
        "priority": priority,
        "requires_paid_ai": True,
        "reason": "Novel unresolved route",
        "mind_forge_seed": f"Teach route {task_id}",
        "context": {
            "market_code": "NO",
            "project_domain": domain,
            "evidence_observation_count": evidence_count,
        },
    }


def test_scheduled_selector_runs_only_highest_priority_unseen_task():
    module = _load_module()
    result = module.select_scheduled_teaching(
        queue=_queue(_task("low", 70), _task("high", 100)),
        state={},
    )

    assert result["should_run"] is True
    assert result["max_paid_ai_tasks_this_checkpoint"] == 1
    assert result["selected_task"]["task_id"] == "high"
    assert result["eligible_unseen_task_count"] == 2


def test_completed_unchanged_task_is_skipped_and_next_task_is_selected():
    module = _load_module()
    first = module.select_scheduled_teaching(queue=_queue(_task("a", 100), _task("b", 90)))
    state = module.record_success(
        state={},
        selection=first,
        run_id="mind-forge-run-1",
        source_run_id="checkpoint-1",
    )

    second = module.select_scheduled_teaching(
        queue=_queue(_task("a", 100), _task("b", 90)),
        state=state,
    )
    assert second["selected_task"]["task_id"] == "b"


def test_changed_task_context_gets_new_fingerprint_and_can_be_relearned():
    module = _load_module()
    first = module.select_scheduled_teaching(queue=_queue(_task("a", 100, evidence_count=0)))
    state = module.record_success(
        state={},
        selection=first,
        run_id="mind-forge-run-1",
        source_run_id="checkpoint-1",
    )

    changed = module.select_scheduled_teaching(
        queue=_queue(_task("a", 100, evidence_count=2)),
        state=state,
    )
    assert changed["should_run"] is True
    assert changed["selected_task"]["task_id"] == "a"


def test_no_unseen_ai_task_means_zero_paid_run():
    module = _load_module()
    first = module.select_scheduled_teaching(queue=_queue(_task("a")))
    state = module.record_success(
        state={},
        selection=first,
        run_id="mind-forge-run-1",
        source_run_id="checkpoint-1",
    )
    result = module.select_scheduled_teaching(queue=_queue(_task("a")), state=state)

    assert result["should_run"] is False
    assert result["status"] == "NO_NEW_AI_TEACHING_TASK"


def test_out_of_domain_scheduled_task_is_rejected():
    module = _load_module()
    with pytest.raises(ValueError, match="escaped project domain"):
        module.select_scheduled_teaching(queue=_queue(_task(domain="CARS")))


def test_manual_seed_remains_supported():
    module = _load_module()
    result = module.manual_selection("manual idea")
    assert result["scheduled"] is False
    assert result["should_run"] is True
    assert result["selected_task"]["mind_forge_seed"] == "manual idea"


def test_launcher_is_wired_to_successful_scheduled_daily_checkpoint():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_run:" in text
    assert 'workflows: ["Multi-Market Daily Operator Checkpoint"]' in text
    assert "github.event.workflow_run.event == 'schedule'" in text
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "mind_forge_scheduled_teaching_selector.py" in text
    assert "ai-teaching-queue-v1.json" in text
    assert "max_paid_ai_tasks_this_checkpoint" in SCRIPT.read_text(encoding="utf-8")
    assert "actions/download-artifact@v4" in text


def test_manual_paid_authorization_is_still_required_for_ad_hoc_runs():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'default: "NO"' in text
    assert "inputs.confirm_paid_live_research == 'YES'" in text
    assert "github.event_name == 'workflow_dispatch'" in text
