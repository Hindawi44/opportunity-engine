#!/usr/bin/env python3
"""Write the bounded fabric procurement watch and attach it to the daily brief."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.discovery.fabric_procurement_watch import (
    collect_fabric_procurement_watch,
)


SECTION_START = "\n## Fabric procurement watch\n"


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _compact_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": candidate.get("candidate_id"),
        "source_name": candidate.get("source_name"),
        "source_country": candidate.get("source_country"),
        "title": candidate.get("title"),
        "source_url": candidate.get("source_url"),
        "fabric_terms": candidate.get("fabric_terms") or [],
        "bridal_terms": candidate.get("bridal_terms") or [],
        "price": candidate.get("price"),
        "currency": candidate.get("currency"),
        "procurement_relevance_score": candidate.get(
            "procurement_relevance_score", 0
        ),
        "recommended_operator_action": candidate.get(
            "recommended_operator_action"
        ),
    }


def _brief_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    candidates = report.get("candidates") or []
    compact_candidates = [
        _compact_candidate(item)
        for item in candidates[:5]
        if isinstance(item, Mapping)
    ]
    return {
        "feed_family": report.get("feed_family"),
        "purpose": report.get("purpose"),
        "search_language": report.get("search_language"),
        "approved_official_domains": report.get("approved_official_domains") or [],
        "status_counts": report.get("status_counts") or {},
        "query_budget_total": report.get("query_budget_total", 0),
        "requests_made": report.get("requests_made", 0),
        "candidate_count": report.get("candidate_count", 0),
        "top_candidates": compact_candidates,
        "seller_or_source_verification_required": True,
        "not_part_of_opportunity_top5": True,
        "promotion_to_opportunity_allowed": False,
        "automatic_contact": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _render_text(report: Mapping[str, Any]) -> str:
    lines = [
        "FABRIC PROCUREMENT WATCH",
        f"status_counts: {json.dumps(report.get('status_counts') or {}, sort_keys=True)}",
        f"requests_made: {report.get('requests_made', 0)}",
        f"candidate_count: {report.get('candidate_count', 0)}",
        "purchase_mode: MANUAL_ONLY",
    ]
    candidates = report.get("candidates") or []
    if not candidates:
        lines.append("result: No current official-domain fabric candidate passed the gate.")
        return "\n".join(lines) + "\n"

    lines.append("top_candidates:")
    for index, item in enumerate(candidates[:5], start=1):
        if not isinstance(item, Mapping):
            continue
        price = item.get("price")
        currency = item.get("currency") or ""
        price_text = f"{price} {currency}" if price is not None else "price not visible"
        lines.extend(
            [
                f"{index}. {item.get('source_name')} — {item.get('title')}",
                f"   score: {item.get('procurement_relevance_score', 0)}",
                f"   price: {price_text}",
                f"   url: {item.get('source_url')}",
                "   action: compare sample, composition, width, price and shipping",
            ]
        )
    return "\n".join(lines) + "\n"


def _attach_to_brief(
    report: Mapping[str, Any],
    *,
    brief_json: Path | None,
    brief_text: Path | None,
) -> None:
    summary = _brief_summary(report)
    if brief_json is not None and brief_json.exists():
        payload = json.loads(brief_json.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload["fabric_procurement_watch"] = summary
            _write_json(brief_json, payload)

    if brief_text is not None and brief_text.exists():
        text = brief_text.read_text(encoding="utf-8")
        if SECTION_START in text:
            text = text.split(SECTION_START, 1)[0].rstrip() + "\n"
        section = _render_text(report)
        brief_text.write_text(
            text.rstrip() + SECTION_START + section,
            encoding="utf-8",
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--brief-json")
    parser.add_argument("--brief-text")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        report = collect_fabric_procurement_watch(environment=os.environ)
    except Exception as exc:
        report = {
            "schema_version": "fabric-procurement-watch-1.0",
            "feed_family": "FABRIC_DEADSTOCK_PROCUREMENT_FEED_V1",
            "purpose": "TAILORING_SHOP_FABRIC_PROCUREMENT_INTELLIGENCE",
            "status": "FAILED",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "approved_official_domains": [
                "evaresource.com",
                "fabrichouse.com",
                "bridalfabrics.com",
            ],
            "status_counts": {"FAILED": 1},
            "query_budget_total": 3,
            "requests_made": 0,
            "candidate_count": 0,
            "candidates": [],
            "promotion_to_opportunity_allowed": False,
            "analysis_eligible": False,
            "top5_eligible": False,
            "automatic_contact": False,
            "automatic_reservation": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }

    _write_json(output_dir / "fabric-procurement-watch.json", report)
    (output_dir / "fabric-procurement-watch.txt").write_text(
        _render_text(report), encoding="utf-8"
    )
    _attach_to_brief(
        report,
        brief_json=Path(args.brief_json) if args.brief_json else None,
        brief_text=Path(args.brief_text) if args.brief_text else None,
    )
    print(_render_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
