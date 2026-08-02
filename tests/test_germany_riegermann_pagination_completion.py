from opportunity_engine.discovery.germany_riegermann_live import (
    RiegermannLiveResult,
)
from opportunity_engine.discovery.germany_riegermann_pagination_completion import (
    reconcile_riegermann_catalog_completion,
)


def _live_result(diagnostics):
    parent = {
        "page_role": "AUCTION_EVENT",
        "promoted_bulk_lot_count": 0,
        "missing_information": [
            "complete public catalog coverage",
            "cross-border logistics basis",
        ],
        "post_verification_top5_block_reason": (
            "catalog_pagination_incomplete"
        ),
    }
    discovery = {
        "all_discovered_candidates": [parent],
        "search_run_report": {"riegermann_live": diagnostics},
    }
    return RiegermannLiveResult(
        discovery_result=discovery,
        diagnostics=diagnostics,
    )


def test_completion_reconciliation_accepts_only_duplicate_bootstrap_page():
    diagnostics = {
        "catalog_page_urls": [
            "https://riegermann.de/de/objekte/au-908/cabrini",
            "https://riegermann.de/de/objekte/au-908/cabrini?pagenumber=1",
            "https://riegermann.de/de/objekte/au-908/cabrini?pagenumber=2",
            "https://riegermann.de/de/objekte/au-908/cabrini?pagenumber=3",
        ],
        "catalog_page_errors": [
            {
                "url": (
                    "https://riegermann.de/de/objekte/au-908/"
                    "cabrini?pagenumber=1"
                ),
                "error": "pagination page produced no new item URLs",
            }
        ],
        "catalog_page_limit_reached": False,
        "catalog_total_results": 50,
        "child_lots_observed": 50,
        "catalog_expected_page_count": None,
        "catalog_coverage_complete": False,
        "catalog_coverage_reason": "catalog_page_errors",
    }
    live = _live_result(diagnostics)

    reconciled = reconcile_riegermann_catalog_completion(live)
    report = reconciled.discovery_result["search_run_report"]["riegermann_live"]
    parent = reconciled.discovery_result["all_discovered_candidates"][0]

    assert report["catalog_expected_page_count"] == 3
    assert report["catalog_duplicate_bootstrap_page_count"] == 1
    assert report["catalog_result_count_proves_completion"] is True
    assert report["catalog_contiguous_pages_prove_completion"] is True
    assert report["catalog_page_errors"] == []
    assert report["catalog_coverage_reason"] == "complete"
    assert report["catalog_coverage_complete"] is True
    assert parent["catalog_coverage_complete"] is True
    assert "complete public catalog coverage" not in parent["missing_information"]
    assert "post_verification_top5_block_reason" not in parent


def test_completion_reconciliation_keeps_unproven_single_page_incomplete():
    diagnostics = {
        "catalog_page_urls": [
            "https://riegermann.de/de/objekte/au-908/cabrini"
        ],
        "catalog_page_errors": [],
        "catalog_page_limit_reached": False,
        "catalog_total_results": None,
        "child_lots_observed": 24,
        "catalog_expected_page_count": None,
        "catalog_coverage_complete": False,
        "catalog_coverage_reason": "pagination_not_proven",
    }
    live = _live_result(diagnostics)

    reconciled = reconcile_riegermann_catalog_completion(live)
    report = reconciled.discovery_result["search_run_report"]["riegermann_live"]
    parent = reconciled.discovery_result["all_discovered_candidates"][0]

    assert report["catalog_result_count_proves_completion"] is False
    assert report["catalog_contiguous_pages_prove_completion"] is False
    assert report["catalog_coverage_complete"] is False
    assert report["catalog_coverage_reason"] == "pagination_not_proven"
    assert parent["catalog_coverage_complete"] is not True
    assert parent["post_verification_top5_block_reason"] == (
        "catalog_pagination_incomplete"
    )
