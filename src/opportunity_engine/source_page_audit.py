"""Bounded read-only source-page audit of the human review batch.

A URL shape and an HTTP 200 are not proof of an individual listing, inventory,
stock, company registration, or seller legitimacy. The only positive item-page
identity in this module comes from a Product JSON-LD record anchored to the
fetched final URL and containing a source-supplied productID or SKU. Even that
identity does not verify a fixed bulk lot or availability.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from html import unescape
import json
import re
from typing import Any, Callable, Mapping
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from opportunity_engine.discovery.keyword_shadow_verification import fetch_public_page
from opportunity_engine.human_listing_review_queue import classify_url

MAX_AUDIT_PAGES = 10
_SCRIPT = re.compile(r"<script\b([^>]*)>(.*?)</script\s*>", re.IGNORECASE | re.DOTALL)
_LD_TYPE = re.compile(r"\btype\s*=\s*(['\"])application/ld\+json\1", re.IGNORECASE)
_TRACKING = frozenset({"fbclid", "gclid"})
_SOLD_OUT = frozenset({"outofstock", "soldout", "discontinued"})


def _canonical(url: str) -> str:
    try:
        p = urlsplit(str(url or "").strip())
        if p.scheme.lower() not in {"http", "https"} or not p.hostname:
            return ""
        query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                 if not k.lower().startswith("utm_") and k.lower() not in _TRACKING]
        return urlunsplit(("https", p.hostname.lower().removeprefix("www."),
                           p.path.rstrip("/") or "/", "&".join(f"{k}={v}" for k, v in sorted(query)), ""))
    except ValueError:
        return ""


def _product_objects(payload: Any):
    """Traverse only JSON-LD object/list/@graph nodes, not arbitrary nested offers."""
    if isinstance(payload, list):
        for node in payload[:50]:
            yield from _product_objects(node)
    elif isinstance(payload, dict):
        kinds = payload.get("@type") or []
        if isinstance(kinds, str):
            kinds = [kinds]
        if isinstance(kinds, list) and any(str(kind).split("/")[-1].casefold() == "product" for kind in kinds):
            yield payload
        graph = payload.get("@graph")
        if isinstance(graph, list):
            yield from _product_objects(graph[:50])


def _url_matches(value: Any, final_url: str) -> bool:
    if not isinstance(value, str) or not value.strip().startswith(("https://", "http://")):
        return False
    return _canonical(value) == _canonical(final_url)


def _source_product(raw_html: str, final_url: str) -> dict[str, Any] | None:
    if not raw_html or classify_url(final_url) != "DIRECT":
        return None
    matched: list[dict[str, Any]] = []
    for attrs, script in _SCRIPT.findall(raw_html[:600_000]):
        if not _LD_TYPE.search(attrs) or len(script) > 200_000:
            continue
        try:
            payload = json.loads(unescape(script.strip()))
        except (ValueError, TypeError):
            continue
        for product in _product_objects(payload):
            # A product in the navigation, recommendation carousel, or an
            # ItemList must not verify the page. Demand an exact source URL.
            if not any(_url_matches(product.get(key), final_url) for key in ("url", "@id")):
                continue
            identifier = product.get("productID") or product.get("sku")
            if not isinstance(identifier, (str, int)) or not str(identifier).strip():
                continue
            matched.append({"id": str(identifier).strip()[:120], "name": str(product.get("name") or "")[:250],
                            "offers": product.get("offers")})
    identifiers = {item["id"] for item in matched}
    return matched[0] if len(identifiers) == 1 and matched else None


def _source_sold_out(offers: Any, final_url: str) -> bool:
    # A global stock flag cannot identify a specific ?variant= product selection.
    if any(k.lower() in {"variant", "variation", "sku", "attribute_pa_size", "size"}
           for k, _ in parse_qsl(urlsplit(final_url).query)):
        return False
    offers = offers if isinstance(offers, list) else [offers]
    statuses = []
    for offer in offers:
        if not isinstance(offer, dict):
            return False
        availability = offer.get("availability")
        if not isinstance(availability, str):
            return False
        statuses.append(availability.rstrip("/").rsplit("/", 1)[-1].casefold())
    return bool(statuses) and all(value in _SOLD_OUT for value in statuses)


def audit_review_batch(queue: Mapping[str, Any], *,
                       fetcher: Callable[[str], Any] = fetch_public_page,
                       limit: int = MAX_AUDIT_PAGES,
                       checked_at: str | None = None) -> dict[str, Any]:
    """Audit at most ten displayed URLs; preserve unreadable/unknown records.

    Explicit source-reported sold-out records and redirects to non-item pages
    leave today's review inbox but remain in held history. No fetch result
    asserts the legal identity of a seller or a ready-to-purchase opportunity.
    """
    if not 0 <= limit <= MAX_AUDIT_PAGES:
        raise ValueError("source-page audit limit must be 0..10")
    result = deepcopy(dict(queue))
    items = result.get("review_queue") or []
    batch = result.get("daily_batch") or []
    held = result.setdefault("held_separately", [])
    counts = result.setdefault("counts", {})
    timestamp = checked_at or datetime.now(timezone.utc).isoformat()
    audits = Counter()
    remove: set[str] = set()
    checked: dict[str, dict[str, Any]] = {}
    for item in batch[:limit]:
        url = str(item.get("source_url") or "")
        if not url or url in checked:
            continue
        audits["page_audit_attempted"] += 1
        try:
            page = fetcher(url)
        except Exception as exc:  # Bounded source failure never becomes stock evidence.
            checked[url] = {"source_page_check_status": "FETCH_FAILED_UNVERIFIED",
                            "source_page_error": type(exc).__name__, "source_last_checked_at": timestamp}
            audits["page_audit_fetch_failed"] += 1
            continue
        proof = {"source_last_checked_at": timestamp,
                 "source_page_http_status": getattr(page, "status_code", None),
                 "source_page_final_url": getattr(page, "final_url", url) or url,
                 "site_identity_status": "UNVERIFIED", "stock_confidence": "UNVERIFIED"}
        if not getattr(page, "ok", False):
            proof["source_page_check_status"] = "FETCH_FAILED_UNVERIFIED"
            proof["source_page_error"] = str(getattr(page, "error", None) or "UNAVAILABLE")[:160]
            audits["page_audit_fetch_failed"] += 1
        else:
            final = proof["source_page_final_url"]
            orig_host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
            final_host = (urlsplit(final).hostname or "").lower().removeprefix("www.")
            if orig_host != final_host or classify_url(final) != "DIRECT":
                proof["source_page_check_status"] = "REDIRECT_NON_DIRECT_OR_CROSS_SITE_UNVERIFIED"
                remove.add(url)
                audits["page_audit_redirect_held"] += 1
            else:
                product = _source_product(str(getattr(page, "raw_html", "") or ""), final)
                if product is None:
                    proof["source_page_check_status"] = "READABLE_ITEM_IDENTITY_UNPROVEN"
                    audits["page_audit_identity_unproven"] += 1
                else:
                    proof["source_page_check_status"] = "SOURCE_PRODUCT_ID_EVIDENCE"
                    proof["source_product_identifier"] = product["id"]
                    proof["source_product_title"] = product["name"]
                    proof["page_type"] = "SOURCE_PRODUCT_ID_EVIDENCE_NOT_FIXED_LOT"
                    proof["source_detail_status"] = "SOURCE_PRODUCT_ID_EVIDENCE_ONLY"
                    audits["page_audit_product_id_evidence"] += 1
                    if _source_sold_out(product["offers"], final):
                        proof["source_page_check_status"] = "SOURCE_REPORTED_SOLD_OUT"
                        proof["stock_confidence"] = "SOURCE_REPORTED_SOLD_OUT"
                        remove.add(url)
                        audits["page_audit_sold_out_held"] += 1
        checked[url] = proof
    result["review_queue"] = []
    for item in items:
        url = str(item.get("source_url") or "")
        item.update(checked.get(url, {}))
        if url in remove:
            held.append({"identity": item.get("identity"), "title": item.get("title"),
                         "url": url, "reason": item["source_page_check_status"],
                         "source_last_checked_at": timestamp})
        else:
            result["review_queue"].append(item)
    result["daily_batch"] = [row for row in batch if row.get("source_url") not in remove]
    counts["direct_waiting_for_review"] = len(result["review_queue"])
    counts["daily_batch"] = len(result["daily_batch"])
    counts["remaining"] = len(result["review_queue"]) - len(result["daily_batch"])
    counts["url_shape_only_unverified"] = sum(
        row.get("page_type") == "DIRECT_URL_SHAPE_ONLY_UNVERIFIED" for row in result["review_queue"])
    counts["source_item_page_evidence"] = sum(
        row.get("page_type") == "SOURCE_ITEM_PAGE_EVIDENCE" for row in result["review_queue"])
    counts.update({key: audits[key] for key in (
        "page_audit_attempted", "page_audit_fetch_failed", "page_audit_redirect_held",
        "page_audit_identity_unproven", "page_audit_product_id_evidence", "page_audit_sold_out_held")})
    result["source_page_audit"] = {"checked_at": timestamp, "attempted": audits["page_audit_attempted"],
                                   "limit": limit, "read_only": True,
                                   "source_product_id_is_stock_proof": False,
                                   "site_identity_verified": False}
    return result
