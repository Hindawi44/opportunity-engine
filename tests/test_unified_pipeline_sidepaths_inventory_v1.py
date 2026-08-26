from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "config" / "unified_pipeline_sidepaths_v1.json"
WORKFLOWS = ROOT / ".github" / "workflows"


def _load() -> dict:
    return json.loads(INVENTORY.read_text(encoding="utf-8"))


def test_every_operator_visible_workflow_is_classified() -> None:
    inventory = _load()
    classified = {item["path"] for item in inventory["workflow_inventory"]}
    actual = {
        str(path.relative_to(ROOT)).replace("\\", "/")
        for path in WORKFLOWS.iterdir()
        if path.is_file() and path.suffix in {".yml", ".yaml"}
    }
    assert classified == actual


def test_exactly_one_governing_daily_pipeline_exists() -> None:
    inventory = _load()
    primary = [
        item
        for item in inventory["workflow_inventory"]
        if item["role"] == "PRIMARY_RUNTIME"
    ]
    assert len(primary) == 1
    assert primary[0]["path"] == ".github/workflows/multi-market-daily-operator-checkpoint.yaml"
    assert inventory["governing_pipeline"]["contract"] == "UNIFIED_SIX_MARKET_PIPELINE_V1"
    assert inventory["governing_pipeline"]["markets"] == ["NO", "SE", "DE", "FR", "IT", "NL"]


def test_country_diagnostics_are_archived_and_have_no_schedule_authority() -> None:
    inventory = _load()
    active_diagnostics = [
        item
        for item in inventory["workflow_inventory"]
        if item["role"] == "MANUAL_DIAGNOSTIC"
    ]
    assert active_diagnostics == []

    archived = inventory["archived_workflow_inventory"]
    assert {item["path"] for item in archived} == {
        "docs/workflow-archive/sweden-clothing-inventory-live.yaml",
        "docs/workflow-archive/germany-clothing-inventory-live.yaml",
    }
    for item in archived:
        text = (ROOT / item["path"]).read_text(encoding="utf-8")
        assert "workflow_dispatch:" in text
        assert "\n  schedule:" not in text
        assert "ARCHIVED_REDUNDANT_ENTRY_POINT" in item["decision"]


def test_side_families_cannot_create_parallel_decision_authority() -> None:
    inventory = _load()
    rules = inventory["migration_rules"]
    assert rules["single_governing_pipeline"] is True
    assert rules["source_or_country_may_own_parallel_final_decision"] is False
    assert rules["shadow_may_promote_directly_to_production"] is False
    assert rules["learning_requires_validation_gate"] is True
    assert rules["downstream_analysis_requires_verified_unified_input"] is True

    families = {item["family"]: item for item in inventory["architectural_families"]}
    assert families["SOURCE_SPECIFIC_ADAPTERS"]["role"] == "OPTIONAL_INGESTION_PROVIDER"
    assert families["SHADOW_AND_LABS"]["role"] == "EXPERIMENTAL_OBSERVATORY"
    assert families["LEARNING_QUERY_GAP_AND_FEEDBACK"]["role"] == "CONTROLLED_FEEDBACK_LOOP"
    assert families["COMMERCIAL_EVIDENCE_COST_AND_LOGISTICS"]["role"] == "DOWNSTREAM_ANALYSIS_CAPABILITY"


def test_inventory_preserves_read_only_safety_and_branch_cleanup_is_separate() -> None:
    inventory = _load()
    rules = inventory["migration_rules"]
    for key in (
        "automatic_contact",
        "automatic_bid",
        "automatic_reservation",
        "automatic_purchase",
        "automatic_payment",
    ):
        assert rules[key] is False

    hygiene = inventory["git_branch_hygiene"]
    assert hygiene["runtime_authority"] is False
    assert hygiene["delete_in_this_inventory"] is False
    assert hygiene["agent_branch_count"] >= 200
