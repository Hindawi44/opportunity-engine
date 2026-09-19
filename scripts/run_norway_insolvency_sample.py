"""Norway-only, all-sector official insolvency/liquidation signals.

The registry is an event source, NOT a source of goods for sale. No generic
auction item can become an insolvency opportunity without separate evidence.
The three bounded registry queries are samples, not comprehensive or newest.
No paid API, credentials, contacts, purchases or database writes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlencode

import requests

BASE = "https://data.brreg.no/enhetsregisteret/api/enheter"
FILTERS = ("konkurs", "underAvvikling", "underTvangsavviklingEllerTvangsopplosning")
LABELS = {
    "konkurs": "إفلاس",
    "underAvvikling": "تصفية",
    "underTvangsavviklingEllerTvangsopplosning": "تصفية أو حلّ إجباري",
}
DATES = {
    "konkurs": "konkursdato",
    "underAvvikling": "underAvviklingDato",
}


def fetch_status(status: str, size: int) -> Mapping[str, Any]:
    if status not in FILTERS or not 1 <= size <= 50:
        raise ValueError("Unsupported registry query")
    url = BASE + "?" + urlencode({status: "true", "page": 0, "size": size})
    response = requests.get(url, headers={"Accept": "application/json",
                                         "User-Agent": "OpportunityEngine-Norway-Insolvency/1.0"},
                            timeout=20, allow_redirects=False)
    response.raise_for_status()
    if response.url != url or response.is_redirect or len(response.content) > 2_000_000:
        raise RuntimeError("Registry redirected or exceeded bounded response size")
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Registry response is not a JSON object")
    return payload


def sample(*, size: int = 25, max_cards: int = 10,
           fetcher: Callable[[str, int], Mapping[str, Any]] = fetch_status,
           now: datetime | None = None) -> dict[str, Any]:
    if not 1 <= size <= 50 or not 1 <= max_cards <= 10:
        raise ValueError("Bound exceeded")
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    events: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []
    counts: dict[str, dict[str, int | None]] = {}
    successful = 0
    for status in FILTERS:
        try:
            payload = fetcher(status, size)
            if not isinstance(payload, Mapping):
                raise ValueError("Invalid registry response")
            page = payload.get("page")
            embedded = payload.get("_embedded")
            total = page.get("totalElements") if isinstance(page, Mapping) else None
            if not isinstance(embedded, Mapping) or not isinstance(embedded.get("enheter"), list):
                if total != 0:
                    raise ValueError("No explicit registry entity array or confirmed zero")
                rows: list[Any] = []
            else:
                rows = embedded["enheter"]
            if total is not None and (not isinstance(total, int) or total < 0):
                raise ValueError("Invalid totalElements")
            counts[status] = {"read": len(rows), "total_reported": total}
            successful += 1
        except Exception as exc:
            errors.append({"source": status, "error": f"{type(exc).__name__}: {exc}"})
            continue
        for entity in rows:
            if not isinstance(entity, Mapping) or entity.get(status) is not True:
                continue
            number = str(entity.get("organisasjonsnummer") or "").strip()
            name = str(entity.get("navn") or "").strip()
            if not (len(number) == 9 and number.isascii() and number.isdigit() and name):
                continue
            address = entity.get("forretningsadresse")
            if isinstance(address, Mapping) and address.get("landkode") not in (None, "NO"):
                continue
            event = events.setdefault(number, {
                "organisation_number": number,
                "company_name": name,
                "official_url": f"{BASE}/{number}",
                "source_country": "NO",
                "event_kinds": [], "event_date": None,
                "location": address.get("poststed") if isinstance(address, Mapping) else None,
                "evidence_status": "OFFICIAL_REGISTRY_EVENT_ONLY",
                "sale_listing_url": None, "sale_link_verified": False,
                "inventory_verified": False, "sale_availability_verified": False,
                "followup_search": f'"{name}" "{number}" konkursbo varelager avvikling',
            })
            if status not in event["event_kinds"]:
                event["event_kinds"].append(status)
            date_value = entity.get(DATES.get(status, ""))
            if isinstance(date_value, str) and len(date_value) >= 10:
                date_value = date_value[:10]
                if event["event_date"] is None or date_value > event["event_date"]:
                    event["event_date"] = date_value
    ordered = sorted(events.values(), key=lambda e: (e["event_date"] or "", e["organisation_number"]), reverse=True)
    return {
        "schema_version": "norway-insolvency-event-sample-1",
        "scope": "NO_ONLY_INSOLVENCY_LIQUIDATION_ALL_SECTORS",
        "captured_at": stamp,
        "coverage": ("SOURCE_UNAVAILABLE" if not successful else
                     "PARTIAL_SOURCE_FAILURE" if errors else "BOUNDED_SAMPLE_NOT_FULL_NORWAY"),
        "filter_queries_attempted": len(FILTERS), "filter_queries_successful": successful,
        "sample_page_size": size, "counts_by_filter": counts,
        "unique_sampled_companies": len(events),
        "displayed_event_count": min(len(events), max_cards),
        "truncated_event_count": max(0, len(events) - max_cards),
        "verified_insolvency_sale_count": 0, "verified_insolvency_sale_links": [],
        "ordinary_auction_listings_excluded": True,
        "source_errors": errors, "events": ordered[:max_cards],
        "paid_provider_requests": 0, "automatic_contact": False,
        "automatic_bid": False, "automatic_purchase": False,
        "automatic_payment": False,
    }


def render_arabic(report: Mapping[str, Any]) -> str:
    lines = ["صيّاد الإفلاس والتصفية — النرويج، جميع القطاعات",
             f"التغطية: {report['coverage']} — عيّنة محدودة وليست جميع الشركات أو أحدث الإفلاسات.",
             f"شركات رُصدت في العينة: {report['unique_sampled_companies']} | أحداث معروضة: {report['displayed_event_count']} | روابط بيع مرتبطة مثبتة: 0",
             "لا يُعامل أي إعلان مزاد عام كفرصة إفلاس. سجل الشركة لا يثبت بيع أصولها."]
    for event in report["events"]:
        labels = "، ".join(LABELS[k] for k in event["event_kinds"])
        lines.extend(["", f"{labels}: {event['company_name']} ({event['organisation_number']})",
                      f"التاريخ: {event['event_date'] or 'غير معروف'} | المكان: {event['location'] or 'غير معروف'}",
                      f"السجل الرسمي: {event['official_url']}",
                      "رابط بيع الأصول: غير مثبت، ويحتاج بحثًا مستقلاً في المصادر النرويجية."])
    for error in report["source_errors"]:
        lines.append(f"فشل مصدر {error['source']}: {error['error']}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--page-size", type=int, default=25)
    parser.add_argument("--max-cards", type=int, default=10)
    args = parser.parse_args()
    report = sample(size=args.page_size, max_cards=args.max_cards)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "insolvency-events.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "insolvency-events-ar.txt").write_text(render_arabic(report), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("coverage", "unique_sampled_companies", "verified_insolvency_sale_count", "source_errors")}, ensure_ascii=False))
    if report["coverage"] == "SOURCE_UNAVAILABLE":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
