#!/usr/bin/env python3
"""Inspect Vareauksjonen public clothing/inventory pages for a safe adapter.

Temporary bounded diagnostic. It reads robots.txt plus two public category pages,
follows no listing links, retains no contact data, and never logs in, bids, buys,
reserves, or pays.
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

BASE_URL = "https://www.vareauksjonen.no"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
CATEGORY_URLS = (
    f"{BASE_URL}/Browse/C161443/Kl%C3%A6r",
    f"{BASE_URL}/Browse/C161461/Varelager-og-konkursbo",
)
MAX_LINKS_PER_PAGE = 100


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[dict[str, str]] = []
        self.forms: list[dict[str, str]] = []
        self.scripts: list[dict[str, str]] = []
        self.meta: dict[str, str] = {}
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.casefold(): value or "" for key, value in attrs}
        lowered = tag.casefold()
        if lowered == "a" and values.get("href"):
            self._href = values["href"]
            self._parts = []
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
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "a" and self._href is not None:
            self.anchors.append(
                {
                    "href": self._href,
                    "text": " ".join("".join(self._parts).split())[:600],
                }
            )
            self._href = None
            self._parts = []


def _get(url: str, accept: str) -> tuple[str, dict[str, Any]]:
    request = Request(
        url,
        headers={
            "Accept": accept,
            "User-Agent": "OpportunityEngine/Vareauksjonen-Public-Source-Probe-1.0",
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


def _listing_url(href: str) -> str | None:
    absolute = urljoin(BASE_URL, href)
    parsed = urlparse(absolute)
    if (
        parsed.scheme == "https"
        and parsed.hostname in {"vareauksjonen.no", "www.vareauksjonen.no"}
        and re.fullmatch(r"/Listing/Details/\d+(?:/[^?#]*)?", parsed.path, re.I)
    ):
        return absolute
    return None


def main() -> int:
    robots, robots_diag = _get(ROBOTS_URL, "text/plain,*/*;q=0.1")
    reports: list[dict[str, Any]] = []
    for category_url in CATEGORY_URLS:
        body, diagnostics = _get(category_url, "text/html,application/xhtml+xml")
        parser = PageParser()
        parser.feed(body)
        links: list[dict[str, str]] = []
        for anchor in parser.anchors:
            url = _listing_url(anchor["href"])
            if not url:
                continue
            record = {"url": url, "text": anchor["text"]}
            if record not in links:
                links.append(record)
            if len(links) >= MAX_LINKS_PER_PAGE:
                break
        reports.append(
            {
                **diagnostics,
                "meta": parser.meta,
                "forms": parser.forms[:20],
                "scripts": parser.scripts[:50],
                "anchor_count": len(parser.anchors),
                "listing_link_count": len(links),
                "listing_links": links,
                "active_term_present": "Aktiv" in body,
                "completed_term_present": "Fullført" in body,
                "sold_term_present": "Solgt" in body,
            }
        )

    robots_disallows = [
        line.strip()
        for line in robots.splitlines()
        if line.strip().casefold().startswith("disallow:")
    ]
    report = {
        "robots": {
            **robots_diag,
            "first_lines": robots.splitlines()[:100],
            "disallow_rules": robots_disallows,
            "browse_disallowed": any(
                re.match(r"(?i)Disallow:\s*/Browse(?:/|\s|$)", line)
                for line in robots_disallows
            ),
            "listing_disallowed": any(
                re.match(r"(?i)Disallow:\s*/Listing(?:/|\s|$)", line)
                for line in robots_disallows
            ),
        },
        "categories": reports,
        "total_listing_links": sum(item["listing_link_count"] for item in reports),
        "contact_values_logged": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase_decision": False,
        "automatic_payment": False,
    }
    output = Path("artifacts/vareauksjonen-public-source-probe")
    output.mkdir(parents=True, exist_ok=True)
    path = output / "probe-report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Robots HTTP: {robots_diag['http_status']}")
    print(f"Robots disallow rules: {json.dumps(robots_disallows, ensure_ascii=False)}")
    print(f"Browse disallowed: {report['robots']['browse_disallowed']}")
    print(f"Listing disallowed: {report['robots']['listing_disallowed']}")
    for category in reports:
        print(f"Category: {category['requested_url']}")
        print(f"HTTP: {category['http_status']}")
        print(f"Final URL: {category['final_url']}")
        print(f"Response bytes: {category['response_bytes']}")
        print(f"Anchor count: {category['anchor_count']}")
        print(f"Listing links: {json.dumps(category['listing_links'], ensure_ascii=False)}")
        print(
            "State terms: "
            f"active={category['active_term_present']} "
            f"completed={category['completed_term_present']} "
            f"sold={category['sold_term_present']}"
        )
    print(f"Report: {path}")
    return 0 if all(item["http_status"] == 200 for item in reports) else 2


if __name__ == "__main__":
    raise SystemExit(main())
