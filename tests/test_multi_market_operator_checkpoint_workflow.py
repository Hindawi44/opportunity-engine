from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"
RECONCILE = ROOT / "scripts/reconcile_checkpoint_human_reviews.py"
BUILD_INTELLIGENCE = ROOT / "scripts/build_domain_market_intelligence_feed.py"


def test_checkpoint_workflow_is_daily_and_read_only() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "name: Multi-Market Daily Operator Checkpoint" in text
    assert "workflow_dispatch:" in text
    assert "schedule:" in text
    assert 'cron: "17 5 * * *"' in text
    assert "operator-read-only-checkpoint:" in text
    assert "github.event_name == 'workflow_dispatch' || github.event_name == 'schedule'" in text
    assert "permissions:\n  contents: read\n  actions: read" in text
    assert "automatic_purchase" in text
    assert "automatic_payment" in text
    assert "run_multi_market_daily_operator_checkpoint.py" in text


def test_checkpoint_workflow_covers_only_completed_markets() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert '"market_code": "NO"' in text
    assert '"market_code": "SE"' in text
    assert '"market_code": "DE"' in text
    assert '"market_code": "DK"' not in text
    assert "run_auksjonen_live_clothing.py" in text
    assert "run_finn_email_intake.py" in text
    assert "--market SE" in text
    assert "--source blinto" in text
    assert "--source klaravik" in text
    assert "--source psauction" in text
    assert '"source_name": "Blinto"' in text
    assert '"source_name": "Klaravik"' in text
    assert '"source_name": "PS Auction"' in text
    assert '"artifact_dir": "artifacts/multi-market-inputs/se-blinto"' in text
    assert '"artifact_dir": "artifacts/multi-market-inputs/se-klaravik"' in text
    assert '"artifact_dir": "artifacts/multi-market-inputs/se-psauction"' in text
    assert "run_riegermann_active_discovery.py" in text
    assert "run_venta_active_discovery.py" in text
    assert "run_dpv_active_discovery.py" in text


def test_checkpoint_reads_finn_gmail_after_auksjonen() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    auksjonen = text.index("- name: Run Norway Auksjonen public clothing path")
    finn = text.index("- name: Read FINN saved-search alerts from Gmail")
    sweden = text.index("- name: Run Sweden Blinto bounded pilot")

    assert auksjonen < finn < sweden
    assert "GMAIL_CLIENT_ID: ${{ secrets.GMAIL_CLIENT_ID }}" in text
    assert "GMAIL_CLIENT_SECRET: ${{ secrets.GMAIL_CLIENT_SECRET }}" in text
    assert "GMAIL_REFRESH_TOKEN: ${{ secrets.GMAIL_REFRESH_TOKEN }}" in text
    assert "--gmail-api" in text
    assert "--max-messages 20" in text
    assert 'from:agent@finn.no subject:"Nye annonser:" newer_than:7d' in text
    assert "--auksjonen-report" in text
    assert '"source_name": "FINN saved-search email"' in text
    assert "all six bounded source paths" in text


def test_sweden_daily_checkpoint_runs_three_direct_source_packs_before_germany() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    blinto = text.index("- name: Run Sweden Blinto bounded pilot")
    klaravik = text.index("- name: Run Sweden Klaravik bounded direct scan")
    psauction = text.index("- name: Run Sweden PS Auction bounded direct scan")
    germany = text.index("- name: Run active Riegermann discovery")

    assert blinto < klaravik < psauction < germany
    assert "all nine bounded source paths" in text
    assert '!= 9' in text
    assert '"Klaravik" not in source_by_name' in text
    assert '"PS Auction" not in source_by_name' in text


def test_checkpoint_workflow_preserves_one_human_action() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'summary.count("الإجراء البشري الوحيد:") != 1' in text
    assert "contact sellers" not in text.lower()
    assert "git push" not in text


def test_checkpoint_restores_state_before_sources_and_enriches_after_build() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    restore = text.index("- name: Restore previous lifecycle SQLite state")
    first_source = text.index("- name: Run Norway Auksjonen public clothing path")
    finn_source = text.index("- name: Read FINN saved-search alerts from Gmail")
    build = text.index("- name: Build the three-market operator checkpoint")
    enrich = text.index("- name: Enrich checkpoint with lifecycle state and transitions")
    reconcile = text.index("- name: Reconcile persisted human review outcomes")

    assert restore < first_source < finn_source < build < enrich < reconcile
    assert "previous-state-restore.json" in text
    assert "SINCE_PREVIOUS_SUCCESSFUL_CHECKPOINT" in text
    assert "CURRENT_RUN_INITIALIZATION" in text
    assert "دورة الحياة:" in text
    assert "استمرارية SQLite:" in text


def test_checkpoint_persists_and_validates_auksjonen_lifecycle() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    start = text.index("Run Norway Auksjonen public clothing path")
    end = text.index("Read FINN saved-search alerts from Gmail", start)
    norway_step = text[start:end]

    assert "--persist-unified" in norway_step
    assert (
        'sqlite:///$INPUT_ROOT/no-auksjonen/opportunity_engine.db' in norway_step
    )
    assert "Auksjonen unified SQLite persistence did not succeed" in text
    assert "Auksjonen lifecycle event storage is not enabled" in text


def test_checkpoint_supports_bounded_explicit_human_review() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "human_review_opportunity_id:" in text
    assert "human_review_outcome:" in text
    for outcome in (
        "NONE",
        "VERIFIED",
        "NEEDS_MORE_INFORMATION",
        "REJECTED",
        "CLOSED",
    ):
        assert f"- {outcome}" in text
    apply_step = text.index("- name: Apply optional human review outcome")
    manifest_step = text.index("- name: Write checkpoint input manifest")
    assert apply_step < manifest_step
    assert "scripts/apply_human_review_outcome.py" in text
    assert "scripts/reconcile_checkpoint_human_reviews.py" in text
    assert "human-review-outcome.json" in text


def test_reconciliation_builds_one_daily_analysis_artifact() -> None:
    text = RECONCILE.read_text(encoding="utf-8")
    assert "build_daily_analysis" in text
    assert "one-opportunity-daily-analysis.json" in text
    assert "one-opportunity-daily-analysis.txt" in text
    assert "render_daily_analysis" in text


def test_sweden_identity_bridge_runs_before_official_status_check() -> None:
    text = BUILD_INTELLIGENCE.read_text(encoding="utf-8")
    bridge = text.index("resolve_sweden_artifact_company_identities")
    official = text.index("collect_manifest_official_signals_with_sweden_status")

    assert bridge < official
    assert "sweden-organisation-discovery-bridge.json" in text


def test_brave_market_signal_radar_runs_before_official_status_check() -> None:
    text = BUILD_INTELLIGENCE.read_text(encoding="utf-8")
    radar = text.index("collect_manifest_brave_market_signals")
    official = text.index("collect_manifest_official_signals_with_sweden_status")

    assert radar < official
    assert "brave-market-signal-radar.json" in text
    assert '"market_coverage": ["NO", "SE", "DE"]' in text
