"""Contract for the active Norway-only hunt; historical multi-market spec is archived."""
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
    # The original stays available only as historical documentation, not as
    # another GitHub Actions workflow or an active source.
    assert ARCHIVE.parent != WORKFLOW.parent


def test_active_workflow_is_scheduled_norway_only():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.startswith("name: Norway Opportunity Hunter\n")
    assert 'cron: "47 5 * * *"' in text
    assert 'timezone: "Europe/Oslo"' in text
    assert "workflow_dispatch:" in text
    assert "norway-events:" in text
    assert "run_event_first_hunter_pilot.py" in text
    assert "--live --lookback-days 1 --update-limit 500 --entity-limit 20" in text
    assert "--max-cards 5" in text
    assert "norway-hunter-evidence" in text
    assert "if: always()" in text


def test_active_workflow_does_not_execute_non_norwegian_sources_or_paid_services():
    text = WORKFLOW.read_text(encoding="utf-8")
    # Ignore the explanatory comment but reject active invocations and scope.
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    for token in (
        "--market SE", "--market DE", "--market FR", "--market IT", "--market NL",
        '"market_code": "SE"', '"market_code": "DE"', '"market_code": "FR"',
        '"market_code": "IT"', '"market_code": "NL"',
        "run_explicit_six_market_expansion.py", "run_unified_daily_runtime.py",
        "run_market_clothing_inventory_discovery.py", "run_exa_exact_lot_checkpoint.py",
        "BRAVE_SEARCH_API_KEY:", "EXA_API_KEY:", "OPENAI_API_KEY:",
        "GMAIL_CLIENT_ID:", "MYBRING_API_KEY:",
        "--persist-unified", "--database-url", "automatic_purchase: true",
    ):
        assert token not in code, token
    assert "permissions:\n  contents: read" in code
    assert "contents: write" not in code
    assert "automatic_contact" not in code
    assert "automatic_bid" not in code
    assert "automatic_purchase" not in code


def test_active_workflow_does_not_claim_full_market_coverage_or_inventory():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "Read Norwegian official company events only" in text
    assert "--update-limit 500" in text
    assert "--entity-limit 20" in text
    assert "--output-dir artifacts/norway-hunter" in text
    assert "verified_inventory_links: 1" not in text
