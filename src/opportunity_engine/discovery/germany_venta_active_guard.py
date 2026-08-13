"""Strict post-crawl evidence gate for the VENTA active catalog watch.

VENTA repeats the global category browser on some pages. A label such as
``Textil (0)`` is not clothing inventory evidence. This guard requires either a
bounded catalog heading that describes the whole catalog as clothing inventory
or at least one clothing child lot before a parent opportunity is retained.

After that catalog gate, exact public item verification removes clothing-word
false positives such as ``Kleiderstangen`` and hydrates explicit source
logistics for bounded bulk clothing lots.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from opportunity_engine.discovery.germany_venta_active import (
    VentaActiveWatchResult,
    run_venta_active_clothing_watch,
)
from opportunity_engine.discovery.germany_venta_item_verification import (
    DEFAULT_ITEM_VERIFICATION_LIMIT,
    apply_venta_exact_item_verification,
)


def apply_venta_explicit_clothing_gate(
    result: VentaActiveWatchResult,
) -> VentaActiveWatchResult:
    """Remove parent leads supported only by global zero-count category text."""
    discovery = deepcopy(result.discovery_result)
    report = discovery["search_run_report"]
    diagnostics = report["venta_active"]

    valid_runs: list[dict[str, Any]] = []
    valid_identities: set[str] = set()
    rejected_runs: list[dict[str, Any]] = []
    for catalog_run in diagnostics.get("catalog_runs") or []:
        has_child_evidence = int(
            catalog_run.get("clothing_child_lot_count") or 0
        ) > 0
        has_full_scope_heading = (
            catalog_run.get("full_catalog_clothing_scope") is True
        )
        if has_child_evidence or has_full_scope_heading:
            valid_runs.append(catalog_run)
            identity = str(catalog_run.get("opportunity_identity") or "")
            if identity:
                valid_identities.add(identity)
        elif catalog_run.get("explicit_clothing_evidence") is True:
            rejected_runs.append(catalog_run)

    original_candidates = list(discovery.get("all_discovered_candidates") or [])
    candidates = [
        candidate
        for candidate in original_candidates
        if str(candidate.get("opportunity_identity") or "") in valid_identities
    ]
    discovery["all_discovered_candidates"] = candidates
    discovery["discovery_top5"] = []

    clothing_child_lot_count = sum(
        int(run.get("clothing_child_lot_count") or 0) for run in valid_runs
    )
    ordinary_child_lot_count = sum(
        int(run.get("ordinary_child_lot_count") or 0) for run in valid_runs
    )
    observed_bulk_lot_count = sum(
        int(run.get("observed_bulk_lot_count") or 0) for run in valid_runs
    )
    diagnostics["clothing_catalog_count"] = len(valid_runs)
    diagnostics["clothing_child_lot_count"] = clothing_child_lot_count
    diagnostics["ordinary_child_lot_count"] = ordinary_child_lot_count
    diagnostics["observed_bulk_lot_count"] = observed_bulk_lot_count
    diagnostics["promoted_bulk_lot_count"] = 0
    diagnostics["zero_count_category_false_positive_count"] = len(rejected_runs)
    diagnostics["zero_count_category_false_positives"] = [
        {
            "catalog_block_id": run.get("catalog_block_id"),
            "opportunity_identity": run.get("opportunity_identity"),
            "title": run.get("title"),
            "explicit_clothing_terms": run.get("explicit_clothing_terms") or [],
            "reason": "no clothing child lot and no full-catalog clothing heading",
        }
        for run in rejected_runs
    ]

    report["merged_candidates"] = len(candidates)
    report["strong_leads_requiring_verification"] = len(candidates)
    report["top5_count"] = 0
    report["top5_eligible_count"] = 0
    report["discovery_bands"] = {
        "HIGH": 0,
        "REVIEW": len(candidates),
        "LOW": 0,
    }
    report["opportunity_quality_status"] = (
        "LEADS_REQUIRING_VERIFICATION"
        if candidates
        else "NO_VALID_OPPORTUNITIES"
    )
    report["no_opportunities_found"] = not candidates
    report["rejected_results"] = max(
        0,
        int(diagnostics.get("auction_entries_discovered") or 0) - len(valid_runs),
    )
    report["false_positive_guard_triggered"] = (
        int(diagnostics.get("company_name_only_false_positive_count") or 0)
        + len(rejected_runs)
    )
    adapter = report["source_adapter"]
    adapter["parent_candidate_count"] = len(candidates)
    adapter["child_lot_count"] = clothing_child_lot_count
    adapter["observed_bulk_lot_count"] = observed_bulk_lot_count
    adapter["promoted_bulk_candidate_count"] = 0
    adapter["single_garment_candidate_count"] = 0
    discovery["source_adapter"] = adapter

    return VentaActiveWatchResult(
        discovery_result=discovery,
        diagnostics=diagnostics,
    )


def run_venta_active_clothing_watch_strict(*args: Any, **kwargs: Any) -> VentaActiveWatchResult:
    """Run public VENTA watch, catalog gate, then exact bounded item verification."""
    item_verification_limit = int(
        kwargs.pop("item_verification_limit", DEFAULT_ITEM_VERIFICATION_LIMIT)
    )
    session = kwargs.get("session")
    timeout = float(kwargs.get("timeout", 20.0))
    max_response_bytes = int(kwargs.get("max_response_bytes", 4_000_000))
    gated = apply_venta_explicit_clothing_gate(
        run_venta_active_clothing_watch(*args, **kwargs)
    )
    return apply_venta_exact_item_verification(
        gated,
        session=session,
        timeout=timeout,
        max_response_bytes=max_response_bytes,
        item_verification_limit=item_verification_limit,
    )
