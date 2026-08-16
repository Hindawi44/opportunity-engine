from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/one-opportunity-commercial-analysis.yaml"
WORKFLOW_DIR = ROOT / ".github/workflows"


def test_targeted_stage_reuses_existing_workflow_inventory() -> None:
    active = sorted(path.name for path in WORKFLOW_DIR.iterdir() if path.suffix in {".yml", ".yaml"})
    assert len(active) == 5
    assert "multi-market-daily-operator-checkpoint.yaml" in active
    assert "one-opportunity-commercial-analysis.yaml" in active
    assert not (WORKFLOW_DIR / "targeted-market-enrichment.yaml").exists()


def test_targeted_stage_runs_after_successful_daily_core_and_not_after_pr() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "name: One Opportunity Commercial Analysis" in text
    assert "workflow_run:" in text
    assert "Multi-Market Daily Operator Checkpoint" in text
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "github.event.workflow_run.event != 'pull_request'" in text
    assert "targeted-read-only-enrichment:" in text
    assert "workflow_dispatch:" in text


def test_manual_commercial_analysis_remains_manual_only() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    marker = "manual-read-only-commercial-analysis:"
    start = text.index(marker)
    manual_job = text[start:]
    assert "if: ${{ github.event_name == 'workflow_dispatch' }}" in manual_job
    assert "Apply explicit commercial inputs and run conservative decision engine" in manual_job
    assert "automatic_purchase" in manual_job


def test_gate_runs_before_any_paid_secret_is_exposed() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    gate = text.index("- name: Run zero-cost eligibility gate")
    paid = text.index("- name: Run paid targeted enrichment only for eligible hunt signals")
    openai_secret = text.index("OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}")
    brave_secret = text.index("BRAVE_SEARCH_API_KEY: ${{ secrets.BRAVE_SEARCH_API_KEY }}")

    assert gate < paid <= openai_secret
    assert gate < paid <= brave_secret
    assert "id: gate" in text[gate:paid]
    assert "--gate-only" in text[gate:paid]
    assert 'steps.gate.outputs.should_run == \'true\'' in text
    assert 'os.environ["GITHUB_OUTPUT"]' in text[gate:paid]
    assert "gate_uses_paid_api" in text


def test_targeted_stage_reuses_upstream_artifact_and_never_rescans_markets() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'gh run download "$SOURCE_RUN_ID"' in text
    assert "--name multi-market-daily-operator-checkpoint" in text
    assert "domain-market-intelligence-brief.json" in text
    assert "run_targeted_market_enrichment.py" in text
    targeted_start = text.index("targeted-read-only-enrichment:")
    manual_start = text.index("manual-read-only-commercial-analysis:")
    targeted_job = text[targeted_start:manual_start]
    for forbidden in (
        "run_auksjonen_live_clothing.py",
        "run_market_clothing_inventory_discovery.py",
        "run_riegermann_active_discovery.py",
        "run_venta_active_discovery.py",
        "run_dpv_active_discovery.py",
        "build_domain_market_intelligence_feed.py",
    ):
        assert forbidden not in targeted_job


def test_paid_stage_is_bounded_read_only_and_fails_closed_on_missing_keys() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'OPENAI_HUNT_MAX_API_REQUESTS: "3"' in text
    assert 'OPENAI_HUNT_MAX_ESTIMATED_COST_USD: "0.16"' in text
    assert 'HUNT_FOLLOWUP_MAX_REQUESTS: "6"' in text
    assert 'summary.get("openai_hunt_status") == "SKIPPED_NO_API_KEY"' in text
    assert 'summary.get("targeted_followup_status") == "SKIPPED_NO_BRAVE_KEY"' in text
    assert 'float(summary.get("openai_estimated_cost_usd") or 0.0) > 0.16' in text
    assert "automatic_contact" in text
    assert "automatic_bid" in text
    assert "automatic_purchase" in text
    assert "automatic_payment" in text
    assert "contents: read" in text
    assert "actions: read" in text


def test_zero_eligibility_skips_openai_and_brave_followup_artifacts() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "SKIPPED_NO_ELIGIBLE_HUNT_SIGNALS" in text
    assert 'steps.gate.outputs.should_run == \'true\'' in text
    assert 'openai-hunt-case-enrichment.json").exists()' in text
    assert 'hunt-case-targeted-followup.json").exists()' in text
