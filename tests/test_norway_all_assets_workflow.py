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
    assert "needs: norway-contract" not in job
    assert "github.event_name == 'schedule'" in job
    assert "github.event_name == 'workflow_dispatch'" in job
    assert "python scripts/run_norway_direct_sales.py" in job
    assert "--max-pages 2" in job and "--max-cards 10" in job
    assert "python scripts/restore_norway_review_state.py" in job
    assert "python scripts/run_norway_review_cycle.py" in job
    assert "norway-existing-all-assets-evidence" in job
    assert "name: multi-market-daily-operator-checkpoint" in job
    assert "if: always()" in job
    assert "run_norway_insolvency_sale_links.py" not in job
    for market in ("SE", "DE", "FR", "IT", "NL"):
        assert f"--market {market}" not in job


def test_norway_daily_tools_are_active_but_foreign_execution_stays_off():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert 'cron: "47 6 * * *"' in workflow
    assert 'timezone: "Europe/Oslo"' in workflow
    assert "  workflow_dispatch:" in workflow
    assert "  push:" in workflow and "- main" in workflow
    assert "  norway-insolvency-source-pilot:\n    # The experimental replacement yielded no qualified links in bounded live\n    # samples. Preserve its code/history, but stop duplicate network work.\n    if: ${{ false }}" in workflow

    job = workflow.split("  norway-all-assets:\n", 1)[1].split("  norway-existing-engine:\n", 1)[0]
    for required in (
        "BRAVE_SEARCH_API_KEY: ${{ secrets.BRAVE_SEARCH_API_KEY }}",
        "EXA_API_KEY: ${{ secrets.EXA_API_KEY }}",
        "OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}",
        "GMAIL_REFRESH_TOKEN: ${{ secrets.GMAIL_REFRESH_TOKEN }}",
        "python scripts/run_exa_exact_lot_checkpoint.py",
        "--market NO",
        "python scripts/run_finn_email_intake.py",
        "--gmail-api",
        "python scripts/run_norway_openai_search_intelligence.py",
        "--persist-unified",
        "--database-url",
    ):
        assert required in job
    for forbidden in (
        "--market SE", "--market DE", "--market FR", "--market IT", "--market NL",
        "run_explicit_six_market_expansion.py", "run_market_clothing_inventory_discovery.py",
        "actions: write", "contents: write",
    ):
        assert forbidden not in workflow


def test_archived_foreign_history_is_preserved_not_executed():
    old = ARCHIVE.read_text(encoding="utf-8")
    for old_stage in (
        "Run Exa Exact-Lot NO checkpoint source",
        "Run Norway Auksjonen public clothing path",
        "Read FINN saved-search alerts from Gmail",
        "Restore previous lifecycle SQLite state",
        "Run Exa Exact-Lot SE checkpoint source",
        "Run Exa Exact-Lot DE checkpoint source",
    ):
        assert old_stage in old


def test_existing_direct_source_is_no_only_and_review_only():
    original = DIRECT.read_text(encoding="utf-8")
    assert '"scope": "NO_ONLY_ALL_ASSETS"' in original
    assert "parse_auksjonen_item_page" in original
    assert "build_public_item_url" in original
    assert '"automatic_purchase": False' in original
    assert '"paid_api_requests": 0' in original
    assert "CLOTHING_INVENTORY" not in original
