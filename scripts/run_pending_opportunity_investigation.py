#!/usr/bin/env python3
"""Investigate a bounded set of pending opportunities using their live pages.

This is an evidence step, not a promotion or purchase step. It records what
the public page proves and leaves the commercial decision to the existing
gates. A small durable state rotates investigation across the pending backlog
so daily runs do not keep re-fetching the same highest-scoring rows forever.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping, Callable

from opportunity_engine.discovery.exa_shadow_page_verification import (
    ACTIVE_STOCK_SIGNAL,
    EXACT_LOT_CANDIDATE,
    FETCH_FAILED,
    _classify_page,
    fetch_public_page,
)

SCHEMA_VERSION = "pending-opportunity-investigation-1.2"
STATE_SCHEMA_VERSION = "pending-opportunity-investigation-state-1.0"
STATE_FILENAME = "pending-investigation-state.json"
MAX_LIMIT = 20
PENDING_WORKFLOW_STATUSES = {"REQUIRES_VERIFICATION", "ACTIVE_OPPORTUNITY"}


def _text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _rows(value: object) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, Mapping)] if isinstance(value, list) else []


def _is_public_http_url(value: object) -> bool:
    text = _text(value).lower()
    return text.startswith("https://") or text.startswith("http://")


def _investigation_url(item: Mapping[str, Any]) -> str:
    """Return the best live-page URL available on a checkpoint record.

    Canonical checkpoint records may use the public listing URL itself as
    ``opportunity_identity`` without duplicating it into ``source_url``.
    """
    for key in ("source_url", "canonical_url", "url", "opportunity_identity"):
        value = item.get(key)
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
        item["_rank_score"] = score
        item["_attempt_count"] = attempts
        item["_last_investigated_at"] = _text(history.get("last_investigated_at"))
        rows.append(item)

    # Unseen rows always come first. Once every row has had a turn, revisit the
    # oldest attempted rows before newer attempts. Score only ranks peers.
    rows.sort(
        key=lambda item: (
            0 if int(item.get("_attempt_count") or 0) == 0 else 1,
            _text(item.get("_last_investigated_at")),
            -float(item.get("_rank_score") or 0),
            _text(item.get("opportunity_identity")),
        )
    )
    for item in rows:
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

    results: list[dict[str, Any]] = []
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
                status = "VERIFIED_EXACT_LOT_CANDIDATE"
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
            try:
                previous_attempts = max(0, int(previous.get("attempt_count") or 0))
            except (TypeError, ValueError):
                previous_attempts = 0
            updated_state_records[state_key] = {
                "attempt_count": previous_attempts + 1,
                "last_investigated_at": generated_at,
                "last_status": result_row["investigation_status"],
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
        "previously_investigated_pending_count": previously_attempted_pending,
        "unseen_pending_before_selection": unseen_before,
        "newly_investigated_count": selected_unseen_count,
        "unseen_pending_after_selection": max(0, unseen_before - selected_unseen_count),
        "selected_count": len(selected),
        "remaining_selectable_after_selection": max(0, len(selectable_rows) - len(selected)),
        "investigated_count": len(results),
        "status_counts": counts,
        "results": results,
        "investigation_state": updated_state,
        "promotion_to_opportunity_allowed": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


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

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(result["investigation_state"], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
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
        "selected_count": result["selected_count"],
        "investigated_count": result["investigated_count"],
        "newly_investigated_count": result["newly_investigated_count"],
        "unseen_pending_after_selection": result["unseen_pending_after_selection"],
        "status_counts": result["status_counts"],
        "state_path": state_path.as_posix(),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
