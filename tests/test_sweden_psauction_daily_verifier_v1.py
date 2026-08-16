from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_sweden_clothing_inventory_discovery_search.py"
VERIFIER = ROOT / "src" / "opportunity_engine" / "discovery" / "sweden_psauction_playwright.py"
WORKFLOW = ROOT / ".github" / "workflows" / "multi-market-daily-operator-checkpoint.yaml"


def test_verified_psauction_source_runs_auto_enable_rendered_verification() -> None:
    text = RUNNER.read_text(encoding="utf-8")

    assert 'args.source == "psauction" and args.verify_pages' in text
    assert "PSAuctionPlaywrightFallbackVerifier" in text
    assert "max_pages=args.psauction_browser_pages" in text
    assert "default=6" in text


def test_psauction_rendering_is_bounded_and_fail_closed() -> None:
    text = VERIFIER.read_text(encoding="utf-8")

    assert "MAX_RENDERED_PAGES = 6" in text
    assert '"specific_psauction_item_pages_only"' in text
    assert '"insufficient public listing content"' in text
    assert "canonicalize_psauction_item_url" in text
    assert "system Chromium renderer failed" in text
    assert '"automatic_contact": False' in text
    assert '"automatic_bid": False' in text
    assert '"automatic_purchase_decision": False' in text
    assert '"automatic_payment": False' in text


def test_daily_checkpoint_already_requests_psauction_page_verification() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    start = text.index("- name: Run Sweden PS Auction bounded direct scan")
    end = text.index("- name: Run active Riegermann discovery", start)
    step = text[start:end]

    assert "--source psauction" in step
    assert "--verify-pages" in step
    assert "--verification-limit 20" in step
