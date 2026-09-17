"""Read-only source-page review inbox: a direct-looking URL is not a verified offer.

Keep source intelligence and excluded domains in the historical record. This
module does not fetch pages or declare a business legitimate: live source proof
must come from the existing bounded investigation pipeline.
"""
from __future__ import annotations

from collections import Counter
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

MARKETS = ("NO", "SE", "DE", "FR", "IT", "NL")
_EXCLUDED_DOMAINS = frozenset({"vinqa-grossiste.com"})
_GENERIC_SLUGS = frozenset({
    "all", "index", "search", "category", "categories", "collection",
    "collections", "catalog", "catalogue", "products", "product", "stock",
    "boxes", "box", "mystery-box", "restpartier", "clothing", "clothes",
    "fashion", "shoes", "footwear", "new", "sale", "wholesale",
})
_GENERIC_PATH_SEGMENTS = frozenset({
    "search", "category", "categories", "collection", "collections",
    "catalog", "catalogue", "pages", "landing", "lp", "shop-all",
    "product-category", "product-categorie", "recherche", "sok", "søk",
})


def _host(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def classify_url(url: str) -> str:
    """Return DIRECT (URL shape only), CAMPAIGN, EXCLUDED or UNKNOWN.

    DIRECT is never evidence that a page loaded, a seller is real, or stock exists.
    """
    try:
        parsed = urlsplit(url)
        host, path = (parsed.hostname or "").lower(), parsed.path.lower()
        parts = [part for part in path.strip("/").split("/") if part]
        if parsed.scheme not in {"http", "https"} or not host or not parts:
            return "UNKNOWN"
        if parsed.username or parsed.password:
            return "UNKNOWN"
        if any(_host(host, domain) for domain in _EXCLUDED_DOMAINS):
            return "EXCLUDED"
        if _host(host, "psauction.se") and path.startswith("/auction/"):
            return "CAMPAIGN"  # Parent auction is not its individual objects.
        if _host(host, "riegermann.de") and "/objekte/au-" in path:
            return "CAMPAIGN"
        if any(part in _GENERIC_PATH_SEGMENTS for part in parts):
            return "CAMPAIGN"
        if parts[-1] in _GENERIC_SLUGS:
            return "CAMPAIGN"
        if len(parts) >= 2 and parts[-2] in {"products", "product", "stock", "p"} and parts[-1] in _GENERIC_SLUGS:
            return "CAMPAIGN"
        direct = (
            _host(host, "auksjonen.no") and parts[0] == "auksjon" and len(parts) >= 2,
            _host(host, "finn.no") and (
                (len(parts) == 1 and parts[0].isdigit() and len(parts[0]) >= 7)
                or (len(parts) == 4 and parts[:3] == ["recommerce", "forsale", "item"] and parts[3].isdigit())
            ),
            _host(host, "blocket.se") and parts[:3] == ["recommerce", "forsale", "item"] and len(parts) == 4 and parts[3].isdigit(),
            _host(host, "klaravik.se") and parts[:2] == ["auktion", "produkt"] and len(parts) >= 3,
            _host(host, "blinto.se") and parts[0] == "auction" and len(parts) >= 2,
            _host(host, "grossist.se") and "parti" in parts and len(parts) >= 2,
            _host(host, "salzmann-restwaren.de") and parts[0] == "product" and len(parts) == 2,
            _host(host, "destockplus.com") and parts[0] == "acheter" and len(parts) >= 2 and parts[1].startswith("c-"),
            _host(host, "stockitaly24.com") and parts[0] == "products" and len(parts) == 2,
            _host(host, "friptadium.com") and parts[0] == "products" and len(parts) == 2,
            _host(host, "luxvintagewholesale.com") and "products" in parts and len(parts) >= 2,
            _host(host, "restposten.de") and parts[0] == "p" and len(parts) == 2,
            _host(host, "stocklots24.it") and len(parts) >= 2,
            _host(host, "bijuymoda.com") and "lotti-in-offerta-all-ingrosso" in parts and len(parts) >= 2,
            _host(host, "stockoutlet.it") and parts[0] == "stock" and len(parts) >= 2,
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
    # A real recorded redirect overrides the search-result URL. If it lands on
    # a generic page, NEVER resurrect the stale original as a direct offer.
    final = pending.get("final_url")
    if isinstance(final, str) and final.strip():
        final_role = classify_url(final)
        if final_role != "DIRECT":
            return None, "REDIRECT_TO_" + final_role
        original = pending.get("source_url") or row.get("canonical_url")
        if isinstance(original, str) and original.strip():
            old_host = urlsplit(original).hostname or ""
            new_host = urlsplit(final).hostname or ""
            if old_host.lower() != new_host.lower() and not (
                old_host.lower().removeprefix("www.") == new_host.lower().removeprefix("www.")
            ):
                return None, "CROSS_SITE_REDIRECT_UNVERIFIED"
        return final, "DIRECT"
    urls = [row.get("canonical_url"), pending.get("source_url"), *(row.get("source_urls") or [])]
    valid = [u for u in urls if isinstance(u, str) and u.strip()]
    for url in valid:
        if classify_url(url) == "DIRECT":
            return url, "DIRECT"
    roles = {classify_url(url) for url in valid}
    if "EXCLUDED" in roles:
        return None, "EXCLUDED_SOURCE"
    return None, "CAMPAIGN" if "CAMPAIGN" in roles else "UNKNOWN"


def _page_proof(row: dict, url: str) -> bool:
    """Use existing dated source investigation, not inferred page legitimacy."""
    pending = row.get("pending_investigation") or {}
    evidence = pending.get("evidence") or {}
    return bool(
        pending.get("status") == "VERIFIED_EXACT_LOT_CANDIDATE"
        and pending.get("last_investigated_at")
        and classify_url(pending.get("final_url") or pending.get("source_url") or "") == "DIRECT"
        and _url_key(pending.get("final_url") or pending.get("source_url")) == _url_key(url)
        and all(evidence.get(field) is True for field in (
            "item_specific_url_evidence", "domain_evidence", "inventory_evidence",
            "direct_sale_evidence", "price_evidence", "quantity_evidence",
        ))
        and str(evidence.get("source_listing_status") or "").upper() not in {"ENDED", "SOLD", "SOLD_OUT"}
    )


def build_queue(report: dict, memory: dict | None = None, batch_size: int = 10) -> dict:
    """Preserve direct-looking candidates without describing them as real stock."""
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
            held.append({"identity": identity, "title": row.get("title"), "reason": role,
                         "source_urls": row.get("source_urls") or []})
            stats["excluded_source" if role == "EXCLUDED_SOURCE" else "non_direct_or_uncertain"] += 1
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
        page_proven = _page_proof(row, url)
        stats["source_item_page_evidence" if page_proven else "url_shape_only_unverified"] += 1
        review.append({
            "identity": identity, "source_url": url, "title": row.get("title"),
            "market": row.get("market_code"), "sources": row.get("source_names") or [],
            "record_status": status, "stock_confidence": "UNVERIFIED",
            "page_type": "SOURCE_ITEM_PAGE_EVIDENCE" if page_proven else "DIRECT_URL_SHAPE_ONLY_UNVERIFIED",
            "site_identity_status": "UNVERIFIED",  # Neither HTTP 200 nor a product URL validates a business.
            "capture_timestamp": report.get("generated_at"),
            "source_last_investigated_at": pending.get("last_investigated_at"),
            "lot_quantity": lot_quantity, "price": None, "price_basis": None,
            "condition": None, "shipping": None, "seller_name": None, "seller_phone": None,
            "photos": [], "commercially_qualified": False,
            "source_detail_status": "EXACT_ITEM_VERIFIED" if page_proven else "POSSIBLE_DIRECT_LISTING_UNVERIFIED",
            "missing_evidence": row.get("missing_evidence") or [],
            "why_selected": ("Dated source page supplied item-specific evidence; live stock and site identity unverified"
                             if page_proven else "Direct-looking URL only; page, site identity and stock unverified"),
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
    lines = ["مراجعة روابط المنتجات — غير مؤكدة التوافر", "",
             f"السجلات: {counts['discovered_records']} | للمراجعة: {counts['direct_waiting_for_review']} | دفعة اليوم: {counts['daily_batch']} | الباقي: {counts['remaining']}",
             "DIRECT شكل رابط فقط؛ هوية الموقع والمخزون غير مؤكدين. صفحات الهبوط منفصلة.",
             "ACTIVE حالة سجل وليست تأكيد مخزون. لا تُحفظ قراراتك من هذا الملف وحده.", ""]
    for i, row in enumerate(queue["daily_batch"], 1):
        lines.extend((f"{i}. [{row['market']}] {row['title']}", row["source_url"],
                      f"نوع الصفحة: {row['page_type']} | هوية الموقع: غير موثقة | المخزون: غير مؤكد | القرار: غير مسجل", ""))
    return "\n".join(lines) + "\n"
