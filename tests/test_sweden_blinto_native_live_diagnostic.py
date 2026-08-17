"""TEMPORARY diagnostic for BLINTO_NATIVE_LIVE_DISCOVERY_V1 live evidence propagation."""
import json
from pathlib import Path

from scripts.run_blinto_native_live_discovery import run_native_live_pipeline


def test_dump_live_candidate_verification_fields(tmp_path: Path) -> None:
    result, _ = run_native_live_pipeline(
        output_dir=tmp_path,
        results_per_query=20,
        verification_limit=20,
    )
    report = result["search_run_report"]
    payload = {
        "report": {
            "confirmed_sales": report.get("confirmed_sales"),
            "strong_leads": report.get("strong_leads_requiring_verification"),
            "brave_requests": report.get("brave_requests"),
            "source": report.get("source_diagnostics"),
            "verifier": report.get("source_page_verifier_diagnostics"),
        },
        "candidates": result.get("all_discovered_candidates"),
    }
    raise AssertionError(json.dumps(payload, ensure_ascii=False, sort_keys=True))
