"""Contract for restoring existing NO all-asset listings without rebuilding search."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"
ARCHIVE = ROOT / "docs/archive/legacy-six-market-checkpoint-20260919.yaml.txt"
DIRECT = ROOT / "scripts/run_norway_direct_sales.py"
CROSS = ROOT / "scripts/run_cross_source_clothing_verification.py"


def test_original_all_asset_runner_reconnected_and_bounded():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert DIRECT.is_file() and CROSS.is_file() and ARCHIVE.is_file()
    job = text.split("  norway-all-assets:\n", 1)[1].split("  norway-existing-engine:\n", 1)[0]
    assert "needs: norway-contract" in job
    assert "if: ${{ github.event_name == 'pull_request' }}" in job
    assert "python scripts/run_norway_direct_sales.py" in job
    assert "--max-pages 2" in job and "--max-cards 10" in job
    assert "norway-existing-all-assets-evidence" in job
    assert "if: always()" in job
    assert "--persist-unified" not in job and "--database-url" not in job
    assert "run_norway_insolvency_sale_links.py" not in job
    assert "market SE" not in job and "market DE" not in job


def test_no_duplicate_insolvency_run_or_paid_foreign_cron():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "  schedule:" not in workflow
    assert "  workflow_dispatch:" not in workflow
    assert "  norway-insolvency-source-pilot:\n    # The experimental replacement yielded no qualified links in bounded live\n    # samples. Preserve its code/history, but stop duplicate network work.\n    if: ${{ false }}" in workflow
    for token in (
        "BRAVE_SEARCH_API_KEY:", "EXA_API_KEY:", "OPENAI_API_KEY:",
        "GMAIL_REFRESH_TOKEN:", "--market SE", "--market DE", "--market FR",
        "--persist-unified", "--database-url", "actions: write", "contents: write",
    ):
        assert token not in workflow
    for old_stage in (
        "Run Exa Exact-Lot NO checkpoint source",
        "Run Norway Auksjonen public clothing path",
        "Read FINN saved-search alerts from Gmail",
        "Restore previous lifecycle SQLite state",
    ):
        assert old_stage in ARCHIVE.read_text(encoding="utf-8")


def test_existing_direct_source_is_no_only_and_review_only():
    original = DIRECT.read_text(encoding="utf-8")
    assert '"scope": "NO_ONLY_ALL_ASSETS"' in original
    assert "parse_auksjonen_item_page" in original
    assert "build_public_item_url" in original
    assert '"automatic_purchase": False' in original
    assert '"paid_api_requests": 0' in original
    assert "CLOTHING_INVENTORY" not in original
