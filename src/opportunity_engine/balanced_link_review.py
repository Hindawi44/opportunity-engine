"""Balanced, read-only recovery of useful discovery links hidden by URL-only gates.

This is a supplementary human inbox, NOT a source verification or a purchase
recommendation. The strict product/stock/site evidence gates remain unchanged.
Parent auctions are navigation leads requiring child-item extraction, not lots.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit
from typing import Any, Mapping

from opportunity_engine.human_listing_review_queue import classify_url

_RELEVANT_PARENT = re.compile(
    r"butiksinredning|butikslager|kontorsinredning|möblerbutik|"
    r"arbetskläder|skyddskläder|sängtextilier|slippers|accessoarer|"
    r"butiksverksamhet|kläder|arbeidsklær|butikkinnredning|"
    r"office.?furniture|store.?fixtures|clothing.?inventory",
    re.IGNORECASE,
)


def _parts(url: str) -> tuple[str, list[str]]:
    try:
        parsed = urlsplit(url)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            return "", []
        if parsed.username or parsed.password:
            return "", []
        return parsed.hostname.lower().removeprefix("www."), [
            segment for segment in parsed.path.strip("/").split("/") if segment
        ]
    except (TypeError, ValueError):
        return "", []


def _source_item_pattern(url: str) -> bool:
    """Site-specific route hint only; never verifies a seller, item or stock."""
    host, parts = _parts(url)
    if not parts or classify_url(url) == "EXCLUDED":
        return False
    if host == "cubecompany.nl":
        return len(parts) == 2 and parts[0] == "product" and parts[1] not in {"all", "index", "category"}
    if host == "partijhandelaren.nl":
        return len(parts) == 4 and parts[:2] == ["partijhandel", "kleding"] and parts[-1].isdigit()
    if host == "restposten24.de":
        return len(parts) == 2 and parts[-1].isdigit()
    if host == "cdon.se":
        return len(parts) == 2 and parts[0] == "produkt" and bool(
            re.search(r"-[a-f0-9]{20,}$", parts[-1], flags=re.IGNORECASE)
        )
    return False


def build_balanced_review(report: Mapping[str, Any], queue: Mapping[str, Any],
                          memory: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return separately labeled leads; never silently promote held URLs to verified stock."""
    memory = memory or {}
    excluded_ids = set(memory.get("deleted_ids") or [])
    excluded_ids.update(str(item.get("opportunity_id")) for group in ("study", "later")
                        for item in memory.get(group) or [] if isinstance(item, dict))
    rows = {str(row.get("opportunity_identity")): row
            for row in report.get("deduplicated_opportunities") or [] if isinstance(row, dict)}
    visible = {str(row.get("identity")) for row in queue.get("review_queue") or []}
    recovered: list[dict[str, Any]] = []
    parents: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for held in queue.get("held_separately") or []:
        if not isinstance(held, dict):
            continue
        identity = str(held.get("identity") or "")
        if not identity or identity in excluded_ids or identity in visible:
            continue
        record = rows.get(identity)
        if not record:
            continue
        reason = str(held.get("reason") or "")
        if reason == "EXCLUDED_SOURCE" or reason.startswith("SOURCE_RECORD_"):
            continue
        urls = [url for url in record.get("source_urls") or [] if isinstance(url, str)]
        url = next((candidate for candidate in urls if _parts(candidate)[0]), "")
        if not url:
            continue
        if reason == "CAMPAIGN":
            name = str(record.get("title") or held.get("title") or "")
            # The campaign URL slug can carry useful inventory context even
            # when the fetched parent page has a generic search-page title.
            if not _RELEVANT_PARENT.search(name + " " + url):
                continue
            if url not in seen_urls:
                parents.append({
                    "identity": identity, "title": name, "source_url": url,
                    "market": record.get("market_code"),
                    "discovery_score": record.get("discovery_score"),
                    "workflow_status": record.get("workflow_status"),
                    "role": "PARENT_PAGE_FIND_CHILD_LISTINGS",
                    "child_listings_extracted": False,
                    "offer_or_stock_verified": False,
                })
                seen_urls.add(url)
            continue
        if reason not in {"UNKNOWN", "REDIRECT_TO_UNKNOWN"}:
            continue
        if str(record.get("listing_status") or "").upper() in {"ENDED", "HISTORICAL", "SOLD", "SOLD_OUT"}:
            continue
        if str(record.get("workflow_status") or "").upper() == "REJECTED":
            continue
        investigation = record.get("pending_investigation") or {}
        final = investigation.get("final_url") if isinstance(investigation, dict) else None
        candidate = final if isinstance(final, str) and final.strip() else url
        orig_host, _ = _parts(url)
        final_host, _ = _parts(candidate)
        if not orig_host or orig_host != final_host or not _source_item_pattern(candidate):
            continue
        if candidate in seen_urls:
            continue
        try:
            score = float(record.get("discovery_score") or 0)
        except (ValueError, TypeError):
            score = 0
        if score < 50:
            continue
        recovered.append({
            "identity": identity, "title": record.get("title"),
            "source_url": candidate, "market": record.get("market_code"),
            "discovery_score": score,
            "role": "PROBABLE_SOURCE_ITEM_URL_FOR_HUMAN_REVIEW",
            "why_recovered": "Source-specific item URL pattern and existing discovery signals; no live item proof",
            "previous_hold_reason": reason,
            "page_identity_verified": False, "site_identity_verified": False,
            "stock_verified": False, "commercially_qualified": False,
            "record_active_is_stock_proof": False,
        })
        seen_urls.add(candidate)
    return {
        "schema_version": "balanced-link-review-v1", "read_only": True,
        "existing_strict_review_count": len(queue.get("review_queue") or []),
        "recovered_unverified_item_leads": recovered,
        "campaign_parents_for_child_extraction": parents,
        "counts": {"recovered_unverified_item_leads": len(recovered),
                   "campaign_parents_for_child_extraction": len(parents)},
        "automatic_contact": False, "automatic_purchase": False,
        "page_or_company_or_stock_truth_inferred": False,
    }


def readable_balanced_review(review: Mapping[str, Any]) -> str:
    recovered = review["recovered_unverified_item_leads"]
    parents = review["campaign_parents_for_child_extraction"]
    lines = ["روابط أنقذها التصنيف المتوازن — للمراجعة فقط، لا تأكيد للتوافر أو هوية البائع",
             f"روابط منتج محتملة: {len(recovered)} | صفحات مزاد/حملة لاستخراج إعلاناتها: {len(parents)}", ""]
    for item in recovered:
        lines += [f"[منتج محتمل / {item['market']}] {item['title']}", item["source_url"],
                  "الدليل: تصنيف المحرك وشكل مسار المنصة؛ هوية الإعلان والمخزون غير مثبتين.", ""]
    for item in parents:
        lines += [f"[صفحة مصدر وليست إعلانًا / {item['market']}] {item['title']}",
                  item["source_url"], "تحتاج استخراج روابط الإعلانات الفردية؛ لا تُحسب فرصة.", ""]
    return "\n".join(lines) + "\n"
