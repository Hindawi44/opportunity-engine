#!/usr/bin/env python3
"""Investigate a bounded set of pending opportunities using their live pages.

This is an evidence step, not a purchase or commercial-decision step. It records
what the public page proves, rotates across the pending backlog, and reconciles
that durable investigation evidence back into the checkpoint lifecycle without
claiming more than the page actually proved.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from opportunity_engine.discovery.exa_shadow_page_verification import (
    ACTIVE_STOCK_SIGNAL,
    EXACT_LOT_CANDIDATE,
    FETCH_FAILED,
    _classify_page,
    fetch_public_page,
)
from opportunity_engine.discovery.lifecycle_checkpoint_integration import (
    WORKFLOW_STATUSES,
    write_lifecycle_checkpoint_artifacts,
)

SCHEMA_VERSION = "pending-opportunity-investigation-1.4"
STATE_SCHEMA_VERSION = "pending-opportunity-investigation-state-1.1"
STATE_FILENAME = "pending-investigation-state.json"
MAX_LIMIT = 20
PENDING_WORKFLOW_STATUSES = {"REQUIRES_VERIFICATION", "ACTIVE_OPPORTUNITY"}
VERIFIED_EXACT_LOT_STATUS = "VERIFIED_EXACT_LOT_CANDIDATE"
EXACT_ITEM_PAGE_BLOCKER = "verified exact item-page evidence"
EXACT_ITEM_PAGE_BLOCKERS = frozenset(
    {
        "verified exact item-page evidence",
        "verified exact item page evidence",
        "verified exact item pages for promoted bulk lots",
    }
)


def _text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _text_list(value: object) -> list[str]:
    if isinstance(value, str):
        text = _text(value)
        return [text] if text else []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    result: list[str] = []
    for raw in value:
        if isinstance(raw, Mapping):
            text = _text(raw.get("field_name"))
        else:
            text = _text(raw)
        if text and text not in result:
            result.append(text)
    return result


def _rows(value: object) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, Mapping)] if isinstance(value, list) else []


def _is_public_http_url(value: object) -> bool:
    text = _text(value).lower()
    return text.startswith("https://") or text.startswith("http://")


def _investigation_url(item: Mapping[str, Any]) -> str:
    """Return the best live-page URL available on a checkpoint record.

    Canonical checkpoint records may expose a scalar URL or only the merged
    ``source_urls`` list. Treat both forms as first-class investigation input so
    deduplication cannot make an otherwise verifiable record invisible.
    """
    for key in ("source_url", "canonical_url", "url", "opportunity_identity"):
        value = item.get(key)
        if _is_public_http_url(value):
            return _text(value)
    for value in item.get("source_urls") or []:
        if _is_public_http_url(value):
            return _text(value)
    return ""


def _is_pending(item: Mapping[str, Any]) -> bool:
    if _text(item.get("listing_status")).upper() != "ACTIVE":
        return False
    return _text(item.get("workflow_status")).upper() in PENDING_WORKFLOW_STATUSES


def _state_key(item: Mapping[str, Any]) -> str:
    return _text(item.get("opportunity_identity")) or _investigation_url(item)


def _state_records(state: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    raw = (state or {}).get("records")
    if not isinstance(raw, Mapping):
        return {}
    return {
        _text(key): dict(value)
        for key, value in raw.items()
        if _text(key) and isinstance(value, Mapping)
    }


def _attempt_count(state_records: Mapping[str, Mapping[str, Any]], item: Mapping[str, Any]) -> int:
    row = state_records.get(_state_key(item)) or {}
    try:
        return max(0, int(row.get("attempt_count") or 0))
    except (TypeError, ValueError):
        return 0


def _exact_item_page_blockers(item: Mapping[str, Any]) -> list[str]:
    return [
        value
        for value in _text_list(item.get("missing_evidence"))
        if value.casefold() in EXACT_ITEM_PAGE_BLOCKERS
    ]


def select_pending_opportunities(
    report: Mapping[str, Any],
    limit: int = 10,
    investigation_state: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
    state_records = _state_records(investigation_state)
    rows = []
    for item in _rows(report.get("deduplicated_opportunities")):
        if not _is_pending(item):
            continue
        if not _investigation_url(item):
            continue
        try:
            score = float(item.get("discovery_score") or 0)
        except (TypeError, ValueError):
            score = 0.0
        history = state_records.get(_state_key(item)) or {}
        attempts = _attempt_count(state_records, item)
        item["_resolution_priority"] = 0 if _exact_item_page_blockers(item) else 1
        item["_rank_score"] = score
        item["_attempt_count"] = attempts
        item["_last_investigated_at"] = _text(history.get("last_investigated_at"))
        rows.append(item)

    rows.sort(
        key=lambda item: (
            int(item.get("_resolution_priority") or 0),
            0 if int(item.get("_attempt_count") or 0) == 0 else 1,
            _text(item.get("_last_investigated_at")),
            -float(item.get("_rank_score") or 0),
            _text(item.get("opportunity_identity")),
        )
    )
    for item in rows:
        item.pop("_resolution_priority", None)
        item.pop("_rank_score", None)
        item.pop("_attempt_count", None)
        item.pop("_last_investigated_at", None)
    return rows[:limit]


def investigate_pending_opportunities(
    report: Mapping[str, Any],
    *,
    limit: int = 10,
    page_fetcher: Callable[[str], Any] = fetch_public_page,
    investigation_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    all_rows = _rows(report.get("deduplicated_opportunities"))
    pending_rows = [item for item in all_rows if _is_pending(item)]
    selectable_rows = [item for item in pending_rows if _investigation_url(item)]
    resolution_targetable_rows = [
        item for item in selectable_rows if _exact_item_page_blockers(item)
    ]
    previous_state_records = _state_records(investigation_state)
    previously_attempted_pending = sum(
        _attempt_count(previous_state_records, item) > 0 for item in selectable_rows
    )
    unseen_before = sum(
        _attempt_count(previous_state_records, item) == 0 for item in selectable_rows
    )
    selected = select_pending_opportunities(
        report,
        limit,
        investigation_state=investigation_state,
    )
    selected_unseen_count = sum(
        _attempt_count(previous_state_records, item) == 0 for item in selected
    )
    selected_resolution_targetable_count = sum(
        bool(_exact_item_page_blockers(item)) for item in selected
    )

    results: list[dict[str, Any]] = []
    newly_verified_exact_lot_ids: list[str] = []
    generated_at = datetime.now(timezone.utc).isoformat()
    updated_state_records = {key: dict(value) for key, value in previous_state_records.items()}

    for item in selected:
        url = _investigation_url(item)
        fetched = page_fetcher(url)
        base = {
            "opportunity_identity": item.get("opportunity_identity"),
            "title": item.get("title"),
            "market_code": item.get("market_code"),
            "source_url": url,
            "discovery_score": item.get("discovery_score"),
            "targeted_missing_evidence": _exact_item_page_blockers(item),
        }
        if not getattr(fetched, "ok", False):
            result_row = {
                **base,
                "investigation_status": "FETCH_FAILED",
                "classification": FETCH_FAILED,
                "fetch_error": getattr(fetched, "error", None),
                "evidence": {},
            }
        else:
            classification, evidence = _classify_page(
                title=_text(getattr(fetched, "title", "") or item.get("title")),
                text=_text(getattr(fetched, "text", "")),
                url=_text(getattr(fetched, "final_url", "") or url),
                raw_html=_text(getattr(fetched, "raw_html", "")),
            )
            if classification == EXACT_LOT_CANDIDATE:
                status = VERIFIED_EXACT_LOT_STATUS
            elif classification == ACTIVE_STOCK_SIGNAL:
                status = "VERIFIED_ACTIVE_STOCK"
            else:
                status = "NEEDS_MORE_EVIDENCE"
            result_row = {
                **base,
                "investigation_status": status,
                "classification": classification,
                "status_code": getattr(fetched, "status_code", None),
                "final_url": getattr(fetched, "final_url", url),
                "evidence": evidence,
            }
        results.append(result_row)

        state_key = _state_key(item)
        if state_key:
            previous = updated_state_records.get(state_key) or {}
            previous_status = _text(previous.get("last_status")).upper()
            if (
                result_row["investigation_status"] == VERIFIED_EXACT_LOT_STATUS
                and previous_status != VERIFIED_EXACT_LOT_STATUS
            ):
                newly_verified_exact_lot_ids.append(state_key)
            try:
                previous_attempts = max(0, int(previous.get("attempt_count") or 0))
            except (TypeError, ValueError):
                previous_attempts = 0
            updated_state_records[state_key] = {
                "attempt_count": previous_attempts + 1,
                "last_investigated_at": generated_at,
                "last_status": result_row["investigation_status"],
                "last_classification": result_row.get("classification"),
                "last_status_code": result_row.get("status_code"),
                "last_final_url": result_row.get("final_url") or url,
                "last_evidence": deepcopy(result_row.get("evidence") or {}),
                "source_url": url,
                "market_code": item.get("market_code"),
            }

    counts: dict[str, int] = {}
    for result in results:
        key = _text(result.get("investigation_status"))
        counts[key] = counts.get(key, 0) + 1

    if selected:
        selection_status = "SELECTED_FOR_INVESTIGATION"
    elif pending_rows and not selectable_rows:
        selection_status = "PENDING_ROWS_HAVE_NO_PUBLIC_URL"
    else:
        selection_status = "NO_PENDING_ROWS"

    updated_state = {
        "schema_version": STATE_SCHEMA_VERSION,
        "updated_at": generated_at,
        "records": updated_state_records,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "SUCCESS",
        "selection_status": selection_status,
        "selection_limit": limit,
        "pending_candidate_count": len(pending_rows),
        "selectable_pending_count": len(selectable_rows),
        "unselectable_pending_count": len(pending_rows) - len(selectable_rows),
        "resolution_targetable_pending_count": len(resolution_targetable_rows),
        "selected_resolution_targetable_count": selected_resolution_targetable_count,
        "previously_investigated_pending_count": previously_attempted_pending,
        "unseen_pending_before_selection": unseen_before,
        "newly_investigated_count": selected_unseen_count,
        "unseen_pending_after_selection": max(0, unseen_before - selected_unseen_count),
        "selected_count": len(selected),
        "remaining_selectable_after_selection": max(0, len(selectable_rows) - len(selected)),
        "investigated_count": len(results),
        "status_counts": counts,
        "newly_verified_exact_lot_ids": sorted(set(newly_verified_exact_lot_ids)),
        "results": results,
        "investigation_state": updated_state,
        "promotion_to_opportunity_allowed": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _candidate_score(item: Mapping[str, Any]) -> tuple[float, str]:
    try:
        score = float(item.get("discovery_score") or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    return (-score, _text(item.get("opportunity_identity")))


def reconcile_investigation_lifecycle(
    report: Mapping[str, Any],
    investigation_state: Mapping[str, Any],
    *,
    newly_verified_ids: Sequence[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply only evidence that a durable exact-lot investigation actually proved.

    Exact-lot verification clears recognized exact-item-page blockers and nothing
    else. A record advances to ACTIVE_OPPORTUNITY only when that was its final
    blocker. Prior durable state is reapplied on later daily runs so canonical
    source regeneration cannot silently forget investigation evidence.
    """
    reconciled = deepcopy(dict(report))
    state_records = _state_records(investigation_state)
    newly_verified = {_text(item) for item in newly_verified_ids or [] if _text(item)}
    applied_ids: list[str] = []
    blocker_cleared_ids: list[str] = []
    already_satisfied_ids: list[str] = []
    still_pending_ids: list[str] = []
    promoted_ids: list[str] = []

    records = reconciled.get("deduplicated_opportunities") or []
    for item in records:
        if not isinstance(item, dict):
            continue
        identity = _state_key(item)
        history = state_records.get(identity) or {}
        if _text(history.get("last_status")).upper() != VERIFIED_EXACT_LOT_STATUS:
            continue
        if _text(item.get("listing_status")).upper() != "ACTIVE":
            continue
        workflow = _text(item.get("workflow_status")).upper()
        if workflow not in PENDING_WORKFLOW_STATUSES:
            continue

        missing = _text_list(item.get("missing_evidence"))
        matched_blockers = [
            value for value in missing if value.casefold() in EXACT_ITEM_PAGE_BLOCKERS
        ]
        item["pending_investigation"] = {
            "status": VERIFIED_EXACT_LOT_STATUS,
            "last_investigated_at": history.get("last_investigated_at"),
            "source_url": history.get("source_url"),
            "final_url": history.get("last_final_url"),
            "evidence": deepcopy(history.get("last_evidence") or {}),
            "evidence_effect": "RECOGNIZED_EXACT_ITEM_PAGE_BLOCKERS_ONLY",
            "matched_blockers": matched_blockers,
        }
        applied_ids.append(identity)

        if not matched_blockers:
            already_satisfied_ids.append(identity)
            if workflow == "REQUIRES_VERIFICATION":
                still_pending_ids.append(identity)
            continue

        matched_keys = {value.casefold() for value in matched_blockers}
        remaining = [value for value in missing if value.casefold() not in matched_keys]
        item["missing_evidence"] = remaining
        item["verified"] = True
        blocker_cleared_ids.append(identity)

        if remaining:
            item["workflow_status"] = "REQUIRES_VERIFICATION"
            item["evaluation_status"] = "REQUIRES_VERIFICATION"
            item["analysis_eligible"] = False
            item["lifecycle_reason_code"] = "PENDING_INVESTIGATION_PARTIAL_EVIDENCE"
            still_pending_ids.append(identity)
        else:
            item["workflow_status"] = "ACTIVE_OPPORTUNITY"
            item["evaluation_status"] = "NOT_EVALUATED"
            item["analysis_eligible"] = True
            item["lifecycle_reason_code"] = "PENDING_INVESTIGATION_EXACT_LOT_VERIFIED"
            promoted_ids.append(identity)

    valid_records = [item for item in records if isinstance(item, Mapping)]
    reconciled["analysis_eligible_count"] = sum(
        item.get("analysis_eligible") is True
        and _text(item.get("listing_status")).upper() == "ACTIVE"
        for item in valid_records
    )
    reconciled["commercially_qualified_count"] = sum(
        _text(item.get("workflow_status")).upper() == "QUALIFIED_OPPORTUNITY"
        for item in valid_records
    )

    lifecycle = reconciled.get("lifecycle")
    if isinstance(lifecycle, dict):
        stage = Counter(_text(item.get("workflow_status")).upper() for item in valid_records)
        evaluation = Counter(
            _text(item.get("evaluation_status")).upper() for item in valid_records
        )
        lifecycle["stage_counts"] = {
            status: int(stage.get(status, 0)) for status in WORKFLOW_STATUSES
        }
        lifecycle["evaluation_status_counts"] = dict(
            sorted((key, int(value)) for key, value in evaluation.items() if key)
        )
        lifecycle["requires_verification_count"] = int(
            stage.get("REQUIRES_VERIFICATION", 0)
        )

    all_missing: set[str] = set()
    for item in valid_records:
        all_missing.update(_text_list(item.get("missing_evidence")))
    reconciled["missing_evidence"] = sorted(all_missing)

    applied_set = set(applied_ids)
    unresolved_evidence_counts: Counter[str] = Counter()
    for item in valid_records:
        identity = _state_key(item)
        if identity not in applied_set:
            continue
        if _text(item.get("workflow_status")).upper() != "REQUIRES_VERIFICATION":
            continue
        unresolved_evidence_counts.update(_text_list(item.get("missing_evidence")))

    current_run_promoted = [identity for identity in promoted_ids if identity in newly_verified]
    if current_run_promoted:
        promoted_set = set(current_run_promoted)
        candidates = [
            item
            for item in valid_records
            if _text(item.get("opportunity_identity")) in promoted_set
        ]
        candidates.sort(key=_candidate_score)
        target = candidates[0] if candidates else None
        if target is not None:
            reconciled["next_human_action"] = {
                "action": "REVIEW_ONE_OPPORTUNITY",
                "opportunity_identity": _text(target.get("opportunity_identity")),
                "reason": (
                    "Current-run page investigation cleared the final exact-item "
                    "verification blocker; the opportunity is ready for human analysis review."
                ),
                "workflow_status": "ACTIVE_OPPORTUNITY",
                "missing_evidence": list(target.get("missing_evidence") or []),
            }

        novelty = reconciled.get("daily_novelty")
        if isinstance(novelty, dict):
            active_ids = {
                _text(item.get("opportunity_identity"))
                for item in valid_records
                if _text(item.get("listing_status")).upper() == "ACTIVE"
                and _text(item.get("workflow_status")).upper() == "ACTIVE_OPPORTUNITY"
                and item.get("analysis_eligible") is True
            }
            novel_ids = {
                _text(item) for item in novelty.get("novel_active_opportunity_ids") or []
            }
            novel_ids.update(current_run_promoted)
            novel_ids.intersection_update(active_ids)
            carryover_ids = active_ids - novel_ids
            novelty.update(
                {
                    "reason": "SINCE_PREVIOUS_SUCCESSFUL_CHECKPOINT_PLUS_PENDING_INVESTIGATION",
                    "active_analysis_eligible_count": len(active_ids),
                    "novel_active_count": len(novel_ids),
                    "carryover_active_count": len(carryover_ids),
                    "novel_active_opportunity_ids": sorted(novel_ids),
                    "carryover_active_opportunity_ids": sorted(carryover_ids),
                }
            )

    reconciliation = {
        "schema_version": "pending-investigation-lifecycle-reconciliation-1.1",
        "durable_exact_lot_state_count": sum(
            _text(value.get("last_status")).upper() == VERIFIED_EXACT_LOT_STATUS
            for value in state_records.values()
        ),
        "durable_evidence_record_count": sum(
            isinstance(value.get("last_evidence"), Mapping)
            and bool(value.get("last_evidence"))
            for value in state_records.values()
        ),
        "applied_record_count": len(applied_ids),
        "exact_item_page_blocker_cleared_count": len(blocker_cleared_ids),
        "exact_item_page_already_satisfied_count": len(already_satisfied_ids),
        "still_requires_verification_count": len(set(still_pending_ids)),
        "unresolved_evidence_counts": dict(
            sorted((key, int(value)) for key, value in unresolved_evidence_counts.items())
        ),
        "promoted_to_active_count": len(promoted_ids),
        "current_run_promoted_to_active_count": len(current_run_promoted),
        "applied_opportunity_ids": sorted(set(applied_ids)),
        "blocker_cleared_opportunity_ids": sorted(set(blocker_cleared_ids)),
        "promoted_opportunity_ids": sorted(set(promoted_ids)),
        "current_run_promoted_opportunity_ids": sorted(set(current_run_promoted)),
        "commercial_decision_created": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    reconciled["pending_investigation_reconciliation"] = reconciliation
    return reconciled, reconciliation


def _default_state_path(report_path: str | Path) -> Path:
    report = Path(report_path)
    artifacts_root = report.parent.parent
    return artifacts_root / "multi-market-inputs" / "learning" / STATE_FILENAME


def _read_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--state", default="")
    args = parser.parse_args()

    report_path = Path(args.report)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    state_path = Path(args.state) if _text(args.state) else _default_state_path(report_path)
    previous_state = _read_state(state_path)
    result = investigate_pending_opportunities(
        report,
        limit=args.limit,
        investigation_state=previous_state,
    )

    reconciled_report, lifecycle_reconciliation = reconcile_investigation_lifecycle(
        report,
        result["investigation_state"],
        newly_verified_ids=result.get("newly_verified_exact_lot_ids") or [],
    )
    result["lifecycle_reconciliation"] = lifecycle_reconciliation

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(result["investigation_state"], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary_path = report_path.with_name("multi-market-phone-summary.txt")
    if isinstance(reconciled_report.get("lifecycle"), Mapping) and summary_path.exists():
        write_lifecycle_checkpoint_artifacts(
            reconciled_report,
            report_path,
            summary_path,
        )
    else:
        report_path.write_text(
            json.dumps(reconciled_report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": result["status"],
        "selection_status": result["selection_status"],
        "pending_candidate_count": result["pending_candidate_count"],
        "selectable_pending_count": result["selectable_pending_count"],
        "resolution_targetable_pending_count": result["resolution_targetable_pending_count"],
        "selected_resolution_targetable_count": result["selected_resolution_targetable_count"],
        "selected_count": result["selected_count"],
        "investigated_count": result["investigated_count"],
        "newly_investigated_count": result["newly_investigated_count"],
        "unseen_pending_after_selection": result["unseen_pending_after_selection"],
        "status_counts": result["status_counts"],
        "lifecycle_reconciliation": lifecycle_reconciliation,
        "state_path": state_path.as_posix(),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
