"""Bounded review-only Vareauksjonen probe for items with unlabeled index links.

The index frequently omits the parent bankruptcy auction name on lot anchors.
Only a source-native individual heading can promote a URL to *research*;
never infer an active sale, official seller or verified estate from a category.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

from scripts.audit_norway_insolvency_sale_links import index_says_closed, item_says_closed
from scripts.run_norway_insolvency_sale_links import (
    INSOLVENCY, ITEM_ESTATE, Page, SOURCES, exact_item, fetch_html,
)

INDEX = SOURCES["Vareauksjonen"]
TOTAL_DETAIL_LIMIT = 9


def augment(report: Mapping[str, Any], *, loader: Callable[[str], str] = fetch_html,
            max_probe: int = 3, now: datetime | None = None) -> dict[str, Any]:
    if (report.get("schema_version") != "no-insolvency-multisource-evidence-1" or
            report.get("scope") != "NO_ONLY_BANKRUPTCY_LIQUIDATION_ALL_SECTORS"):
        raise ValueError("Only original bounded Norway insolvency evidence is supported")
    used = report.get("detail_pages_checked")
    previous = report.get("review_only_unverified_direct_leads")
    if (not isinstance(used, int) or not 0 <= used <= TOTAL_DETAIL_LIMIT or
            not isinstance(previous, list) or len(previous) > used or
            not isinstance(max_probe, int) or not 0 <= max_probe <= TOTAL_DETAIL_LIMIT - used):
        raise ValueError("Probe exceeds total nine-page budget or malformed report")
    result = dict(report)
    errors = list(result.get("source_errors") or [])
    leads = list(previous)
    visited = {item.get("url") for item in leads}
    diagnostics: dict[str, Any] = {
        "unlabeled_unique_item_urls": 0, "homepage_closed_items_not_probed": 0,
        "detail_pages_probed": 0, "estate_heading_matched": 0,
        "sold_or_ended_details_excluded": 0, "new_review_only_leads": 0,
        "selection": "SPACED_BOUNDED_INDEX_SAMPLE_NOT_COMPREHENSIVE",
    }
    try:
        html = loader(INDEX)
        page = Page()
        page.feed(html)
    except Exception as exc:
        errors.append({"source": "Vareauksjonen", "stage": "unlabeled_index",
                       "reason": f"{type(exc).__name__}: {exc}"})
        html, page = "", Page()
    candidates: dict[str, str] = {}
    for href, label in page.anchors:
        url = exact_item("Vareauksjonen", href, INDEX)
        if (url and url not in visited and
                not INSOLVENCY.search(label + " " + urlsplit(url).path)):
            candidates.setdefault(url, label)
    diagnostics["unlabeled_unique_item_urls"] = len(candidates)
    eligible = []
    for url, label in candidates.items():
        if index_says_closed(html, label):
            diagnostics["homepage_closed_items_not_probed"] += 1
        else:
            eligible.append((url, label))
    # Spread across the index instead of silently inspecting only its first lot.
    if eligible and max_probe:
        positions = [i * len(eligible) // min(max_probe, len(eligible))
                     for i in range(min(max_probe, len(eligible)))]
        for position in positions:
            url, label = eligible[position]
            diagnostics["detail_pages_probed"] += 1
            try:
                item_html = loader(url)
                item = Page()
                item.feed(item_html)
                if len(item.headings) < 2:
                    continue  # No separate parent-auction and individual-lot heading.
                auction, lot = item.headings[0], item.headings[-1]
                if not lot or lot == auction:
                    continue
                item_text = " ".join(" ".join(item.parts).split())[:2500]
                if not (INSOLVENCY.search(auction) or ITEM_ESTATE.search(item_text[:1800])):
                    continue
                diagnostics["estate_heading_matched"] += 1
                if item_says_closed(item_html, lot) or index_says_closed(html, lot):
                    diagnostics["sold_or_ended_details_excluded"] += 1
                    continue
                leads.append({
                    "source": "Vareauksjonen", "url": url, "title": lot,
                    "auction_title": auction, "index_label": label,
                    "organisation_number": None, "official_event_url": None,
                    "relation_evidence": "SOURCE_AUCTION_ESTATE_HEADING_ONLY_NOT_OFFICIAL",
                    "sale_status": "UNVERIFIED_NO_SOURCE_NATIVE_OPEN_PROOF",
                    "seller_identity_verified": False, "availability_verified": False,
                    "inventory_verified": False, "review_only": True,
                    "captured_at": (now or datetime.now(timezone.utc)).isoformat(),
                })
                diagnostics["new_review_only_leads"] += 1
            except Exception as exc:
                errors.append({"source": "Vareauksjonen", "stage": "unlabeled_item", "url": url,
                               "reason": f"{type(exc).__name__}: {exc}"})
    result.update({
        "detail_pages_checked": used + diagnostics["detail_pages_probed"],
        "unverified_lead_count": len(leads), "review_only_unverified_direct_leads": leads,
        "source_errors": errors, "vare_unlabeled_lot_probe": diagnostics,
        "verified_insolvency_sale_count": 0, "verified_insolvency_sale_links": [],
        "source_coverage_complete": False,
    })
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--max-probe", type=int, default=3)
    args = parser.parse_args()
    path = args.output_dir / "insolvency-sale-link-investigations.json"
    raw = path.read_text(encoding="utf-8")
    result = augment(json.loads(raw), max_probe=args.max_probe)
    (args.output_dir / "insolvency-sale-link-discovery-raw.json").write_text(raw, encoding="utf-8")
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = args.output_dir / "insolvency-sale-link-investigations-ar.txt"
    if report.exists():
        (args.output_dir / "insolvency-sale-link-discovery-raw-ar.txt").write_text(
            report.read_text(encoding="utf-8"), encoding="utf-8")
    lines = ["النرويج: فحص محدود لعناوين أصول Vareauksjonen التي لا تذكر الإفلاس في رابط الفهرس.",
             "روابط البحث هنا ليست فرص بيع مؤكدة ولا دليلًا على توافر البضائع.",
             f"صفحات فردية فُحصت إجمالًا: {result['detail_pages_checked']}/9 | روابط للمراجعة: {result['unverified_lead_count']} | مبيعات إفلاس مؤكدة: 0"]
    for lead in result["review_only_unverified_direct_leads"]:
        lines.extend([lead["title"], lead["url"], "تحتاج إثبات البائع وحالة البيع."])
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"detail_pages_checked": result["detail_pages_checked"],
                      "unverified_lead_count": result["unverified_lead_count"],
                      "vare_unlabeled_lot_probe": result["vare_unlabeled_lot_probe"],
                      "source_errors": result["source_errors"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
