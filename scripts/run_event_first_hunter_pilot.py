"""Small, read-only event-first pilot. No paid providers, sales or SQLite mutations.

The official company event is a LEAD, never proof of a saleable stock lot.
Run manually with --live or replay a previously saved official report with --source-report.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.discovery.direct_official_source_adapters import (
    BRREG_ENTITY_URL,
    collect_brreg_direct_signals,
)

SOURCE_KEY = "BRREG_ENHETSREGISTERET_API"
EVENT_LABELS = {
    "KONKURS": "إفلاس",
    "AVVIKLING": "تصفية",
    "TVANGSAVVIKLING_ELLER_TVANGSOPPLOSNING": "تصفية أو حلّ إجباري",
}


def build_event_report(source: Mapping[str, Any], *, max_cards: int = 5) -> dict[str, Any]:
    """Project verified-source events into leads; never infer inventory or availability."""
    if not 1 <= max_cards <= 10:
        raise ValueError("max_cards must be between 1 and 10")
    if source.get("source_key") != SOURCE_KEY or source.get("source_country") != "NO":
        raise ValueError("Expected the Norwegian official-register source report")

    leads: dict[str, dict[str, Any]] = {}
    rejected = 0
    for item in source.get("signals") or []:
        if not isinstance(item, dict):
            rejected += 1
            continue
        metadata = item.get("metadata") or {}
        if not isinstance(metadata, dict):
            rejected += 1
            continue
        orgnr = str(metadata.get("organisation_number") or "").strip()
        kind = str(metadata.get("event_kind") or "").strip()
        name = str(item.get("company_name") or "").strip()
        url = str(item.get("source_url") or "").strip()
        signal_id = str(item.get("signal_id") or "").strip()
        if (
            len(orgnr) != 9 or not orgnr.isdigit()
            or kind not in EVENT_LABELS or not name
            or url != BRREG_ENTITY_URL.format(orgnr=orgnr)
            or signal_id != f"official-notice:no:brreg:{orgnr}:{kind.casefold()}"
        ):
            rejected += 1
            continue
        leads[signal_id] = {
            "event_id": signal_id,
            "event_kind": kind,
            "event_label_ar": EVENT_LABELS[kind],
            "company_name": name,
            "organisation_number": orgnr,
            "official_source_url": url,
            "event_date": item.get("event_date"),
            "observed_at": item.get("observed_at"),
            "location": item.get("location"),
            "record_type": "OFFICIAL_EVENT_SIGNAL_ONLY",
            "inventory_link": None,
            "inventory_verified": False,
            "availability_verified": False,
            "next_action": "SEARCH_FOR_RELATED_STOCK_WITH_EVIDENCE",
            "research_query": f'"{name}" (konkursbo OR varelager OR auksjon)',
        }

    # The existing collector reads only a bounded latest-updates page and bounded
    # entity details. Reaching either cap is NEVER evidence of complete coverage.
    retrieved = int(source.get("retrieved_record_count") or 0)
    candidates = int(source.get("candidate_entity_count") or 0)
    updates_limit = int(source.get("update_limit") or 500)
    entity_limit = int(source.get("entity_limit") or 20)
    source_status = str(source.get("status") or "UNKNOWN")
    incomplete = (retrieved >= updates_limit or candidates > entity_limit
                  or bool(source.get("errors")) or rejected > 0)
    if source_status not in {"SUCCESS", "VALID_ZERO"}:
        coverage = "BLOCKED_OR_FAILED"
    elif incomplete:
        coverage = "PARTIAL_BOUNDED_SCAN"
    else:
        coverage = "BOUNDED_SCAN_NOT_FULL_REGISTRY"

    ordered = sorted(leads.values(), key=lambda lead: (str(lead["event_date"] or ""), lead["event_id"]), reverse=True)
    visible = ordered[:max_cards]
    return {
        "schema_version": "event-first-hunter-pilot-1.0",
        "generated_at": source.get("generated_at"),
        "source_status": source_status,
        "coverage": coverage,
        "retrieved_update_count": retrieved,
        "candidate_company_count": candidates,
        "source_error_count": len(source.get("errors") or []),
        "invalid_signal_count": rejected,
        "unique_event_count": len(ordered),
        "displayed_event_count": len(visible),
        "truncated_display_count": max(0, len(ordered) - len(visible)),
        "paid_search_requests": 0,
        "openai_requests": 0,
        "verified_inventory_links": 0,
        "human_decision_required": True,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
        "events": visible,
    }


def render_arabic(report: Mapping[str, Any]) -> str:
    lines = [
        "صيّاد الفرص — تجربة الأحداث (النرويج)",
        f"حالة المصدر: {report['source_status']} | نطاق الفحص: {report['coverage']}",
        f"أحداث مميزة: {report['unique_event_count']} | بطاقات: {report['displayed_event_count']} | روابط مخزون مؤكدة: 0",
        "ملاحظة: حدث الشركة ليس عرض بضائع ولا يؤكد توافر المخزون أو إمكانية الشراء.",
    ]
    if report["coverage"] == "BLOCKED_OR_FAILED":
        lines.append("فشل الوصول أو المصدر؛ لا يُعدّ ذلك صفر فرص.")
    elif not report["events"]:
        lines.append("لم تُكتشف أحداث مؤهلة ضمن العينة المحدودة فقط.")
    for i, event in enumerate(report["events"], 1):
        lines.extend([
            "",
            f"بطاقة {i}: {event['event_label_ar']} — {event['company_name']}",
            f"رقم الشركة: {event['organisation_number']}",
            f"تاريخ الحدث: {event['event_date'] or 'غير معلوم'}",
            f"المصدر الرسمي: {event['official_source_url']}",
            "رابط البضائع: لم يُعثر عليه بعد؛ المخزون والتوافر غير مؤكدين.",
            f"بحث المتابعة: {event['research_query']}",
        ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true", help="Use the existing read-only official API collector")
    mode.add_argument("--source-report", type=Path, help="Replay an existing collector report without network calls")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--lookback-days", type=int, default=1)
    parser.add_argument("--update-limit", type=int, default=500)
    parser.add_argument("--entity-limit", type=int, default=20)
    parser.add_argument("--max-cards", type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.lookback_days <= 7 or not 1 <= args.update_limit <= 500 or not 1 <= args.entity_limit <= 20:
        parser.error("Pilot limits: 1-7 days, 1-500 updates and 1-20 company requests")

    if args.live:
        source = collect_brreg_direct_signals(
            observed_at=datetime.now(timezone.utc),
            lookback_days=args.lookback_days,
            update_limit=args.update_limit,
            entity_fetch_limit=args.entity_limit,
        )
    else:
        source = json.loads(args.source_report.read_text(encoding="utf-8"))
    if not isinstance(source, dict):
        parser.error("The official source report must be a JSON object")
    source["update_limit"] = args.update_limit
    source["entity_limit"] = args.entity_limit
    result = build_event_report(source, max_cards=args.max_cards)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "official-source-raw.json").write_text(json.dumps(source, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "event-first-report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "event-first-cards-ar.txt").write_text(render_arabic(result), encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("source_status", "coverage", "unique_event_count", "displayed_event_count", "paid_search_requests")}, ensure_ascii=False))
    if result["coverage"] == "BLOCKED_OR_FAILED":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
