"""Read-only, zero-API join of official event leads with existing auction evidence.

An organisation number in an auction record is an unverified assertion until
independently checked. This tool outputs *investigation leads*, not stock proof.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.auction_only_review_policy import auction_route
from scripts.run_event_first_hunter_pilot import render_arabic


def link_existing_auctions(
    event_report: Mapping[str, Any],
    market_brief: Mapping[str, Any],
    *,
    max_lots_per_event: int = 3,
) -> dict[str, Any]:
    """Join only exact Norwegian registry numbers and approved auction lot URLs."""
    if not 1 <= max_lots_per_event <= 5:
        raise ValueError("max_lots_per_event must be between 1 and 5")
    if event_report.get("schema_version") != "event-first-hunter-pilot-1.0":
        raise ValueError("Expected event-first-hunter-pilot-1.0 input")
    raw_rows = market_brief.get("current_direct_opportunities")
    if not isinstance(raw_rows, list):
        raise ValueError("The market brief lacks current_direct_opportunities; not a verified zero")

    indexed: dict[str, dict[str, dict[str, Any]]] = {}
    rejected = 0
    for row in raw_rows:
        if not isinstance(row, dict):
            rejected += 1
            continue
        number = str(row.get("organisation_number") or "").strip()
        url = row.get("source_url")
        if (row.get("market_code") != "NO" or len(number) != 9
                or not number.isascii() or not number.isdigit()
                or not isinstance(url, str)
                or auction_route(url) != "AUKSJONEN_LOT"):
            rejected += 1
            continue
        indexed.setdefault(number, {})[url] = {
            "source_url": url,
            "source_title": str(row.get("title") or "").strip() or None,
            "reported_organisation_number": number,
            "auction_record_identity": str(row.get("opportunity_identity") or "").strip() or None,
            "record_capture_at": market_brief.get("generated_at"),
            "association_status": "CANDIDATE_EXACT_NUMBER_MATCH_NOT_INDEPENDENTLY_VERIFIED",
            "auction_open_verified": False,
            "inventory_verified": False,
            "seller_identity_verified": False,
            "purchase_authorized": False,
        }

    events: list[dict[str, Any]] = []
    total = 0
    for original in event_report.get("events") or []:
        if not isinstance(original, dict):
            raise ValueError("Event report contains a malformed event")
        event = dict(original)
        orgnr = str(event.get("organisation_number") or "")
        official = str(event.get("official_source_url") or "")
        if len(orgnr) != 9 or not orgnr.isdigit() or official != (
            f"https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}"
        ):
            raise ValueError("Event lacks exact official company provenance")
        candidates = list(sorted(indexed.get(orgnr, {}).values(), key=lambda row: row["source_url"]))
        event["related_auction_leads"] = candidates[:max_lots_per_event]
        event["unshown_related_auction_count"] = max(0, len(candidates) - max_lots_per_event)
        event["relation_evidence"] = (
            "EXACT_REPORTED_ORGANISATION_NUMBER_UNVERIFIED_ASSOCIATION" if candidates
            else "NO_EXACT_ORGANISATION_NUMBER_LINK_IN_SUPPLIED_BRIEF"
        )
        # Preserve the original unknown inventory/availability status.
        event["inventory_verified"] = False
        event["availability_verified"] = False
        event["inventory_link"] = None
        total += len(event["related_auction_leads"])
        events.append(event)

    result = dict(event_report)
    result["schema_version"] = "event-auction-evidence-link-1.0"
    result["source_market_brief_capture_at"] = market_brief.get("generated_at")
    result["existing_auction_record_count"] = len(raw_rows)
    result["ignored_unmatched_or_unqualified_record_count"] = rejected
    result["related_auction_lead_count"] = total
    result["verified_inventory_links"] = 0
    result["paid_search_requests"] = 0
    result["openai_requests"] = 0
    result["automatic_contact"] = False
    result["automatic_bid"] = False
    result["automatic_purchase"] = False
    result["automatic_payment"] = False
    result["events"] = events
    return result


def render_linked_arabic(report: Mapping[str, Any]) -> str:
    # The original concise official-event cards remain the visible starting point.
    basic = dict(report)
    basic["schema_version"] = "event-first-hunter-pilot-1.0"
    lines = [render_arabic(basic).rstrip(), "", "مطابقة سجلات المزادات السابقة — روابط للتحقيق فقط، لا إثبات مخزون أو توافر:"]
    for i, event in enumerate(report.get("events") or [], 1):
        links = event.get("related_auction_leads") or []
        if not links:
            continue
        lines.append(f"بطاقة {i} | روابط مزادات محتملة مرتبطة برقم الشركة:")
        for row in links:
            lines.append(f"- {row['source_url']} | {row.get('source_title') or 'عنوان مجهول'}")
        lines.append("تطابق الرقم المصرح به لا يثبت علاقة البائع بالشركة أو حالة المزاد أو وجود المخزون.")
    lines.append(f"إجمالي الروابط المحتملة من السجل السابق: {report['related_auction_lead_count']} | روابط مخزون مؤكدة: 0")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, required=True, help="Existing event-first-report.json")
    parser.add_argument("--market-brief", type=Path, required=True, help="Existing domain-market-intelligence-brief.json")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    events = json.loads(args.events.read_text(encoding="utf-8"))
    brief = json.loads(args.market_brief.read_text(encoding="utf-8"))
    if not isinstance(events, dict) or not isinstance(brief, dict):
        parser.error("Both inputs must be JSON objects")
    linked = link_existing_auctions(events, brief)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "event-auction-leads.json").write_text(
        json.dumps(linked, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "event-auction-leads-ar.txt").write_text(
        render_linked_arabic(linked), encoding="utf-8"
    )
    print(json.dumps({
        "event_count": len(linked["events"]),
        "candidate_auction_links": linked["related_auction_lead_count"],
        "verified_inventory_links": 0,
        "paid_search_requests": 0,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
