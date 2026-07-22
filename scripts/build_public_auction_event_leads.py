#!/usr/bin/env python3
"""Collect public auction-event discovery leads from Politiet.no.

This collector reads only the official public lost-property information page. It
records explicit auction links when present and otherwise keeps the official
auction directory as a single discovery lead. These are event leads, not proof
that a specific lot is currently available for online purchase.
"""

from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

DEFAULT_URL = "https://www.politiet.no/tjenester/hittegods"


class _AuctionLinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self._href: str | None = None
        self._text: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.casefold() != "a":
            return
        values = dict(attrs)
        self._href = values.get("href")
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "a" or self._href is None:
            return
        title = " ".join("".join(self._text).split())
        url = urljoin(self.base_url, self._href)
        searchable = f"{title} {url}".casefold()
        if ("auksjon" in searchable or "hittegods" in searchable) and _is_official(url):
            self.links.append((title or "Politiet auction information", url))
        self._href = None
        self._text = []


def _is_official(url: str) -> bool:
    host = urlparse(url).netloc.casefold()
    return host == "politiet.no" or host.endswith(".politiet.no") or host == "www.politiet.no"


def parse_auction_leads(html: str, *, source_url: str = DEFAULT_URL) -> list[dict[str, object]]:
    parser = _AuctionLinkParser(source_url)
    parser.feed(html)
    seen: set[str] = set()
    leads: list[dict[str, object]] = []
    for title, url in parser.links:
        if url in seen:
            continue
        seen.add(url)
        lead_id = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        leads.append(
            {
                "lead_id": f"politiet-auction-{lead_id}",
                "channel": "public_auction_event_lead",
                "source": "Politiet.no",
                "title": title,
                "url": url,
                "status": "FOLLOW_UP_EVENT_LEAD",
                "asking_price_nok": None,
                "city": None,
                "ends_at": None,
                "warning": "Official auction discovery lead only; specific lots, dates and availability must be verified from the linked announcement.",
            }
        )
    if not leads:
        leads.append(
            {
                "lead_id": "politiet-auction-directory",
                "channel": "public_auction_event_lead",
                "source": "Politiet.no",
                "title": "Politiet lost-property and bicycle auction directory",
                "url": source_url,
                "status": "SOURCE_DIRECTORY",
                "asking_price_nok": None,
                "city": None,
                "ends_at": None,
                "warning": "Official directory only; local auctions may be announced in local media, Facebook or auction houses.",
            }
        )
    return leads


def fetch_html(url: str, timeout: float = 20.0) -> str:
    if not _is_official(url) or not url.startswith("https://"):
        raise ValueError("Politiet source URL must be an official HTTPS politiet.no URL")
    request = Request(url, headers={"User-Agent": "Opportunity-Engine/1.0 (public-source-discovery)"})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed official public source
            return response.read().decode(response.headers.get_content_charset() or "utf-8")
    except HTTPError as exc:
        raise RuntimeError(f"Politiet.no returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Politiet.no request failed: {exc.reason}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--output", default="data/public_auction_event_leads.json")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    if args.limit <= 0:
        raise ValueError("limit must be positive")

    error: str | None = None
    try:
        leads = parse_auction_leads(fetch_html(args.url), source_url=args.url)[: args.limit]
    except RuntimeError as exc:
        leads = []
        error = str(exc)

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Politiet.no",
        "access_mode": "official_public_page",
        "fetched_count": len(leads),
        "error": error,
        "items": leads,
        "method": "official public auction-event discovery only; no prices, lots or availability are invented",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "fetched_count": len(leads), "error": error}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
