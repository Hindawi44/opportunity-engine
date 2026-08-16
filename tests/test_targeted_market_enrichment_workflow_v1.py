from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/targeted-market-enrichment.yaml"


def test_targeted_workflow_runs_after_successful_daily_core_and_not_after_pr() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "name: Targeted Market Enrichment" in text
    assert "workflow_run:" in text
    assert "Multi-Market Daily Operator Checkpoint" in text
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "github.event.workflow_run.event != 'pull_request'" in text
    assert "workflow_dispatch:" in text


def test_gate_runs_before_any_paid_secret_is_exposed() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    gate = text.index("- name: Run zero-cost eligibility gate")
    paid = text.index("- name: Run paid targeted enrichment only for eligible hunt signals")
    openai_secret = text.index("OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}")
    brave_secret = text.index("BRAVE_SEARCH_API_KEY: ${{ secrets.BRAVE_SEARCH_API_KEY }}")

    assert gate < paid <= openai_secret
    assert gate < paid <= brave_secret
    assert "--gate-only" in text[gate:paid]
    assert "gate_uses_paid_api" in text


def test_targeted_workflow_reuses_upstream_artifact_and_never_rescans_markets() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'gh run download "$SOURCE_RUN_ID"' in text
    assert "--name multi-market-daily-operator-checkpoint" in text
    assert "domain-market-intelligence-brief.json" in text
    assert "run_targeted_market_enrichment.py" in text
    for forbidden in (
        "run_auksjonen_live_clothing.py",
        "run_market_clothing_inventory_discovery.py",
        "run_riegermann_active_discovery.py",
        "run_venta_active_discovery.py",
        "run_dpv_active_discovery.py",
        "build_domain_market_intelligence_feed.py",
    ):
        assert forbidden not in text


def test_paid_stage_is_bounded_and_read_only() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'OPENAI_HUNT_MAX_API_REQUESTS: "3"' in text
    assert 'OPENAI_HUNT_MAX_ESTIMATED_COST_USD: "0.16"' in text
    assert 'HUNT_FOLLOWUP_MAX_REQUESTS: "6"' in text
    assert "automatic_contact" in text
    assert "automatic_bid" in text
    assert "automatic_purchase" in text
    assert "automatic_payment" in text
    assert "contents: read" in text
    assert "actions: read" in text


def test_zero_eligibility_skips_openai_and_brave_followup_artifacts() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "SKIPPED_NO_ELIGIBLE_HUNT_SIGNALS" in text
    assert 'env.RUN_TARGETED_ENRICHMENT == \'true\'' in text
    assert 'openai-hunt-case-enrichment.json").exists()' in text
    assert 'hunt-case-targeted-followup.json").exists()' in text
