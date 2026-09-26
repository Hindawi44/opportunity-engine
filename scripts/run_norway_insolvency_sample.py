"""Norway-only, all-sector official bankruptcy signals.

The registry is an event source, NOT a source of goods for sale. Liquidation,
forced dissolution and generic auction listings are deliberately excluded.
The bounded registry query is a sample, not comprehensive or necessarily the
newest. No paid API, credentials, contacts, purchases or database writes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlencode

import requests

from opportunity_engine.discovery.direct_official_source_adapters import (
    collect_brreg_direct_signals,
)

BASE = "https://data.brreg.no/enhetsregisteret/api/enheter"
FILTERS = ("konkurs",)
LABELS = {"konkurs": "إفلاس"}
DATES = {"konkurs": "konkursdato"}
SOURCE_KEY = "BRREG_ENHETSREGISTERET_API"


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
    if not 1 <= size <= 50 or not 1 <= max_cards <= 20:
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
                "followup_search": (
                    f'"{name}" konkursbo '
                    "(auksjon OR selges OR varelager OR driftsmidler)"
                ),
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
        "scope": "NO_ONLY_OFFICIAL_BANKRUPTCY_ALL_SECTORS",
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
        "liquidation_events_excluded": True,
        "forced_dissolution_events_excluded": True,
        "surplus_only_links_excluded": True,
        "dealer_links_excluded": True,
        "source_errors": errors, "events": ordered[:max_cards],
        "paid_provider_requests": 0, "automatic_contact": False,
        "automatic_bid": False, "automatic_purchase": False,
        "automatic_payment": False,
    }


def build_recent_sample(
    source: Mapping[str, Any],
    *,
    max_cards: int = 10,
    update_limit: int = 500,
    entity_limit: int = 20,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Convert newest official bankruptcy updates into the strict event schema."""
    if not 1 <= max_cards <= 20:
        raise ValueError("max_cards must be between 1 and 20")
    if not 1 <= update_limit <= 500 or not 1 <= entity_limit <= 20:
        raise ValueError("Recent-update budget exceeded")
    if (
        source.get("source_key") != SOURCE_KEY
        or source.get("source_country") != "NO"
        or source.get("bankruptcy_only") is not True
        or source.get("all_sectors") is not True
    ):
        raise ValueError("Expected all-sector Norwegian bankruptcy-only updates")
    status = str(source.get("status") or "UNKNOWN")
    if status not in {"SUCCESS", "VALID_ZERO", "BLOCKED_DIRECT_ACCESS"}:
        raise ValueError("Unknown official-source status")
    raw_signals = source.get("signals")
    if not isinstance(raw_signals, list):
        raise ValueError("Official-source signals must be a list")

    events: dict[str, dict[str, Any]] = {}
    invalid = 0
    for signal in raw_signals:
        if not isinstance(signal, Mapping):
            invalid += 1
            continue
        metadata = signal.get("metadata")
        if not isinstance(metadata, Mapping):
            invalid += 1
            continue
        organisation_number = str(metadata.get("organisation_number") or "").strip()
        company_name = str(signal.get("company_name") or "").strip()
        official_url = str(signal.get("source_url") or "").strip()
        event_kind = str(metadata.get("event_kind") or "").strip()
        signal_id = str(signal.get("signal_id") or "").strip()
        if (
            event_kind != "KONKURS"
            or len(organisation_number) != 9
            or not organisation_number.isascii()
            or not organisation_number.isdigit()
            or not company_name
            or official_url != f"{BASE}/{organisation_number}"
            or signal_id
            != f"official-notice:no:brreg:{organisation_number}:konkurs"
        ):
            invalid += 1
            continue
        raw_date = str(signal.get("event_date") or "").strip()
        event_date = raw_date[:10] if len(raw_date) >= 10 else None
        events[organisation_number] = {
            "organisation_number": organisation_number,
            "company_name": company_name,
            "official_url": official_url,
            "source_country": "NO",
            "event_kinds": ["konkurs"],
            "event_date": event_date,
            "location": signal.get("location"),
            "evidence_status": "OFFICIAL_RECENT_BANKRUPTCY_EVENT_ONLY",
            "sale_listing_url": None,
            "sale_link_verified": False,
            "inventory_verified": False,
            "sale_availability_verified": False,
            "followup_search": (
                f'"{company_name}" konkursbo '
                "(auksjon OR selges OR varelager OR driftsmidler)"
            ),
        }
    ordered = sorted(
        events.values(),
        key=lambda event: (
            str(event.get("event_date") or ""),
            event["organisation_number"],
        ),
        reverse=True,
    )
    raw_errors = source.get("errors")
    errors = [
        {"source": SOURCE_KEY, "error": str(error)[:1000]}
        for error in (raw_errors if isinstance(raw_errors, list) else [])
    ]
    retrieved = int(source.get("retrieved_record_count") or 0)
    candidates = int(source.get("candidate_entity_count") or 0)
    if status == "BLOCKED_DIRECT_ACCESS":
        coverage = "SOURCE_UNAVAILABLE"
    elif errors or invalid:
        coverage = "PARTIAL_SOURCE_FAILURE"
    elif retrieved >= update_limit or candidates > entity_limit:
        coverage = "PARTIAL_BOUNDED_RECENT_UPDATES"
    else:
        coverage = "BOUNDED_RECENT_UPDATES_NOT_FULL_NORWAY"
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    return {
        "schema_version": "norway-insolvency-event-sample-1",
        "scope": "NO_ONLY_OFFICIAL_BANKRUPTCY_ALL_SECTORS",
        "captured_at": stamp,
        "coverage": coverage,
        "source_mode": "RECENT_OFFICIAL_UPDATES",
        "lookback_days": source.get("lookback_days"),
        "official_updates_read": retrieved,
        "bankruptcy_update_candidates": candidates,
        "official_entity_pages_read": int(source.get("entity_fetch_count") or 0),
        "filter_queries_attempted": 1,
        "filter_queries_successful": 0 if status == "BLOCKED_DIRECT_ACCESS" else 1,
        "sample_page_size": update_limit,
        "counts_by_filter": {
            "konkurs": {
                "read": candidates,
                "total_reported": None,
            }
        },
        "unique_sampled_companies": len(events),
        "displayed_event_count": min(len(events), max_cards),
        "truncated_event_count": max(0, len(events) - max_cards),
        "invalid_official_signal_count": invalid,
        "verified_insolvency_sale_count": 0,
        "verified_insolvency_sale_links": [],
        "ordinary_auction_listings_excluded": True,
        "liquidation_events_excluded": True,
        "forced_dissolution_events_excluded": True,
        "surplus_only_links_excluded": True,
        "dealer_links_excluded": True,
        "source_errors": errors,
        "events": ordered[:max_cards],
        "paid_provider_requests": 0,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def render_arabic(report: Mapping[str, Any]) -> str:
    coverage_note = (
        "تحديثات رسمية حديثة ومحدودة وليست كل إفلاسات النرويج."
        if report.get("source_mode") == "RECENT_OFFICIAL_UPDATES"
        else "عيّنة محدودة وليست جميع الشركات أو بالضرورة أحدث الإفلاسات."
    )
    lines = ["صيّاد الإفلاس فقط — النرويج، جميع القطاعات",
             f"التغطية: {report['coverage']} — {coverage_note}",
             f"شركات رُصدت في العينة: {report['unique_sampled_companies']} | أحداث معروضة: {report['displayed_event_count']} | روابط بيع مرتبطة مثبتة: 0",
             "مستبعد من البداية: التصفية، الحلّ الإجباري، التاجر، والفائض غير المرتبط بإفلاس.",
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
    parser.add_argument("--recent-updates", action="store_true")
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--update-limit", type=int, default=500)
    parser.add_argument("--entity-limit", type=int, default=20)
    args = parser.parse_args()
    source: dict[str, Any] | None = None
    if args.recent_updates:
        if (
            not 1 <= args.lookback_days <= 14
            or not 1 <= args.update_limit <= 500
            or not 1 <= args.entity_limit <= 20
        ):
            parser.error(
                "Recent-update limits: 1-14 days, 1-500 updates and 1-20 entities"
            )
        observed_at = datetime.now(timezone.utc)
        source = collect_brreg_direct_signals(
            observed_at=observed_at,
            lookback_days=args.lookback_days,
            update_limit=args.update_limit,
            entity_fetch_limit=args.entity_limit,
            require_clothing=False,
            bankruptcy_only=True,
        )
        report = build_recent_sample(
            source,
            max_cards=args.max_cards,
            update_limit=args.update_limit,
            entity_limit=args.entity_limit,
            now=observed_at,
        )
    else:
        report = sample(size=args.page_size, max_cards=args.max_cards)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if source is not None:
        (args.output_dir / "official-bankruptcy-updates-raw.json").write_text(
            json.dumps(source, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    (args.output_dir / "insolvency-events.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "insolvency-events-ar.txt").write_text(render_arabic(report), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("coverage", "unique_sampled_companies", "verified_insolvency_sale_count", "source_errors")}, ensure_ascii=False))
    if report["coverage"] == "SOURCE_UNAVAILABLE":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
