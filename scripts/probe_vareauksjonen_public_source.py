#!/usr/bin/env python3
"""Inspect permitted Vareauksjonen public pages for a bounded live adapter.

Temporary diagnostic only. It respects the published 10-second crawl delay,
reads robots.txt, the unfiltered active browse page, and two public category
pages. It follows no listing links and performs no commercial action.
"""
from __future__ import annotations

import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

BASE_URL = "https://www.vareauksjonen.no"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
PUBLIC_PAGES = (
    f"{BASE_URL}/Browse",
    f"{BASE_URL}/Browse/C161443/Kl%C3%A6r",
    f"{BASE_URL}/Browse/C161461/Varelager-og-konkursbo",
)
CRAWL_DELAY_SECONDS = 10
MAX_LINKS_PER_PAGE = 100


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[dict[str, str]] = []
        self.inputs: list[dict[str, str]] = []
        self.selects: list[dict[str, Any]] = []
        self._href: str | None = None
        self._anchor_parts: list[str] = []
        self._select: dict[str, Any] | None = None
        self._option: dict[str, str] | None = None
        self._option_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.casefold(): value or "" for key, value in attrs}
        lowered = tag.casefold()
        if lowered == "a" and values.get("href"):
            self._href = values["href"]
            self._anchor_parts = []
        elif lowered == "input":
            self.inputs.append(
                {
                    "name": values.get("name", ""),
                    "type": values.get("type", "text").lower(),
                    "value": values.get("value", "")[:200],
                    "id": values.get("id", ""),
                }
            )
        elif lowered == "select":
            self._select = {
                "name": values.get("name", ""),
                "id": values.get("id", ""),
                "options": [],
            }
        elif lowered == "option" and self._select is not None:
            self._option = {
                "value": values.get("value", ""),
                "selected": "selected" if "selected" in values else "",
            }
            self._option_parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._anchor_parts.append(data)
        if self._option is not None:
            self._option_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if lowered == "a" and self._href is not None:
            self.anchors.append(
                {
                    "href": self._href,
                    "text": " ".join("".join(self._anchor_parts).split())[:800],
                }
            )
            self._href = None
            self._anchor_parts = []
        elif lowered == "option" and self._option is not None and self._select is not None:
            self._option["text"] = " ".join("".join(self._option_parts).split())[:200]
            self._select["options"].append(self._option)
            self._option = None
            self._option_parts = []
        elif lowered == "select" and self._select is not None:
            self.selects.append(self._select)
            self._select = None


def _get(url: str, accept: str) -> tuple[str, dict[str, Any]]:
    request = Request(
        url,
        headers={
            "Accept": accept,
            "User-Agent": "OpportunityEngine/Vareauksjonen-Public-Source-Probe-1.2",
        },
    )
    with urlopen(request, timeout=30) as response:  # noqa: S310
        body = response.read().decode("utf-8", errors="replace")
        return body, {
            "requested_url": url,
            "final_url": response.geturl(),
            "http_status": int(response.status),
            "content_type": response.headers.get("content-type", ""),
            "response_bytes": len(body.encode("utf-8")),
        }


def _listing_url(href: str) -> str | None:
    absolute = urljoin(BASE_URL, href)
    parsed = urlparse(absolute)
    if parsed.scheme != "https" or parsed.hostname not in {
        "vareauksjonen.no",
        "www.vareauksjonen.no",
    }:
        return None
    if re.fullmatch(r"/Listing/(?:Details/)?\d+(?:/[^?#]*)?", parsed.path, re.I):
        return absolute
    return None


def _html_listing_candidates(body: str) -> list[str]:
    values: list[str] = []
    for match in re.finditer(r"/Listing/(?:Details/)?\d+(?:/[^\s\"'<>\\]*)?", body, re.I):
        value = match.group(0).rstrip(").,;]")
        if value not in values:
            values.append(value)
        if len(values) >= 100:
            break
    return values


def _relevant_text(body: str) -> list[str]:
    plain = re.sub(r"<script\b.*?</script>", " ", body, flags=re.I | re.S)
    plain = re.sub(r"<style\b.*?</style>", " ", plain, flags=re.I | re.S)
    plain = re.sub(r"<[^>]+>", "\n", plain)
    markers = (
        "Ingen",
        "Nye auksjoner",
        "Aktiv",
        "Fullført",
        "objekt",
        "auksjon",
    )
    values: list[str] = []
    for raw in plain.splitlines():
        line = " ".join(raw.split())
        if not line or len(line) > 600:
            continue
        if any(marker.casefold() in line.casefold() for marker in markers):
            if line not in values:
                values.append(line)
        if len(values) >= 100:
            break
    return values


def _category_pages_disallowed(rules: list[str]) -> bool:
    blocked = {"/browse", "/browse/", "/browse/*", "/browse/*/"}
    for rule in rules:
        value = rule.split(":", 1)[1].strip().casefold() if ":" in rule else ""
        if value in blocked:
            return True
    return False


def main() -> int:
    robots, robots_diag = _get(ROBOTS_URL, "text/plain,*/*;q=0.1")
    rules = [
        line.strip()
        for line in robots.splitlines()
        if line.strip().casefold().startswith("disallow:")
    ]
    reports: list[dict[str, Any]] = []
    for page_url in PUBLIC_PAGES:
        time.sleep(CRAWL_DELAY_SECONDS)
        body, diagnostics = _get(page_url, "text/html,application/xhtml+xml")
        parser = PageParser()
        parser.feed(body)
        links: list[dict[str, str]] = []
        for anchor in parser.anchors:
            listing_url = _listing_url(anchor["href"])
            if not listing_url:
                continue
            record = {"url": listing_url, "text": anchor["text"]}
            if record not in links:
                links.append(record)
            if len(links) >= MAX_LINKS_PER_PAGE:
                break
        reports.append(
            {
                **diagnostics,
                "anchor_count": len(parser.anchors),
                "all_anchors": parser.anchors[:120],
                "inputs": parser.inputs[:100],
                "selects": parser.selects[:30],
                "listing_link_count": len(links),
                "listing_links": links,
                "html_listing_candidates": _html_listing_candidates(body),
                "relevant_text": _relevant_text(body),
                "default_active_only": any(
                    item.get("name") == "StatusFilter"
                    and item.get("value") == "active_only"
                    for item in parser.inputs
                ),
            }
        )

    report = {
        "robots": {
            **robots_diag,
            "first_lines": robots.splitlines()[:100],
            "disallow_rules": rules,
            "category_pages_disallowed": _category_pages_disallowed(rules),
            "listing_pages_disallowed": any(
                re.match(r"(?i)Disallow:\s*/Listing(?:/|\s|$)", rule)
                for rule in rules
            ),
            "crawl_delay_seconds": CRAWL_DELAY_SECONDS,
            "crawl_delay_respected": True,
        },
        "pages": reports,
        "total_listing_links": sum(page["listing_link_count"] for page in reports),
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

    print(f"Category pages disallowed: {report['robots']['category_pages_disallowed']}")
    print(f"Listing pages disallowed: {report['robots']['listing_pages_disallowed']}")
    print(f"Crawl delay respected: {report['robots']['crawl_delay_respected']}")
    for page in reports:
        print(f"Page: {page['requested_url']}")
        print(f"HTTP: {page['http_status']}")
        print(f"Default active only: {page['default_active_only']}")
        print(f"Listing links: {json.dumps(page['listing_links'], ensure_ascii=False)}")
        print(
            "HTML listing candidates: "
            + json.dumps(page["html_listing_candidates"], ensure_ascii=False)
        )
        print(f"Relevant text: {json.dumps(page['relevant_text'], ensure_ascii=False)}")
    print(f"Report: {path}")
    return 0 if all(page["http_status"] == 200 for page in reports) else 2


if __name__ == "__main__":
    raise SystemExit(main())
