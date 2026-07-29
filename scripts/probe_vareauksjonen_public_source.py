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
MAX_INLINE_SCRIPT_SNIPPETS = 40


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[dict[str, str]] = []
        self.forms: list[dict[str, str]] = []
        self.inputs: list[dict[str, str]] = []
        self.selects: list[dict[str, Any]] = []
        self.scripts: list[dict[str, str]] = []
        self.meta: dict[str, str] = {}
        self._href: str | None = None
        self._parts: list[str] = []
        self._script: dict[str, str] | None = None
        self._script_parts: list[str] = []
        self._select: dict[str, Any] | None = None
        self._option: dict[str, str] | None = None
        self._option_parts: list[str] = []

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
                    "id": values.get("id", ""),
                    "class": values.get("class", ""),
                }
            )
        elif lowered == "input":
            self.inputs.append(
                {
                    "name": values.get("name", ""),
                    "type": values.get("type", "text").lower(),
                    "value": values.get("value", "")[:300],
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
        elif lowered == "script":
            self._script = {
                "src": values.get("src", ""),
                "type": values.get("type", ""),
                "id": values.get("id", ""),
            }
            self._script_parts = []
        elif lowered == "meta":
            key = values.get("name") or values.get("property")
            if key and values.get("content"):
                self.meta[key.casefold()] = values["content"]

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)
        if self._script is not None:
            self._script_parts.append(data)
        if self._option is not None:
            self._option_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if lowered == "a" and self._href is not None:
            self.anchors.append(
                {
                    "href": self._href,
                    "text": " ".join("".join(self._parts).split())[:600],
                }
            )
            self._href = None
            self._parts = []
        elif lowered == "option" and self._option is not None and self._select is not None:
            self._option["text"] = " ".join("".join(self._option_parts).split())[:300]
            self._select["options"].append(self._option)
            self._option = None
            self._option_parts = []
        elif lowered == "select" and self._select is not None:
            self.selects.append(self._select)
            self._select = None
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
            "User-Agent": "OpportunityEngine/Vareauksjonen-Public-Source-Probe-1.1",
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
        and re.fullmatch(r"/Listing/(?:Details/)?\d+(?:/[^?#]*)?", parsed.path, re.I)
    ):
        return absolute
    return None


def _relevant_script_snippets(scripts: list[dict[str, str]]) -> list[dict[str, Any]]:
    markers = (
        "listing",
        "browse",
        "active",
        "aktiv",
        "completed",
        "fullført",
        "auction",
        "event",
        "viewstyle",
        "ajax",
        "load",
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
                r"\s+", " ", text[max(0, index - 180): index + len(marker) + 300]
            ).strip()
            if snippet and snippet not in snippets:
                snippets.append(snippet[:800])
        results.append(
            {
                "src": script.get("src", ""),
                "id": script.get("id", ""),
                "type": script.get("type", ""),
                "text_length": int(script.get("text_length", "0") or 0),
                "matched_markers": matched,
                "snippets": snippets,
            }
        )
        if len(results) >= MAX_INLINE_SCRIPT_SNIPPETS:
            break
    return results


def _html_url_candidates(body: str) -> list[str]:
    patterns = (
        r"/[Ll]isting/[^\s\"'<>\\]+",
        r"/[Ee]vent/[Dd]etails/[^\s\"'<>\\]+",
        r"/[Bb]rowse/[^\s\"'<>\\]+",
        r"/[Ss]earch[^\s\"'<>\\]*",
    )
    values: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, body):
            value = match.group(0).rstrip(").,;]")[:500]
            if value not in values:
                values.append(value)
            if len(values) >= 100:
                return values
    return values


def _text_snippets(body: str) -> list[str]:
    plain = re.sub(r"<script\b.*?</script>", " ", body, flags=re.I | re.S)
    plain = re.sub(r"<style\b.*?</style>", " ", plain, flags=re.I | re.S)
    plain = re.sub(r"<[^>]+>", "\n", plain)
    plain = re.sub(r"[ \t]+", " ", plain)
    markers = ("Aktiv", "Fullført", "Ingen", "auksjon", "annonser", "resultat")
    lines: list[str] = []
    for raw in plain.splitlines():
        line = " ".join(raw.split())
        if not line or len(line) > 500:
            continue
        if any(marker.casefold() in line.casefold() for marker in markers):
            if line not in lines:
                lines.append(line)
        if len(lines) >= 80:
            break
    return lines


def _rule_blocks_exact_category(rule: str) -> bool:
    value = rule.split(":", 1)[1].strip() if ":" in rule else ""
    return value in {"/Browse", "/Browse/", "/Browse/*", "/Browse/*/"}


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
                "inputs": parser.inputs[:100],
                "selects": parser.selects[:30],
                "all_anchors": parser.anchors[:100],
                "external_scripts": [
                    {key: value for key, value in script.items() if key != "text"}
                    for script in parser.scripts[:80]
                ],
                "relevant_inline_scripts": _relevant_script_snippets(parser.scripts),
                "html_url_candidates": _html_url_candidates(body),
                "text_snippets": _text_snippets(body),
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
            "category_pages_disallowed": any(
                _rule_blocks_exact_category(line) for line in robots_disallows
            ),
            "listing_disallowed": any(
                re.match(r"(?i)Disallow:\s*/Listing(?:/|\s|$)", line)
                for line in robots_disallows
            ),
            "crawl_delay_seconds": 10,
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
    print(f"Category pages disallowed: {report['robots']['category_pages_disallowed']}")
    print(f"Listing disallowed: {report['robots']['listing_disallowed']}")
    for category in reports:
        print(f"Category: {category['requested_url']}")
        print(f"HTTP: {category['http_status']}")
        print(f"Final URL: {category['final_url']}")
        print(f"Response bytes: {category['response_bytes']}")
        print(f"Anchors: {json.dumps(category['all_anchors'], ensure_ascii=False)}")
        print(f"Inputs: {json.dumps(category['inputs'], ensure_ascii=False)}")
        print(f"Selects: {json.dumps(category['selects'], ensure_ascii=False)}")
        print(f"Listing links: {json.dumps(category['listing_links'], ensure_ascii=False)}")
        print(
            "HTML URL candidates: "
            + json.dumps(category["html_url_candidates"], ensure_ascii=False)
        )
        print(
            "Text snippets: "
            + json.dumps(category["text_snippets"], ensure_ascii=False)
        )
        print(
            "Relevant inline scripts: "
            + json.dumps(category["relevant_inline_scripts"], ensure_ascii=False)
        )
    print(f"Report: {path}")
    return 0 if all(item["http_status"] == 200 for item in reports) else 2


if __name__ == "__main__":
    raise SystemExit(main())
