"""ONE-SHOT proof for BLINTO_NATIVE_LIVE_DISCOVERY_V1.

This file is intentionally temporary. After one green live CI proof it should be
removed so the normal test suite remains deterministic and network-free.
"""
from pathlib import Path

from scripts.run_blinto_native_live_discovery import run_native_live_pipeline


def test_blinto_native_live_proof_has_active_opportunity_and_zero_brave(tmp_path: Path) -> None:
    result, _ = run_native_live_pipeline(
        output_dir=tmp_path,
        results_per_query=20,
        verification_limit=20,
    )
    report = result["search_run_report"]
    source = report["source_diagnostics"]
    verifier = report["source_page_verifier_diagnostics"]

    assert report["brave_requests"] == 0
    assert report["paid_search_used"] is False
    assert report["search_engine_used"] is False
    assert source["listing_requests"] == 1
    assert source["accepted_hits"] >= 1
    assert verifier["exact_page_verification_attempts"] >= 1
    assert verifier["active_pages"] >= 1
    assert any(
        candidate.get("listing_status") == "ACTIVE"
        for candidate in result["all_discovered_candidates"]
    )
