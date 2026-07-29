#!/usr/bin/env python3
"""Inspect Auksjoner.no public auction pages for a bounded live adapter.

Temporary diagnostic only. It reads robots.txt plus the current and past auction
index pages. Past data is used only to learn public URL/schema shape and is never
promoted as a live opportunity. No auction detail links are followed.
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

BASE_URL = "https://www.auksjoner.no"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
CURRENT_URL = f"{BASE_URL}/nb-NO/auctions"
PAST_URL = f"{BASE_URL}/nb-NO/auctions/past"
MAX_LINKS = 100


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[dict[str, str]] = []
        self.meta: dict[str, str] = {}
        self.scripts: list[dict[str, str]] = []
        self._href: str | None = None
        self._anchor_parts: list[str] = []
        self._script: dict[str, str] | None = None
        self._script_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.casefold(): value or "" for key, value in attrs}
        lowered = tag.casefold()
        if lowered == "a" and values.get("href"):
            self._href = values["href"]
            self._anchor_parts = []
        elif lowered == "meta":
            key = values.get("name") or values.get("property")
            content = values.get("content")
            if key and content:
                self.meta[key.casefold()] = content[:2000]
        elif lowered == "script":
            self._script = {
                "id": values.get("id", ""),
                "type": values.get("type", ""),
                "src": values.get("src", ""),
            }
            self._script_parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._anchor_parts.append(data)
        if self._script is not None:
            self._script_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if lowered == "a" and self._href is not None:
            self.anchors.append(
                {
                    "href": self._href,
                    "text": " ".join("".join(self._anchor_parts).split())[:1000],
                }
            )
            self._href = None
            self._anchor_parts = []
        elif lowered == "script" and self._script is not None:
            text = "".join(self._script_parts)
            self._script["text_length"] = str(len(text))
            self._script["text"] = text
            self.scripts.append(self._script)
            self._script = None
            self._script_parts = []


def _get(url: str, accept: str) -> tuple[str, dict[str, Any]]:
    request = Request(
        url,
        headers={
            "Accept": accept,
            "User-Agent": "OpportunityEngine/AuksjonerNo-Public-Source-Probe-1.0",
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


def _same_host_link(href: str) -> str | None:
    absolute = urljoin(BASE_URL, href)
    parsed = urlparse(absolute)
    if parsed.scheme != "https" or parsed.hostname not in {
        "auksjoner.no",
        "www.auksjoner.no",
    }:
        return None
    return absolute


def _auction_links(anchors: list[dict[str, str]]) -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    for anchor in anchors:
        absolute = _same_host_link(anchor["href"])
        if not absolute:
            continue
        path = urlparse(absolute).path
        if not re.search(r"/(?:auction|auctions|auksjon|nettauksjon)/", path, re.I):
            continue
        if path.rstrip("/") in {
            "/nb-NO/auctions",
            "/nb-NO/auctions/past",
        }:
            continue
        record = {"url": absolute, "text": anchor["text"]}
        if record not in values:
            values.append(record)
        if len(values) >= MAX_LINKS:
            break
    return values


def _url_candidates(body: str) -> list[str]:
    patterns = (
        r"/(?:nb-NO|en-US)/(?:auction|auctions|auksjon|nettauksjon)/[^\s\"'<>\\]+",
        r"/(?:auction|auctions|auksjon|nettauksjon)/[^\s\"'<>\\]+",
    )
    values: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, body, flags=re.I):
            value = match.group(0).rstrip(").,;]")[:800]
            if value not in values:
                values.append(value)
            if len(values) >= MAX_LINKS:
                return values
    return values


def _relevant_inline_scripts(scripts: list[dict[str, str]]) -> list[dict[str, Any]]:
    markers = (
        "auction",
        "auctions",
        "enddate",
        "startdate",
        "status",
        "past",
        "current",
        "lot",
        "items",
        "api",
        "graphql",
    )
    results: list[dict[str, Any]] = []
    for script in scripts:
        text = script.get("text", "")
        lowered = text.casefold()
        matched = [marker for marker in markers if marker in lowered]
        if not matched:
            continue
        snippets: list[str] = []
        for marker in matched[:10]:
            index = lowered.find(marker)
            if index < 0:
                continue
            snippet = re.sub(
                r"\s+",
                " ",
                text[max(0, index - 180): index + len(marker) + 360],
            ).strip()
            if snippet and snippet not in snippets:
                snippets.append(snippet[:1000])
        results.append(
            {
                "id": script.get("id", ""),
                "type": script.get("type", ""),
                "src": script.get("src", ""),
                "text_length": int(script.get("text_length", "0") or 0),
                "matched_markers": matched,
                "snippets": snippets,
            }
        )
        if len(results) >= 30:
            break
    return results


def _text_snippets(body: str) -> list[str]:
    plain = re.sub(r"<script\b.*?</script>", " ", body, flags=re.I | re.S)
    plain = re.sub(r"<style\b.*?</style>", " ", plain, flags=re.I | re.S)
    plain = re.sub(r"<[^>]+>", "\n", plain)
    markers = (
        "Auksjon",
        "Tidligere",
        "avsluttes",
        "konkursbo",
        "klær",
        "plagg",
        "resultater",
        "ingen",
    )
    values: list[str] = []
    for raw in plain.splitlines():
        line = " ".join(raw.split())
        if not line or len(line) > 1200:
            continue
        if any(marker.casefold() in line.casefold() for marker in markers):
            if line not in values:
                values.append(line)
        if len(values) >= 100:
            break
    return values


def _robots_summary(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    disallows = [
        line.strip()
        for line in lines
        if line.strip().casefold().startswith("disallow:")
    ]
    crawl_match = re.search(r"(?im)^\s*Crawl-delay:\s*([\d.]+)\s*$", text)
    return {
        "first_lines": lines[:100],
        "disallow_rules": disallows,
        "crawl_delay_seconds": (
            float(crawl_match.group(1)) if crawl_match else None
        ),
        "current_auctions_disallowed": any(
            re.match(r"(?i)Disallow:\s*/(?:nb-NO/)?auctions(?:/|\s|$)", rule)
            for rule in disallows
        ),
    }


def main() -> int:
    robots, robots_diag = _get(ROBOTS_URL, "text/plain,*/*;q=0.1")
    pages: list[dict[str, Any]] = []
    for url, role in ((CURRENT_URL, "CURRENT"), (PAST_URL, "PAST_SCHEMA_ONLY")):
        body, diagnostics = _get(url, "text/html,application/xhtml+xml")
        parser = PageParser()
        parser.feed(body)
        pages.append(
            {
                **diagnostics,
                "role": role,
                "meta": parser.meta,
                "anchor_count": len(parser.anchors),
                "auction_links": _auction_links(parser.anchors),
                "url_candidates": _url_candidates(body),
                "text_snippets": _text_snippets(body),
                "relevant_inline_scripts": _relevant_inline_scripts(parser.scripts),
            }
        )

    report = {
        "robots": {**robots_diag, **_robots_summary(robots)},
        "pages": pages,
        "past_data_promoted": False,
        "contact_values_logged": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase_decision": False,
        "automatic_payment": False,
    }
    output = Path("artifacts/auksjoner-no-public-source-probe")
    output.mkdir(parents=True, exist_ok=True)
    path = output / "probe-report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Robots HTTP: {robots_diag['http_status']}")
    print(
        "Current auctions disallowed: "
        f"{report['robots']['current_auctions_disallowed']}"
    )
    print(f"Crawl delay: {report['robots']['crawl_delay_seconds']}")
    for page in pages:
        print(f"Page role: {page['role']}")
        print(f"URL: {page['requested_url']}")
        print(f"HTTP: {page['http_status']}")
        print(f"Auction links: {json.dumps(page['auction_links'], ensure_ascii=False)}")
        print(f"URL candidates: {json.dumps(page['url_candidates'], ensure_ascii=False)}")
        print(f"Text snippets: {json.dumps(page['text_snippets'], ensure_ascii=False)}")
        print(
            "Relevant scripts: "
            + json.dumps(page["relevant_inline_scripts"], ensure_ascii=False)
        )
    print(f"Report: {path}")
    return 0 if all(page["http_status"] == 200 for page in pages) else 2


if __name__ == "__main__":
    raise SystemExit(main())
