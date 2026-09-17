"""Read-only PS Auction parent-to-child discovery from literal source HTML anchors.

A source-linked item URL is a review lead, not evidence of live inventory,
seller identity or commercial suitability. A blocked/JS-only parent is unknown,
not an empty auction. No login, bids, purchases, contact or paid search.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit

from opportunity_engine.discovery.keyword_shadow_verification import fetch_public_page
from opportunity_engine.discovery.sweden_psauction import PSAUCTION_ITEM_PATH

MAX_PARENT_READS = 11
MAX_CHILDREN_PER_PARENT = 12
MAX_TOTAL_CHILDREN = 60
MAX_HTML_CHARS = 600_000
_UNHELPFUL = frozenset({"mer info", "visa objekt", "läs mer", "lägg bud", "bid", "more info"})


def _host(url: str) -> str:
    try:
        parsed = urlsplit(url)
        if parsed.scheme.lower() != "https" or parsed.username or parsed.password:
            return ""
        return (parsed.hostname or "").lower().removeprefix("www.").rstrip(".")
    except ValueError:
        return ""


def _parent_ok(url: str) -> bool:
    if _host(url) != "psauction.se":
        return False
    parts = urlsplit(url)
    segments = parts.path.strip("/").split("/")
    return (len(segments) == 3 and segments[0] == "auction" and
            segments[1].isdigit() and bool(segments[2]) and not parts.query and not parts.fragment)


def _child_url(href: str, parent_url: str) -> tuple[str, str] | None:
    absolute = urljoin(parent_url, href)
    if _host(absolute) != "psauction.se":
        return None
    parts = urlsplit(absolute)
    if parts.query or parts.fragment:
        return None
    match = PSAUCTION_ITEM_PATH.fullmatch(parts.path)
    if match is None:
        return None
    return "https://psauction.se" + parts.path.rstrip("/"), match.group("item_id")


class _ItemAnchors(HTMLParser):
    def __init__(self, parent_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.parent_url = parent_url
        self.active: tuple[str, str] | None = None
        self.words: list[str] = []
        self.found: list[tuple[str, str, str | None]] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip += 1
            return
        if self.skip:
            return
        attributes = {k.lower(): v for k, v in attrs}
        if tag == "a" and self.active is None:
            href = attributes.get("href")
            self.active = _child_url(href, self.parent_url) if href else None
            self.words = []
        elif tag == "img" and self.active is not None and attributes.get("alt"):
            self.words.append(attributes["alt"] or "")

    def handle_data(self, data: str) -> None:
        if self.active and not self.skip:
            self.words.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"} and self.skip:
            self.skip -= 1
            return
        if tag == "a" and self.active is not None:
            title = " ".join(" ".join(self.words).split())[:240]
            # "Mer info" is still a real item hyperlink. Keep its URL and
            # native ID without fabricating a descriptive item title.
            title = title if title and title.casefold() not in _UNHELPFUL else None
            self.found.append((*self.active, title))
            self.active = None
            self.words = []


def extract_child_anchors(html: str, parent_url: str) -> list[dict[str, Any]]:
    """Only literal source item hrefs: never construct URLs from object counts or IDs."""
    if not _parent_ok(parent_url) or not isinstance(html, str):
        return []
    parser = _ItemAnchors(parent_url)
    parser.feed(html[:MAX_HTML_CHARS])
    unique: dict[str, dict[str, Any]] = {}
    for url, native_id, title in parser.found:
        previous = unique.get(url)
        if previous is None or (title and not previous["title_from_parent_anchor"]):
            unique[url] = {"source_url": url, "native_item_id": native_id,
                           "title_from_parent_anchor": title,
                           "title_evidence": "PARENT_ANCHOR_TEXT" if title else "NOT_EXTRACTED"}
    return list(unique.values())


def extract_parent_children(balanced: Mapping[str, Any], *,
                            fetcher: Callable[[str], Any] = fetch_public_page,
                            limit: int = MAX_PARENT_READS,
                            checked_at: str | None = None) -> dict[str, Any]:
    """Inspect at most eleven known parent URLs, preserving failure and provenance."""
    if not 0 <= limit <= MAX_PARENT_READS:
        raise ValueError("parent read limit must be 0..11")
    timestamp = checked_at or datetime.now(timezone.utc).isoformat()
    source_parents = balanced.get("campaign_parents_for_child_extraction") or []
    attempted = 0
    parents: list[dict[str, Any]] = []
    children: list[dict[str, Any]] = []
    seen: set[str] = set()
    for original in source_parents:
        if not isinstance(original, dict):
            continue
        parent = dict(original)
        url = str(parent.get("source_url") or "")
        parent["source_last_checked_at"] = None
        parent["children_found_in_fetched_html"] = 0
        parent["child_listings_extracted"] = False
        if not _parent_ok(url):
            parent["child_extraction_status"] = "INVALID_PARENT_URL_NOT_FETCHED"
        elif attempted >= limit:
            parent["child_extraction_status"] = "NOT_CHECKED_BOUNDED_LIMIT"
        else:
            attempted += 1
            parent["source_last_checked_at"] = timestamp
            try:
                page = fetcher(url)
            except Exception as exc:
                parent["child_extraction_status"] = "FETCH_FAILED_UNVERIFIED"
                parent["fetch_error_type"] = type(exc).__name__
            else:
                final = str(getattr(page, "final_url", "") or "")
                parent["http_status"] = getattr(page, "status_code", None)
                parent["source_final_url"] = final
                if not getattr(page, "ok", False):
                    parent["child_extraction_status"] = "FETCH_FAILED_UNVERIFIED"
                    parent["fetch_error_type"] = str(getattr(page, "error", "") or "HTTP_NOT_READABLE")[:100]
                elif final.rstrip("/") != url.rstrip("/"):
                    parent["child_extraction_status"] = "REDIRECTED_PARENT_NOT_MINED"
                else:
                    found = extract_child_anchors(str(getattr(page, "raw_html", "") or ""), url)
                    parent["children_found_in_fetched_html"] = len(found)
                    parent["child_extraction_status"] = (
                        "SOURCE_CHILD_ANCHORS_EXTRACTED_URLS_UNVERIFIED" if found
                        else "NO_NATIVE_ITEM_ANCHORS_FOUND_UNVERIFIED"
                    )
                    for child in found[:MAX_CHILDREN_PER_PARENT]:
                        if len(children) >= MAX_TOTAL_CHILDREN or child["source_url"] in seen:
                            continue
                        seen.add(child["source_url"])
                        parent["child_listings_extracted"] = True
                        children.append({
                            **child, "identity": "psauction-item:" + child["native_item_id"],
                            "parent_url": url, "market": "SE", "discovered_from_parent_at": timestamp,
                            "role": "SOURCE_LINKED_ITEM_URL_NEEDS_INDIVIDUAL_PAGE_REVIEW",
                            "item_page_verified": False, "stock_verified": False,
                            "seller_verified": False, "commercially_qualified": False,
                            "operator_decision": None,
                        })
        parents.append(parent)
    return {
        "schema_version": "psauction-child-links-v1", "read_only": True,
        "captured_at": timestamp, "max_parent_reads": limit,
        "counts": {
            "parents_total": len(parents), "parents_attempted": attempted,
            "parents_with_child_links": sum(p.get("children_found_in_fetched_html", 0) > 0 for p in parents),
            "parent_fetch_failed": sum(p.get("child_extraction_status") == "FETCH_FAILED_UNVERIFIED" for p in parents),
            "parent_no_anchors_unverified": sum(p.get("child_extraction_status") == "NO_NATIVE_ITEM_ANCHORS_FOUND_UNVERIFIED" for p in parents),
            "child_links_extracted_unverified": len(children),
        },
        "parents": parents, "child_item_url_leads": children,
        "source_link_is_page_or_stock_proof": False,
        "automatic_purchase": False, "automatic_bid": False,
        "automatic_contact": False, "paid_search_requests": 0,
    }


def readable_child_links(result: Mapping[str, Any]) -> str:
    counts = result["counts"]
    lines = ["استخراج روابط إعلانات PS Auction من صفحات المزادات (ليست فرصًا مؤكدة)",
             f"فحص صفحات أصل: {counts['parents_attempted']}/{counts['parents_total']}؛ "
             f"روابط إعلانات مستخرجة: {counts['child_links_extracted_unverified']}؛ "
             f"فشل فتح: {counts['parent_fetch_failed']}؛ بلا روابط ظاهرة: {counts['parent_no_anchors_unverified']}.",
             "روابط العناصر أدناه مأخوذة من روابط الصفحة الأصلية؛ هوية الإعلان والمخزون والبائع لم تُتحقق بعد."]
    for item in result["child_item_url_leads"][:15]:
        lines.append(f"- {item['title_from_parent_anchor'] or 'عنوان غير مستخرج'}: {item['source_url']}")
    if len(result["child_item_url_leads"]) > 15:
        lines.append("روابط إضافية موجودة في ملف JSON؛ لم تُحذف من التقرير.")
    return "\n".join(lines) + "\n"
