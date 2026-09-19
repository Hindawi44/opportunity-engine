"""Operator auction-only PRESENTATION policy; never delete discovery or review history.

An approved platform URL is an allowed source to investigate, NOT a guarantee
of seller legitimacy, lot condition, auction availability or profitability.
Advertisements, wholesale product pages and classified listings remain in the
underlying historic checkpoint/SQLite but cannot enter the human review inbox.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from urllib.parse import urlsplit

from opportunity_engine.human_listing_review_queue import MARKETS

OPEN_STATUSES = frozenset({"INPROGRESS", "OPEN", "ACTIVE"})
MAX_STATUS_AGE = timedelta(hours=24)
_ID = re.compile(r"[0-9]{4,}")
_BLINTO_ITEM = re.compile(r"[a-z0-9-]+-[0-9]{3,}-[0-9]{3,}", re.I)


def auction_route(url: object) -> str | None:
    """Strict, exact-host public auction routes. Parent != individual lot."""
    if not isinstance(url, str):
        return None
    try:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in {None, 443}:
            return None
        host = (parsed.hostname or "").lower()
        parts = parsed.path.strip("/").split("/")
        if parsed.query or parsed.fragment or any(not part for part in parts):
            return None
        if host in {"auksjonen.no", "www.auksjonen.no", "ny.auksjonen.no"}:
            if len(parts) == 4 and parts[0] == "auksjon" and parts[1] in {"torget", "overskuddsvarer"} and _ID.fullmatch(parts[3]):
                return "AUKSJONEN_LOT"
        if host in {"klaravik.se", "www.klaravik.se"}:
            if len(parts) == 3 and parts[:2] == ["auktion", "produkt"] and parts[2] not in {"all", "index", "search"}:
                return "KLARAVIK_LOT"
        if host in {"blinto.se", "www.blinto.se"}:
            if len(parts) == 2 and parts[0] == "auction" and _BLINTO_ITEM.fullmatch(parts[1]):
                return "BLINTO_LOT"
        if host in {"psauction.se", "www.psauction.se"}:
            if len(parts) == 4 and parts[:2] == ["item", "view"] and parts[2].isdigit() and parts[3]:
                return "PSAUCTION_LOT"
            if len(parts) == 3 and parts[0] == "auction" and parts[1].isdigit() and parts[2]:
                return "PSAUCTION_PARENT_NAVIGATION_ONLY"
        if host in {"riegermann.de", "www.riegermann.de"}:
            if len(parts) == 4 and parts[:2] == ["de", "l"] and parts[2].isdigit() and parts[3]:
                return "RIEGERMANN_LOT"
            if len(parts) == 4 and parts[:2] == ["de", "objekte"] and re.fullmatch(r"au-[0-9]+", parts[2]) and parts[3]:
                return "RIEGERMANN_PARENT_NAVIGATION_ONLY"
    except ValueError:
        return None
    return None


def _round_robin(rows: list[dict], limit: int = 10) -> list[dict]:
    buckets = {market: [row for row in rows if row.get("market") == market] for market in MARKETS}
    for row in rows:
        if row.get("market") not in buckets:
            buckets.setdefault(row.get("market"), []).append(row)
    chosen: list[dict] = []
    while len(chosen) < limit and any(buckets.values()):
        for market in buckets:
            if buckets[market] and len(chosen) < limit:
                chosen.append(buckets[market].pop(0))
    return chosen


def _refresh(queue: dict) -> None:
    review = queue["review_queue"]
    queue["daily_batch"] = _round_robin(review)
    queue["counts"]["direct_waiting_for_review"] = len(review)
    queue["counts"]["daily_batch"] = len(queue["daily_batch"])
    queue["counts"]["remaining"] = len(review) - len(queue["daily_batch"])


def restrict_to_auction_sources(queue: dict) -> dict:
    """Remove *all* non-auction links from live review AND held presentation.

    The source checkpoint, SQLite, prior operator STUDY/DELETE/LATER, and source
    exclusion policy are untouched. Only named, exact auction lot routes enter
    the candidate inbox; parent auction URLs are navigation-only technical leads.
    """
    before_review = list(queue.get("review_queue") or [])
    before_held = list(queue.get("held_separately") or [])
    selected = []
    for item in before_review:
        route = auction_route(item.get("source_url"))
        if route and route.endswith("_LOT"):
            selected.append({**item, "auction_platform_route": route,
                             "opportunity_confirmed": False})
    kept_held = []
    for item in before_held:
        candidates = [item.get("url"), item.get("source_url"), *(item.get("source_urls") or [])]
        routes = [(url, auction_route(url)) for url in candidates if isinstance(url, str)]
        match = next(((url, role) for url, role in routes if role), None)
        if match and str(item.get("reason") or "") != "EXCLUDED_SOURCE":
            kept_held.append({**item, "auction_platform_route": match[1],
                              "opportunity_confirmed": False})
    queue["review_queue"] = selected
    queue["held_separately"] = kept_held
    counts = queue["counts"]
    counts["review_policy"] = "AUCTION_ONLY_SOURCE_NATIVE_STATUS_REQUIRED_V1"
    counts["advertisements_and_nonauction_pages_hidden_from_review"] = (
        len(before_review) + len(before_held) - len(selected) - len(kept_held)
    )
    counts["historical_discovery_retained"] = counts.get("discovered_records", 0)
    counts["original_source_report_commercially_qualified"] = counts.get("commercially_qualified", 0)
    counts["commercially_qualified"] = 0  # No unrelated wholesale score may leak into auction output.
    _refresh(queue)
    return queue


def _time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except ValueError:
        return None


def require_dated_open_auction(queue: dict, *, now: datetime | None = None) -> dict:
    """Open source-native evidence, not page shape or ACTIVE search status.

    Absent/stale/conflicting evidence is held as an auction lead; do not infer
    ENDED, SOLD or operator DELETE. For non-Auksjonen, require additionally the
    existing stringent individual item-page verifier to avoid URL-only claims.
    """
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must have timezone")
    current = current.astimezone(timezone.utc)
    kept = []
    for item in queue["review_queue"]:
        evidence = item.get("source_status_evidence") or {}
        captured = _time(evidence.get("captured_at"))
        ends = _time(evidence.get("ends_at"))
        route = auction_route(item.get("source_url"))
        open_status = str(evidence.get("status") or "").upper() in OPEN_STATUSES
        same_source = str(evidence.get("source_url") or "").rstrip("/") == str(item.get("source_url") or "").rstrip("/")
        dated = bool(captured and captured <= current and current - captured <= MAX_STATUS_AGE)
        future_end = bool(ends and captured and ends > captured and ends > current)
        exact_item = (route == "AUKSJONEN_LOT" or item.get("source_detail_status") == "EXACT_ITEM_VERIFIED")
        if open_status and same_source and dated and future_end and exact_item:
            item["auction_status"] = "SOURCE_REPORTED_OPEN_AT_CAPTURE_NOT_COMMERCIAL_PROOF"
            item["opportunity_confirmed"] = False
            kept.append(item)
        else:
            queue["held_separately"].append({
                "identity": item.get("identity"), "title": item.get("title"),
                "url": item.get("source_url"), "auction_platform_route": route,
                "reason": "AUCTION_LIVE_STATUS_NOT_VERIFIED_NOT_OPERATOR_DELETE",
                "opportunity_confirmed": False,
            })
    queue["review_queue"] = kept
    queue["counts"]["auction_native_open_evidence"] = len(kept)
    queue["counts"]["auction_unverified_held"] = sum(
        row.get("reason") == "AUCTION_LIVE_STATUS_NOT_VERIFIED_NOT_OPERATOR_DELETE"
        for row in queue["held_separately"]
    )
    _refresh(queue)
    return queue


def readable_auction_review(queue: dict) -> str:
    counts = queue["counts"]
    lines = ["مزادات فقط — حالة من مصدر المزاد بتاريخ محدد؛ ليست توصية شراء", "",
             f"السجلات التاريخية محفوظة: {counts['discovered_records']} | صفحات غير المزاد محجوبة عن التقرير: {counts['advertisements_and_nonauction_pages_hidden_from_review']}",
             f"مزادات بحالة فتح موثقة من المصدر: {counts['direct_waiting_for_review']} | دفعة المراجعة: {counts['daily_batch']} | مزادات معلّقة لغياب الدليل: {counts['auction_unverified_held']}",
             "صفحات المنتجات والإعلانات التجارية والمبوبة ليست فرصًا هنا. الموقع المعروف لا يثبت البائع أو البضاعة أو الربح.",
             "لا شراء أو مزايدة أو اتصال أو دفع تلقائي. صفر نتائج مقبول.", ""]
    for index, item in enumerate(queue["daily_batch"], 1):
        evidence = item.get("source_status_evidence") or {}
        lines.extend((f"{index}. [{item.get('market')}] {item.get('title')}",
                      str(item.get("source_url") or ""),
                      f"المصدر: {evidence.get('source') or 'UNKNOWN'} | حالته: {evidence.get('status') or 'UNKNOWN'} | التقط: {evidence.get('captured_at') or 'UNKNOWN'} | ينتهي وفق المصدر: {evidence.get('ends_at') or 'UNKNOWN'}",
                      "الحالة لحظة الالتقاط فقط؛ تفاصيل الدفعة والمخزون والنقل غير مؤكدة.", ""))
    return "\n".join(lines) + "\n"
