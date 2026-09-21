"""The operator-visible Norway workflow cannot emit arbitrary or sold auction cards."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"


def test_only_official_insolvency_first_pilot_runs():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "  schedule:" not in text
    assert "  workflow_dispatch:" not in text
    assert "run_norway_insolvency_sample.py --page-size 25 --max-cards 10" in text
    assert "norway-insolvency-source-evidence" in text
    assert "run_norway_direct_sales.py --" not in text
    assert "norway-direct-sale-pilot:" not in text
    assert "norway-events:\n    # Keep the audited source code and historical artifacts; do not execute events.\n    if: ${{ false }}" in text
    assert "OPENAI_API_KEY:" not in text
    assert "BRAVE_SEARCH_API_KEY:" not in text
    assert "EXA_API_KEY:" not in text


def test_source_scan_must_finish_and_be_audited_before_arabic_cards_are_uploaded():
    text = WORKFLOW.read_text(encoding="utf-8")
    source = text.index("python scripts/run_norway_insolvency_sale_links.py")
    audit = text.index("python scripts/audit_norway_insolvency_sale_links.py")
    upload = text.index("name: norway-insolvency-source-evidence")
    assert source < audit < upload
    assert "tests/test_norway_insolvency_sale_status_audit.py" in text
    assert "scripts/audit_norway_insolvency_sale_links.py" in text
