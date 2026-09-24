"""Contract for Norway-only runtime and preserved six-market history."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"
ARCHIVE = ROOT / "docs/archive/legacy-six-market-checkpoint-20260919.yaml.txt"


def test_old_six_country_workflow_archived_not_executable():
    assert ARCHIVE.is_file()
    old = ARCHIVE.read_text(encoding="utf-8")
    assert '"market_code": "SE"' in old
    assert '"market_code": "FR"' in old
    assert '"market_code": "NL"' in old
    assert "Run visible FR/IT/NL Exa Exact-Lot expansion" in old
    assert ARCHIVE.parent != WORKFLOW.parent


def test_daily_norway_runtime_and_legacy_event_prototype_remain_separate():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.startswith("name: Norway Opportunity Hunter\n")
    assert "  schedule:" in text
    assert "  workflow_dispatch:" in text
    assert "  pull_request:" in text
    assert "norway-events:\n    # Keep the audited source code and historical artifacts; do not execute events.\n    if: ${{ false }}" in text
    assert "run_event_first_hunter_pilot.py" in text
    assert "norway-hunter-evidence" in text


def test_active_workflow_uses_tools_only_inside_norway():
    text = WORKFLOW.read_text(encoding="utf-8")
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    norway = code.split("  norway-all-assets:\n", 1)[1].split("  norway-existing-engine:\n", 1)[0]

    for required in (
        "run_exa_exact_lot_checkpoint.py",
        "--market NO",
        "BRAVE_SEARCH_API_KEY:",
        "EXA_API_KEY:",
        "OPENAI_API_KEY:",
        "GMAIL_CLIENT_ID:",
        "run_finn_email_intake.py",
        "run_norway_openai_search_intelligence.py",
    ):
        assert required in norway, required

    for token in (
        "--market SE", "--market DE", "--market FR", "--market IT", "--market NL",
        '"market_code": "SE"', '"market_code": "DE"', '"market_code": "FR"',
        '"market_code": "IT"', '"market_code": "NL"',
        "run_explicit_six_market_expansion.py",
        "run_market_clothing_inventory_discovery.py",
        "MYBRING_API_KEY:",
        "automatic_purchase: true",
    ):
        assert token not in code, token

    assert "permissions:\n  contents: read\n  actions: read" in code
    assert "contents: write" not in code
    assert "actions: write" not in code


def test_paused_experimental_insolvency_route_stays_disabled():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "run_norway_insolvency_sample.py --page-size 25 --max-cards 10" in text
    assert "norway-insolvency-source-evidence" in text
    prototype = text.split("  norway-insolvency-source-pilot:\n", 1)[1].split("  norway-events:\n", 1)[0]
    assert "if: ${{ false }}" in prototype
    assert "verified_inventory_links: 1" not in text
