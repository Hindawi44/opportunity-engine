#!/usr/bin/env python3
"""Investigate a bounded set of pending opportunities using their live pages.

This is an evidence step, not a promotion or purchase step. It records what
the public page proves and leaves the commercial decision to the existing
gates.
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

SCHEMA_VERSION = "pending-opportunity-investigation-1.1"
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

    Some canonical checkpoint records use the public listing URL itself as
    ``opportunity_identity`` and do not duplicate it into ``source_url``.
    The investigation stage must therefore treat an HTTP(S) identity as a
    valid URL fallback instead of silently selecting zero records.
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


def select_pending_opportunities(report: Mapping[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
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
        item["_rank_score"] = score
        rows.append(item)
    rows.sort(key=lambda item: (-float(item.get("_rank_score") or 0), _text(item.get("opportunity_identity"))))
    for item in rows:
        item.pop("_rank_score", None)
    return rows[:limit]


def investigate_pending_opportunities(
    report: Mapping[str, Any],
    *,
    limit: int = 10,
    page_fetcher: Callable[[str], Any] = fetch_public_page,
) -> dict[str, Any]:
    all_rows = _rows(report.get("deduplicated_opportunities"))
    pending_rows = [item for item in all_rows if _is_pending(item)]
    selectable_rows = [item for item in pending_rows if _investigation_url(item)]
    selected = select_pending_opportunities(report, limit)
    results: list[dict[str, Any]] = []
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
            results.append({
                **base,
                "investigation_status": "FETCH_FAILED",
                "classification": FETCH_FAILED,
                "fetch_error": getattr(fetched, "error", None),
                "evidence": {},
            })
            continue
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
        results.append({
            **base,
            "investigation_status": status,
            "classification": classification,
            "status_code": getattr(fetched, "status_code", None),
            "final_url": getattr(fetched, "final_url", url),
            "evidence": evidence,
        })
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

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "SUCCESS",
        "selection_status": selection_status,
        "selection_limit": limit,
        "pending_candidate_count": len(pending_rows),
        "selectable_pending_count": len(selectable_rows),
        "unselectable_pending_count": len(pending_rows) - len(selectable_rows),
        "selected_count": len(selected),
        "remaining_selectable_after_selection": max(0, len(selectable_rows) - len(selected)),
        "investigated_count": len(results),
        "status_counts": counts,
        "results": results,
        "promotion_to_opportunity_allowed": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    result = investigate_pending_opportunities(report, limit=args.limit)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "selection_status": result["selection_status"],
        "pending_candidate_count": result["pending_candidate_count"],
        "selected_count": result["selected_count"],
        "investigated_count": result["investigated_count"],
        "remaining_selectable_after_selection": result["remaining_selectable_after_selection"],
        "status_counts": result["status_counts"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
