"""Protect Norway-only existing discovery and ensure experimental registry search stays paused."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"


def test_existing_search_runs_and_experimental_insolvency_route_is_paused():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "  schedule:" not in text
    assert "  workflow_dispatch:" not in text
    assert "norway-all-assets:" in text
    assert "python scripts/run_norway_direct_sales.py" in text
    assert "norway-existing-engine:" in text
    assert "python scripts/run_cross_source_clothing_verification.py" in text
    assert "norway-insolvency-source-pilot:\n    # The experimental replacement yielded no qualified links in bounded live\n    # samples. Preserve its code/history, but stop duplicate network work.\n    if: ${{ false }}" in text
    assert "run_norway_insolvency_sample.py --page-size 25 --max-cards 10" in text
    assert "norway-insolvency-source-evidence" in text
    assert "norway-events:\n    # Keep the audited source code and historical artifacts; do not execute events.\n    if: ${{ false }}" in text
    for secret in ("OPENAI_API_KEY:", "BRAVE_SEARCH_API_KEY:", "EXA_API_KEY:"):
        assert secret not in text


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
