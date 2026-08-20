from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
ARCHIVE = ROOT / "docs" / "workflow-archive"

ARCHIVED = {
    "v2.6.6-live-dry-run.yml",
    "v2.7.1-real-dataset-validation.yml",
    "v2.7.2.2-internal-score-audit.yml",
    "v2.7.2.3-score-engine-trace-audit.yml",
    "v2.7.2.4.1-research-candidate-audit.yml",
    "v2.7.2.4.2-bootstrap-pipeline-integration.yml",
    "v2.7.2.4.3-external-evidence-execution-audit.yml",
    "v2.7.2.4.4-brave-transport-response-audit.yml",
    "v2.7.2.4.5-brave-response-content-audit.yml",
    "v2.7.2.4.7-comparable-acceptance-audit.yml",
    "v2.7.2.5-external-financial-final-score.yml",
    "v2.8.1-external-market-comparables.yml",
    "v2.8.2-comparable-evidence-integration.yml",
    "v2.8.2b-comparable-evidence-e2e-acceptance.yml",
    "v2.9-auction-cost-logistics-e2e.yml",
    "v2.10-verified-financial-integration.yml",
    "v2.11-live-opportunity-validation.yml",
    "v30-multi-opportunity-ranking.yml",
    "v31-live-batch-validation.yml",
    "v3.4-persistent-opportunity-state.yml",
    "v3.5-opportunity-alert-review-queue.yml",
    "v3.6-multi-source-ingestion.yml",
    "v3.7-production-pilot.yml",
}

EXPECTED_LIVE = {
    "germany-clothing-inventory-live.yaml",
    "mind-forge-live-research-launcher.yaml",
    "multi-market-daily-operator-checkpoint.yaml",
    "one-opportunity-commercial-analysis.yaml",
    "sweden-clothing-inventory-live.yaml",
    "tests.yml",
}


def test_acceptance_workflows_are_archived_not_runnable() -> None:
    for name in ARCHIVED:
        assert not (WORKFLOWS / name).exists(), name
        assert (ARCHIVE / name).exists(), name


def test_actions_surface_matches_current_workflows() -> None:
    current = {
        path.name
        for path in WORKFLOWS.iterdir()
        if path.suffix in {".yml", ".yaml"}
    }
    assert current == EXPECTED_LIVE


def test_only_multi_market_checkpoint_owns_an_automatic_schedule() -> None:
    scheduled = []
    for path in WORKFLOWS.iterdir():
        if path.suffix not in {".yml", ".yaml"}:
            continue
        text = path.read_text(encoding="utf-8")
        # Ignore comments containing historical schedule examples.
        live_lines = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
        if any(line.strip() == "schedule:" for line in live_lines):
            scheduled.append(path.name)
    assert scheduled == ["multi-market-daily-operator-checkpoint.yaml"]
