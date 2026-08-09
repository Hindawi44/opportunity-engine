from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

REMOVED = {
    "daily-opportunity-pipeline.yml",
    "scheduled-agent.yml",
    "discovery-v1-clothing-inventory.yml",
    "discovery-v1.1-live-search.yml",
    "discovery-v1.2-live-pilot.yml",
    "v3.2-continuous-opportunity-monitoring.yml",
    "v3.3-live-source-ingestion.yml",
    "riegermann-active-auctions-live.yaml",
    "venta-active-clothing-watch.yaml",
    "dpv-active-clothing-watch.yaml",
}

REQUIRED = {
    "multi-market-daily-operator-checkpoint.yaml",
    "tests.yml",
    "one-opportunity-commercial-analysis.yaml",
    "sweden-clothing-inventory-live.yaml",
    "germany-clothing-inventory-live.yaml",
}


def test_superseded_workflow_shells_are_removed() -> None:
    present = {path.name for path in WORKFLOWS.iterdir() if path.is_file()}
    assert REMOVED.isdisjoint(present)


def test_current_production_ci_and_manual_diagnostic_workflows_remain() -> None:
    present = {path.name for path in WORKFLOWS.iterdir() if path.is_file()}
    assert REQUIRED.issubset(present)
