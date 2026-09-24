"""Regression guard: restore the original Norway sources, not a replacement engine."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"
ARCHIVE = ROOT / "docs/archive/legacy-six-market-checkpoint-20260919.yaml.txt"
ORIGINAL = ROOT / "scripts/run_cross_source_clothing_verification.py"


def test_original_norway_sources_reconnected_without_replacing_code():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert ORIGINAL.is_file()
    original = ORIGINAL.read_text(encoding="utf-8")
    for source in ("CrossSourceClothingSaleVerifier", "VareauksjonenPublicCollector", "AuksjonerNoPublicCollector"):
        assert source in original
    assert "norway-existing-engine:" in text
    job = text.split("  norway-existing-engine:\n", 1)[1].split("  norway-insolvency-source-pilot:\n", 1)[0]
    assert "python scripts/run_cross_source_clothing_verification.py" in job
    for option in ("--lookback-days 60", "--max-bankruptcy-leads 12", "--max-detail-pages 3", "--max-vareauksjonen-details 3", "--max-auksjoner-no-auctions 8"):
        assert option in job
    assert "norway-original-cross-source-evidence" in job
    assert "if: always()" in job
    assert "--persist-unified" not in job
    assert "--database-url" not in job
    assert "BRAVE_SEARCH_API_KEY" not in job
    assert "EXA_API_KEY" not in job
    assert "OPENAI_API_KEY" not in job
    assert "scripts/run_norway_insolvency_sale_links.py" not in job


def test_original_norway_paid_and_gmail_paths_are_restored_without_foreign_execution():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert ARCHIVE.is_file()
    old = ARCHIVE.read_text(encoding="utf-8")
    for original_stage in (
        "Run Exa Exact-Lot NO checkpoint source",
        "Run Norway Auksjonen public clothing path",
        "Read FINN saved-search alerts from Gmail",
        "Run Norway bounded cross-source verification",
        "Restore previous lifecycle SQLite state",
    ):
        assert original_stage in old

    active = text.split("  norway-all-assets:\n", 1)[1].split("  norway-existing-engine:\n", 1)[0]
    assert "run_exa_exact_lot_checkpoint.py" in active
    assert "--market NO" in active
    assert "run_finn_email_intake.py" in active
    assert "--gmail-api" in active
    assert "run_norway_openai_search_intelligence.py" in active
    assert "restore_norway_review_state.py" in active
    assert "restore_previous_checkpoint_state.py" not in text

    for foreign in ("--market SE", "--market DE", "--market FR", "--market IT", "--market NL"):
        assert foreign not in text
    for destructive in ("git clean", "rm -rf artifacts/multi-market-inputs", "DROP TABLE"):
        assert destructive not in text
    assert "  schedule:" in text
    assert "  workflow_dispatch:" in text
    assert "  pull_request:" in text
    assert "norway-insolvency-source-pilot:" in text
