"""Read-only direct-source review inbox; ACTIVE is never stock proof."""
from __future__ import annotations

from collections import Counter
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

MARKETS = ("NO", "SE", "DE", "FR", "IT", "NL")


def _host(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def classify_url(url: str) -> str:
    """Return DIRECT, CAMPAIGN or UNKNOWN; ambiguous URLs are not deals."""
    try:
        parsed = urlsplit(url)
        host, path = (parsed.hostname or "").lower(), parsed.path.lower()
        if parsed.scheme not in {"http", "https"} or not host or not path.strip("/"):
            return "UNKNOWN"
        if parsed.username or parsed.password:
            return "UNKNOWN"
        if _host(host, "psauction.se") and path.startswith("/auction/"):
            return "CAMPAIGN"
        if _host(host, "riegermann.de") and ("/objekte/au-" in path or path.startswith("/de/objekte/au-")):
            return "CAMPAIGN"
        if path.strip("/") in {"search", "category", "categories", "restpartier", "products", "auktioner"}:
            return "CAMPAIGN"
        direct = (
            _host(host, "auksjonen.no") and path.startswith("/auksjon/") and not path.startswith("/auksjon/auktion/"),
            _host(host, "finn.no") and path.startswith("/recommerce/forsale/item/"),
            _host(host, "blocket.se") and path.startswith("/recommerce/forsale/item/"),
            _host(host, "klaravik.se") and path.startswith("/auktion/produkt/"),
            _host(host, "blinto.se") and path.startswith("/auction/") and len(path.strip("/").split("/")) >= 2,
            _host(host, "grossist.se") and "/parti/" in path,
            _host(host, "salzmann-restwaren.de") and path.startswith("/product/"),
            _host(host, "destockplus.com") and path.startswith("/acheter/c-"),
            _host(host, "stockitaly24.com") and path.startswith("/products/"),
            _host(host, "vinqa-grossiste.com") and path.startswith("/products/"),
            _host(host, "friptadium.com") and path.startswith("/products/"),
            _host(host, "luxvintagewholesale.com") and "/products/" in path,
            _host(host, "restposten.de") and path.startswith("/p/"),
            _host(host, "stocklots24.it") and len(path.strip("/").split("/")) >= 2,
            _host(host, "bijuymoda.com") and "/lotti-in-offerta-all-ingrosso/" in path,
            _host(host, "stockoutlet.it") and path.startswith("/stock/"),
        )
        return "DIRECT" if any(direct) else "UNKNOWN"
    except (TypeError, ValueError):
        return "UNKNOWN"


def _url_key(url: str) -> str:
    parsed = urlsplit(url)
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
                           if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}))
    return urlunsplit((parsed.scheme.lower(), (parsed.hostname or "").lower(), parsed.path.rstrip("/"), query, ""))


def _direct_url(row: dict) -> tuple[str | None, str]:
    pending = row.get("pending_investigation") or {}
    urls = [row.get("canonical_url"), pending.get("final_url"), pending.get("source_url"), *(row.get("source_urls") or [])]
    valid = [u for u in urls if isinstance(u, str) and u.strip()]
    for u in valid:
        if classify_url(u) == "DIRECT":
            return u, "DIRECT"
    return None, "CAMPAIGN" if any(classify_url(u) == "CAMPAIGN" for u in valid) else "UNKNOWN"


def build_queue(report: dict, memory: dict | None = None, batch_size: int = 10) -> dict:
    """Preserve all distinct source-direct records, independent of commercial gate."""
    memory = memory or {}
    deleted = set(memory.get("deleted_ids") or [])
    studying = {r["opportunity_id"] for r in memory.get("study", [])}
    deferred = {r["opportunity_id"] for r in memory.get("later", [])}
    rows = report.get("deduplicated_opportunities") or []
    review, held, seen = [], [], set()
    stats = Counter()
    for row in rows:
        identity = row.get("opportunity_identity") or ""
        url, role = _direct_url(row)
        status = row.get("listing_status") or "UNRESOLVED"
        if not url:
            held.append({"identity": identity, "title": row.get("title"), "reason": role, "source_urls": row.get("source_urls") or []})
            stats["non_direct_or_uncertain"] += 1
            continue
        if status in {"ENDED", "HISTORICAL"}:
            held.append({"identity": identity, "url": url, "reason": "SOURCE_RECORD_" + status})
            stats["historical_or_ended"] += 1
            continue
        key = _url_key(url)
        if key in seen:
            stats["duplicate_urls"] += 1
            continue
        seen.add(key)
        if identity in deleted:
            stats["operator_deleted"] += 1
            continue
        if identity in studying:
            stats["in_study_memory"] += 1
            continue
        if identity in deferred:
            stats["deferred"] += 1
            continue
        pending = row.get("pending_investigation") or {}
        evidence = pending.get("evidence_enrichment") or {}
        q = evidence.get("validated_quantity") if evidence.get("status") == "VALIDATED_FIELDS" else None
        lot_quantity = q if isinstance(q, dict) and q.get("lot_size_proven") is True else None
        review.append({
            "identity": identity, "source_url": url, "title": row.get("title"),
            "market": row.get("market_code"), "sources": row.get("source_names") or [],
            "record_status": status, "stock_confidence": "UNVERIFIED",
            "capture_timestamp": report.get("generated_at"),
            "source_last_investigated_at": pending.get("last_investigated_at"),
            "lot_quantity": lot_quantity, "price": None, "price_basis": None,
            "condition": None, "shipping": None, "seller_name": None, "seller_phone": None,
            "photos": [], "commercially_qualified": False,
            "source_detail_status": "POSSIBLE_DIRECT_LISTING_UNVERIFIED",
            "missing_evidence": row.get("missing_evidence") or [],
            "why_selected": "Source-direct URL; awaiting operator review, not a stock or profit claim",
        })
    buckets = {m: [x for x in review if x["market"] == m] for m in MARKETS}
    for x in review:
        if x["market"] not in buckets:
            buckets.setdefault(x["market"], []).append(x)
    batch = []
    while len(batch) < batch_size and any(buckets.values()):
        for market in buckets:
            if buckets[market] and len(batch) < batch_size:
                batch.append(buckets[market].pop(0))
    return {
        "schema_version": "human-listing-review-queue-v1",
        "production_connected": False, "choices_persisted_by_this_export": False,
        "capture_timestamp": report.get("generated_at"),
        "counts": {"discovered_records": len(rows), "direct_waiting_for_review": len(review),
                   "daily_batch": len(batch), "remaining": len(review) - len(batch), **dict(stats),
                   "commercially_qualified": report.get("commercially_qualified_count", 0)},
        "daily_batch": batch, "review_queue": review, "held_separately": held,
        "study_memory": memory.get("study") or [], "deferred_memory": memory.get("later") or [],
        "automatic_contact": False, "automatic_bid": False,
        "automatic_purchase": False, "automatic_payment": False,
    }


def readable_text(queue: dict) -> str:
    counts = queue["counts"]
    lines = ["مراجعة روابط المنتجات — غير مؤكدة التوافر", "", f"السجلات: {counts['discovered_records']} | للمراجعة: {counts['direct_waiting_for_review']} | دفعة اليوم: {counts['daily_batch']} | الباقي: {counts['remaining']}", "ACTIVE حالة سجل وليست تأكيد مخزون. لا تُحفظ قراراتك من هذا الملف وحده.", ""]
    for i, r in enumerate(queue["daily_batch"], 1):
        lines.extend((f"{i}. [{r['market']}] {r['title']}", r["source_url"], "المخزون: غير مؤكد | الاسم والهاتف: غير موثقين في التقرير | القرار: غير مسجل", ""))
    return "\n".join(lines) + "\n"