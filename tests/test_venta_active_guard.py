from opportunity_engine.discovery.germany_venta_active import VentaActiveWatchResult
from opportunity_engine.discovery.germany_venta_active_guard import (
    apply_venta_explicit_clothing_gate,
)


def _result(*, child_count: int, full_scope: bool) -> VentaActiveWatchResult:
    identity = "venta-auction:5636"
    diagnostics = {
        "auction_entries_discovered": 1,
        "company_name_only_false_positive_count": 0,
        "clothing_catalog_count": 1,
        "clothing_child_lot_count": child_count,
        "ordinary_child_lot_count": child_count,
        "observed_bulk_lot_count": 0,
        "catalog_runs": [
            {
                "catalog_block_id": "792",
                "opportunity_identity": identity,
                "title": "Metallbau catalog",
                "explicit_clothing_evidence": True,
                "explicit_clothing_terms": ["textilien"],
                "clothing_child_lot_count": child_count,
                "ordinary_child_lot_count": child_count,
                "observed_bulk_lot_count": 0,
                "full_catalog_clothing_scope": full_scope,
            }
        ],
    }
    candidate = {
        "opportunity_identity": identity,
        "page_role": "AUCTION_EVENT",
        "top5_eligible": False,
    }
    report = {
        "venta_active": diagnostics,
        "source_adapter": {
            "parent_candidate_count": 1,
            "child_lot_count": child_count,
            "observed_bulk_lot_count": 0,
            "promoted_bulk_candidate_count": 0,
            "single_garment_candidate_count": 0,
        },
        "merged_candidates": 1,
        "strong_leads_requiring_verification": 1,
        "top5_count": 0,
        "top5_eligible_count": 0,
        "discovery_bands": {"HIGH": 0, "REVIEW": 1, "LOW": 0},
        "opportunity_quality_status": "LEADS_REQUIRING_VERIFICATION",
        "no_opportunities_found": False,
        "rejected_results": 0,
        "false_positive_guard_triggered": 0,
    }
    discovery = {
        "all_discovered_candidates": [candidate],
        "discovery_top5": [],
        "source_adapter": report["source_adapter"],
        "search_run_report": report,
    }
    return VentaActiveWatchResult(discovery_result=discovery, diagnostics=diagnostics)


def test_zero_count_category_only_parent_is_removed() -> None:
    guarded = apply_venta_explicit_clothing_gate(
        _result(child_count=0, full_scope=False)
    )
    report = guarded.discovery_result["search_run_report"]
    diagnostics = report["venta_active"]

    assert guarded.discovery_result["all_discovered_candidates"] == []
    assert diagnostics["clothing_catalog_count"] == 0
    assert diagnostics["zero_count_category_false_positive_count"] == 1
    assert report["no_opportunities_found"] is True
    assert report["opportunity_quality_status"] == "NO_VALID_OPPORTUNITIES"
    assert report["false_positive_guard_triggered"] == 1
    assert report["source_adapter"]["parent_candidate_count"] == 0


def test_catalog_with_clothing_child_evidence_is_retained() -> None:
    guarded = apply_venta_explicit_clothing_gate(
        _result(child_count=2, full_scope=False)
    )

    assert len(guarded.discovery_result["all_discovered_candidates"]) == 1
    assert guarded.diagnostics["clothing_catalog_count"] == 1
    assert guarded.diagnostics["zero_count_category_false_positive_count"] == 0


def test_full_catalog_clothing_heading_is_sufficient_without_lot_labels() -> None:
    guarded = apply_venta_explicit_clothing_gate(
        _result(child_count=0, full_scope=True)
    )

    assert len(guarded.discovery_result["all_discovered_candidates"]) == 1
    assert guarded.diagnostics["clothing_catalog_count"] == 1
    assert guarded.diagnostics["zero_count_category_false_positive_count"] == 0
