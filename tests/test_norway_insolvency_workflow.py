"""Protect the live bankruptcy-only route and preserve old routes as disabled history."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"


def test_live_route_is_official_bankruptcy_then_paid_link_chase_then_openai():
    text = WORKFLOW.read_text(encoding="utf-8")
    live = text.split("  norway-bankruptcy-hunter:\n", 1)[1].split(
        "  norway-all-assets:\n", 1
    )[0]
    restore = live.index("python scripts/restore_norway_bankruptcy_watchlist.py")
    official = live.index("python scripts/run_norway_insolvency_sample.py")
    prepare = live.index("python scripts/run_norway_bankruptcy_watchlist.py prepare")
    chase = live.index("python scripts/run_norway_bankruptcy_link_hunt.py")
    finalize = live.index("python scripts/run_norway_bankruptcy_watchlist.py finalize")
    openai = live.index("python scripts/run_norway_openai_search_intelligence.py")
    assert restore < official < prepare < chase < finalize < openai
    assert "actions: read" in live
    assert "--recent-updates" in live
    assert "--lookback-days 7" in live
    assert "--update-limit 500" in live
    assert "--entity-limit 20" in live
    assert "--max-cards 20" in live
    assert "--max-events 5" in live
    assert "--results-per-query 5" in live
    assert "--max-page-reads 15" in live
    assert "--retention-days 60" in live
    assert "--recheck-days 3" in live
    assert "--max-due-cases 5" in live
    assert "bankruptcy-watchlist-due-events.json" in live
    assert "bankruptcy-new-link-report.json" in live
    assert "retention-days: 90" in live
    assert "--bankruptcy-report" in live
    assert "EXA_API_KEY: ${{ secrets.EXA_API_KEY }}" in live
    assert "BRAVE_SEARCH_API_KEY: ${{ secrets.BRAVE_SEARCH_API_KEY }}" in live
    assert "OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}" in live
    for forbidden in (
        "run_norway_direct_sales.py",
        "run_exa_exact_lot_checkpoint.py",
        "run_finn_email_intake.py",
        "run_cross_source_clothing_verification.py",
        "--market SE",
        "--market DE",
        "--market FR",
        "--market IT",
        "--market NL",
    ):
        assert forbidden not in live


def test_generic_norway_jobs_are_disabled_not_executed():
    text = WORKFLOW.read_text(encoding="utf-8")
    all_assets = text.split("  norway-all-assets:\n", 1)[1].split(
        "  norway-existing-engine:\n", 1
    )[0]
    existing = text.split("  norway-existing-engine:\n", 1)[1].split(
        "  norway-insolvency-source-pilot:\n", 1
    )[0]
    assert "if: ${{ false &&" in all_assets
    assert "if: ${{ false &&" in existing


def test_existing_search_runs_and_experimental_insolvency_route_is_paused():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "  schedule:" in text
    assert "  workflow_dispatch:" in text
    assert "norway-all-assets:" in text
    assert "python scripts/run_norway_direct_sales.py" in text
    assert "python scripts/run_exa_exact_lot_checkpoint.py" in text
    assert "--market NO" in text
    assert "python scripts/run_finn_email_intake.py" in text
    assert "python scripts/run_norway_openai_search_intelligence.py" in text
    assert "norway-existing-engine:" in text
    assert "python scripts/run_cross_source_clothing_verification.py" in text
    assert "norway-insolvency-source-pilot:\n    # The experimental replacement yielded no qualified links in bounded live\n    # samples. Preserve its code/history, but stop duplicate network work.\n    if: ${{ false }}" in text
    assert "run_norway_insolvency_sample.py --page-size 25 --max-cards 10" in text
    assert "norway-insolvency-source-evidence" in text
    assert "norway-events:\n    # Keep the audited source code and historical artifacts; do not execute events.\n    if: ${{ false }}" in text
    for foreign in ("--market SE", "--market DE", "--market FR", "--market IT", "--market NL"):
        assert foreign not in text


def test_preserved_prototype_retains_scan_then_audit_order_but_is_not_live():
    text = WORKFLOW.read_text(encoding="utf-8")
    prototype = text.split("  norway-insolvency-source-pilot:\n", 1)[1].split("  norway-events:\n", 1)[0]
    assert "if: ${{ false }}" in prototype
    source = prototype.index("python scripts/run_norway_insolvency_sale_links.py")
    audit = prototype.index("python scripts/audit_norway_insolvency_sale_links.py")
    upload = prototype.index("name: norway-insolvency-source-evidence")
    assert source < audit < upload
    assert "tests/test_norway_insolvency_sale_status_audit.py" in text
    assert "scripts/audit_norway_insolvency_sale_links.py" in text
