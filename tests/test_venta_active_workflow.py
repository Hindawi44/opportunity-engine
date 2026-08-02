import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "venta-active-clothing-watch.yaml"
CONTRACT = ROOT / "config" / "sources" / "de_venta_v1.json"
PLAN = ROOT / "config" / "source_expansion_plan.json"


def test_venta_watch_runs_daily_and_keeps_manual_dispatch() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "name: VENTA Active Clothing Watch" in workflow
    assert "schedule:" in workflow
    assert '- cron: "47 5 * * *"' in workflow
    assert "workflow_dispatch:" in workflow
    assert "pull_request:" in workflow
    assert "scripts/run_venta_active_discovery.py" in workflow


def test_scheduled_venta_watch_uses_bounded_persistent_defaults() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "github.event_name != 'workflow_dispatch' || inputs.persist_unified" in workflow
    assert "github.event.inputs.catalog_limit || '10'" in workflow
    assert "github.event.inputs.catalog_page_limit || '100'" in workflow
    assert "--persist-unified" in workflow
    assert "--database-url" in workflow
    assert "zero_clothing_results_are_valid" in workflow
    assert "promoted_bulk_lot_count" in workflow


def test_venta_remains_planned_until_live_clothing_validation() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    venta = next(
        source
        for market in plan["markets"]
        if market["market"] == "Germany"
        for source in market["sources"]
        if source["source"] == "VENTA Industrieversteigerungen"
    )

    assert contract["runtime_status"] == "PLANNED"
    assert contract["activation_requirements"]["production_ready"] is False
    assert venta["audit_status"] == "PLANNED"
    assert venta["production_ready"] is False
