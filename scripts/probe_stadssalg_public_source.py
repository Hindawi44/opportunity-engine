#!/usr/bin/env python3
"""Inspect Stadssalg's public auction-list page for a bounded live adapter.

Temporary diagnostic only. It performs public GET requests, follows no auction
links, logs no personal/contact data, and never logs in, bids, buys, or pays.
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

BASE_URL = "https://www.stadssalg.no"
ITEMS_URL = f"{BASE_URL}/items"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
MAX_ANCHORS = 80


class PublicPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[dict[str, str]] = []
        self.forms: list[dict[str, str]] = []
        self.scripts: list[dict[str, str]] = []
        self.meta: dict[str, str] = {}
        self._href: str | None = None
        self._anchor_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.casefold(): value or "" for key, value in attrs}
        lowered = tag.casefold()
        if lowered == "a" and values.get("href"):
            self._href = values["href"]
            self._anchor_parts = []
        elif lowered == "form":
            self.forms.append(
                {
                    "action": values.get("action", ""),
                    "method": values.get("method", "get").lower(),
                }
            )
        elif lowered == "script":
            self.scripts.append(
                {
                    "src": values.get("src", ""),
                    "type": values.get("type", ""),
                    "id": values.get("id", ""),
                }
            )
        elif lowered == "meta":
            key = values.get("name") or values.get("property")
            if key and values.get("content"):
                self.meta[key.casefold()] = values["content"]

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._anchor_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "a" and self._href is not None:
            text = " ".join("".join(self._anchor_parts).split())
            self.anchors.append({"href": self._href, "text": text[:500]})
            self._href = None
            self._anchor_parts = []


def _get(url: str, accept: str) -> tuple[str, dict[str, Any]]:
    request = Request(
        url,
        headers={
            "Accept": accept,
            "User-Agent": "OpportunityEngine/Stadssalg-Public-Source-Probe-1.0",
        },
    )
    with urlopen(request, timeout=30) as response:  # noqa: S310
        body = response.read().decode("utf-8", errors="replace")
        diagnostics = {
            "requested_url": url,
            "final_url": response.geturl(),
            "http_status": int(response.status),
            "content_type": response.headers.get("content-type", ""),
            "response_bytes": len(body.encode("utf-8")),
        }
    return body, diagnostics


def _approved_item_link(href: str) -> bool:
    absolute = urljoin(BASE_URL, href)
    parsed = urlparse(absolute)
    return (
        parsed.scheme == "https"
        and parsed.hostname in {"stadssalg.no", "www.stadssalg.no"}
        and parsed.path.startswith("/items/")
        and parsed.path.rstrip("/").split("/")[-1].isdigit()
    )


def main() -> int:
    robots, robots_diag = _get(ROBOTS_URL, "text/plain,*/*;q=0.1")
    page, page_diag = _get(ITEMS_URL, "text/html,application/xhtml+xml")
    parser = PublicPageParser()
    parser.feed(page)

    item_links: list[dict[str, str]] = []
    for anchor in parser.anchors:
        if not _approved_item_link(anchor["href"]):
            continue
        absolute = urljoin(BASE_URL, anchor["href"])
        record = {"url": absolute, "text": anchor["text"]}
        if record not in item_links:
            item_links.append(record)
        if len(item_links) >= MAX_ANCHORS:
            break

    keywords = (
        "klær",
        "klaer",
        "klesbutikk",
        "varelager",
        "konkursbo",
        "tommy hilfiger",
        "calvin klein",
        "belter",
        "vesker",
        "parti",
    )
    keyword_links = [
        item
        for item in item_links
        if any(keyword in item["text"].casefold() for keyword in keywords)
    ]
    report = {
        "robots": {
            **robots_diag,
            "first_lines": robots.splitlines()[:80],
            "disallow_items_detected": bool(
                re.search(r"(?im)^\s*Disallow:\s*/items(?:/|\s|$)", robots)
            ),
        },
        "items_page": page_diag,
        "meta": parser.meta,
        "forms": parser.forms[:20],
        "scripts": parser.scripts[:50],
        "anchor_count": len(parser.anchors),
        "approved_item_link_count": len(item_links),
        "approved_item_links": item_links,
        "keyword_item_links": keyword_links,
        "contact_values_logged": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase_decision": False,
        "automatic_payment": False,
    }
    output = Path("artifacts/stadssalg-public-source-probe")
    output.mkdir(parents=True, exist_ok=True)
    path = output / "probe-report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Robots HTTP: {robots_diag['http_status']}")
    print(f"Disallow /items detected: {report['robots']['disallow_items_detected']}")
    print(f"Items HTTP: {page_diag['http_status']}")
    print(f"Items final URL: {page_diag['final_url']}")
    print(f"Items response bytes: {page_diag['response_bytes']}")
    print(f"Anchor count: {len(parser.anchors)}")
    print(f"Approved item links: {len(item_links)}")
    print(f"Keyword item links: {json.dumps(keyword_links, ensure_ascii=False)}")
    print(f"Forms: {json.dumps(parser.forms[:20], ensure_ascii=False)}")
    print(f"Scripts: {json.dumps(parser.scripts[:50], ensure_ascii=False)}")
    print(f"Report: {path}")
    return 0 if page_diag["http_status"] == 200 else 2


if __name__ == "__main__":
    raise SystemExit(main())
