"""V3.7 production pilot orchestration.

This module composes existing ingestion, lifecycle and review-queue contracts. It does
not introduce new scoring, evidence or purchase-decision logic.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable

from opportunity_engine.persistent_opportunity_state import actionable_records, compare_snapshot
from opportunity_engine.opportunity_review_queue import update_review_queue
from opportunity_engine.source_ingestion.multisource import merge_snapshots

Evaluator = Callable[[list[dict[str, Any]]], list[dict[str, Any]]]


def _lifecycle_record(item: dict[str, Any]) -> dict[str, Any]:
    source = item.get("source") if isinstance(item.get("source"), dict) else {}
    return {
        "listing_id": source.get("listing_id"),
        "source_name": source.get("name"),
        "title": source.get("title"),
        "description": source.get("description"),
        "location": source.get("location"),
        "auction_price_nok": source.get("asking_price_nok"),
        "listing_status": source.get("listing_status"),
        "url": source.get("url"),
        "canonical_opportunity": item,
    }


def run_production_cycle(
    snapshots: Iterable[dict[str, Any]],
    *,
    lifecycle_state: dict[str, Any] | None,
    review_state: dict[str, Any] | None,
    evaluator: Evaluator,
    run_at: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Run one deterministic production cycle using existing stage contracts."""
    merged = merge_snapshots(snapshots)
    lifecycle_input = [_lifecycle_record(item) for item in merged.get("opportunities", [])]
    events, next_lifecycle = compare_snapshot(
        lifecycle_input,
        lifecycle_state,
        observed_at=run_at,
    )
    actionable = actionable_records(events)
    canonical_actionable = [
        record["canonical_opportunity"]
        for record in actionable
        if isinstance(record.get("canonical_opportunity"), dict)
    ]
    evaluated = evaluator(canonical_actionable)
    if not isinstance(evaluated, list):
        raise TypeError("evaluator must return a list")
    queue_report, next_review = update_review_queue(evaluated, review_state, run_at=run_at)

    counts = {name: 0 for name in ("NEW", "UPDATED", "UNCHANGED", "REMOVED", "ARCHIVED")}
    for event in events:
        status = str(event.get("lifecycle_status") or "")
        if status in counts:
            counts[status] += 1

    errors: list[str] = []
    report = {
        "schema_version": "3.7",
        "run_at": run_at,
        "sources": merged.get("sources", []),
        "opportunities_received": merged.get("opportunities_received", 0),
        "unique_opportunities": merged.get("unique_opportunities", 0),
        "duplicates_removed": merged.get("duplicate_count", 0),
        "new_opportunities": counts["NEW"],
        "updated_opportunities": counts["UPDATED"],
        "unchanged_opportunities": counts["UNCHANGED"],
        "removed_opportunities": counts["REMOVED"],
        "archived_opportunities": counts["ARCHIVED"],
        "opportunities_sent_to_analysis": len(canonical_actionable),
        "evaluated_opportunities": len(evaluated),
        "review_queue_count": queue_report.get("review_queue_count", 0),
        "new_alerts_count": queue_report.get("new_alerts_count", 0),
        "automatic_purchase_decision": False,
        "errors": errors,
        "status": "PASS" if not errors else "FAIL",
    }
    return report, next_lifecycle, next_review
