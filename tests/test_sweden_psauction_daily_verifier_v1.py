from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_sweden_clothing_inventory_discovery_search.py"
VERIFIER = ROOT / "src/opportunity_engine/discovery/sweden_psauction_playwright.py"
ARCHIVED = ROOT / "docs/archive/legacy-six-market-checkpoint-20260919.yaml.txt"
ACTIVE = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"


def test_historical_psauction_source_auto_enables_rendered_verification() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    assert 'args.source == "psauction" and args.verify_pages' in text
    assert "PSAuctionPlaywrightFallbackVerifier" in text
    assert "max_pages=args.psauction_browser_pages" in text
    assert "default=6" in text


def test_psauction_rendering_is_bounded_and_fail_closed() -> None:
    text = VERIFIER.read_text(encoding="utf-8")
    for marker in ("MAX_RENDERED_PAGES = 6", '"specific_psauction_listing_pages_only"',
                   '"/auction/<id>/<slug>"', '"insufficient public listing content"',
                   "canonicalize_psauction_listing_url", "system Chromium renderer failed",
                   '"automatic_contact": False', '"automatic_bid": False',
                   '"automatic_purchase_decision": False', '"automatic_payment": False'):
        assert marker in text


def test_psauction_verification_is_archived_and_no_longer_scheduled() -> None:
    old = ARCHIVED.read_text(encoding="utf-8")
    start = old.index("- name: Run Sweden PS Auction bounded direct scan")
    end = old.index("- name: Run active Riegermann discovery", start)
    step = old[start:end]
    for marker in ("--source psauction", "--verify-pages", "--verification-limit 20"):
        assert marker in step
    active = ACTIVE.read_text(encoding="utf-8")
    assert "Run Sweden PS Auction bounded direct scan" not in active
    assert "--source psauction" not in active
