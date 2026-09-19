"""Bounded, free, read-only Norwegian public auction item discovery.

This route deliberately does not use legacy clothing/domain/commercial qualification.
An indexed company event or marketplace category page never becomes a sale card.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from opportunity_engine.discovery.auksjonen_exact_item_verification import (
    fetch_auksjonen_item_page,
    parse_auksjonen_item_page,
)
from opportunity_engine.discovery.auksjonen_public_api_adapter import build_public_item_url

API_URL = "https://ny.auksjonen.no/api/category-search/search"
ACTIVE = frozenset({"ACTIVE", "INPROGRESS", "OPEN"})
MAX_PAGE_BYTES = 2_000_000
END_MARKER = re.compile(r"auksjonen er avsluttet", re.IGNORECASE)


def fetch_page(url: str) -> Mapping[str, Any]:
    parts = urlparse(url)
    if parts.scheme != "https" or parts.netloc != "ny.auksjonen.no" or parts.path != "/api/category-search/search":
        raise ValueError("Only the public Norwegian Auksjonen category search is allowed")
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "OpportunityEngine/NO-Direct-Sales-1.0"})
    with urlopen(req, timeout=15) as response:  # noqa: S310 - exact allowlisted HTTPS API
        if urlparse(response.geturl()).netloc != "ny.auksjonen.no":
            raise RuntimeError("API redirected to another host")
        if response.status != 200:
            raise RuntimeError(f"API HTTP {response.status}")
        raw = response.read(MAX_PAGE_BYTES + 1)
    if len(raw) > MAX_PAGE_BYTES:
        raise RuntimeError("API response too large")
    obj = json.loads(raw)
    if not isinstance(obj, dict) or not isinstance(obj.get("items"), list):
        raise RuntimeError("No public item array: broad API not validated")
    return obj


def _price(item: Mapping[str, Any], key: str) -> float | None:
    try:
        n = float(item[key])
    except (KeyError, TypeError, ValueError):
        return None
    return n if 0 <= n < 1_000_000_000 else None


def _candidate(item: Mapping[str, Any], *, now: datetime) -> dict[str, Any] | None:
    try:
        object_id = int(item["objectId"])
        expiry = datetime.fromtimestamp(float(item["endTime"]) / 1000, tz=timezone.utc)
    except (KeyError, TypeError, ValueError, OverflowError, OSError):
        return None
    title = " ".join(str(item.get("title") or "").split())
    if (object_id <= 0 or not title or len(title) > 300 or expiry <= now
            or str(item.get("status") or "").upper() not in ACTIVE
            or bool(item.get("bidExpired"))):
        return None
    country = str(item.get("countryCode") or item.get("country") or "").strip().upper()
    if country and country not in {"NO", "NOR", "NORWAY", "NORGE"}:
        return None
    # No clothing filter, no expensive intelligence or domain score.
    return {
        "object_id": object_id,
        "title": title,
        "url": build_public_item_url(title, object_id),
        "asset_type": title,
        "location": str(item.get("city") or item.get("zipCode") or "").strip() or None,
        "current_bid_nok": _price(item, "currentBidAmount"),
        "buy_now_nok": _price(item, "buyNowPrice"),
        "start_price_nok": _price(item, "startPrice"),
        "ends_at": expiry.isoformat(),
    }


def discover(
    *,
    max_pages: int = 2,
    max_cards: int = 10,
    page_loader: Callable[[str], Mapping[str, Any]] = fetch_page,
    item_loader: Callable[[str], tuple[str, str, int, str]] = fetch_auksjonen_item_page,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not 1 <= max_pages <= 2 or not 1 <= max_cards <= 10:
        raise ValueError("Search bounds exceeded")
    stamp = now or datetime.now(timezone.utc)
    cards: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    seen: set[int] = set()
    pages_read = 0
    candidates = 0
    for page in range(max_pages):
        url = API_URL + "?" + urlencode({"from": page * 30 + 1, "to": page * 30 + 30,
                                         "asc": "true", "orderBy": "endTime"})
        try:
            payload = page_loader(url)
            items = payload.get("items")
            if not isinstance(items, list):
                raise RuntimeError("Missing exact-item search results")
        except Exception as exc:
            failures.append({"stage": "search", "reason": f"{type(exc).__name__}: {exc}"})
            break
        pages_read += 1
        for raw in items:
            if not isinstance(raw, Mapping):
                continue
            candidate = _candidate(raw, now=stamp)
            if candidate is None or candidate["object_id"] in seen:
                continue
            seen.add(candidate["object_id"])
            candidates += 1
            if len(cards) >= max_cards:
                break
            try:
                html, final_url, _, _ = item_loader(candidate["url"])
                if END_MARKER.search(html):
                    raise RuntimeError("Auction page says it has ended")
                if re.search(r"<h1\b", html, flags=re.I) is None:
                    raise RuntimeError("No product heading on exact item page")
                if urlparse(final_url).path.rstrip("/").split("/")[-1] != str(candidate["object_id"]):
                    raise RuntimeError("Auction identity changed")
                evidence = parse_auksjonen_item_page(html)
                candidate.update({
                    "url": final_url,
                    "asset_type": evidence.get("title") or candidate["title"],
                    "location": candidate["location"] or evidence.get("source_city"),
                    "status": "ACTIVE_VERIFIED_AT_CHECK",
                    "verified_at": stamp.isoformat(),
                })
                cards.append(candidate)
            except Exception as exc:
                failures.append({"stage": "item", "object_id": str(candidate["object_id"]),
                                 "reason": f"{type(exc).__name__}: {exc}"})
        if len(cards) >= max_cards or len(items) < 30:
            break
    return {
        "scope": "NO_ONLY_ALL_ASSETS", "captured_at": stamp.isoformat(),
        "requested_cards": max_cards, "verified_count": len(cards),
        "pages_read": pages_read, "distinct_active_api_candidates": candidates,
        "cards": cards, "failures": failures,
        "missing_count": max_cards - len(cards),
        "paid_api_requests": 0, "estimated_external_api_cost_usd": 0.0,
        "automatic_contact": False, "automatic_bid": False,
        "automatic_purchase": False, "automatic_payment": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Free Norway all-asset exact auction listings")
    parser.add_argument("--output-dir", default="artifacts/norway-direct-sales")
    parser.add_argument("--max-pages", type=int, default=2)
    parser.add_argument("--max-cards", type=int, default=10)
    args = parser.parse_args()
    report = discover(max_pages=args.max_pages, max_cards=args.max_cards)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "direct-sales.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("verified_count", "missing_count", "pages_read",
             "distinct_active_api_candidates", "failures", "paid_api_requests")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
