#!/usr/bin/env python3
"""Inspect one permitted active Vareauksjonen listing detail page.

Temporary bounded diagnostic. It reads the active browse page, waits the
published 10-second crawl delay, then reads only the first public listing. It
retains public commercial fields and no contact/personal data.
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
BROWSE_URL = f"{BASE_URL}/Browse"
CRAWL_DELAY_SECONDS = 10
SENSITIVE_KEYS = ("contact", "kontakt", "email", "e-post", "phone", "telefon", "address", "adresse")


class DetailParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[dict[str, str]] = []
        self.meta: dict[str, str] = {}
        self.json_ld: list[Any] = []
        self.inputs: list[dict[str, str]] = []
        self.times: list[dict[str, str]] = []
        self.headings: list[dict[str, str]] = []
        self._href: str | None = None
        self._anchor_parts: list[str] = []
        self._heading_tag: str | None = None
        self._heading_parts: list[str] = []
        self._script_type: str | None = None
        self._script_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.casefold(): value or "" for key, value in attrs}
        lowered = tag.casefold()
        if lowered == "a" and values.get("href"):
            self._href = values["href"]
            self._anchor_parts = []
        elif lowered in {"h1", "h2", "h3"}:
            self._heading_tag = lowered
            self._heading_parts = []
        elif lowered == "meta":
            key = values.get("name") or values.get("property")
            content = values.get("content")
            if key and content and not any(item in key.casefold() for item in SENSITIVE_KEYS):
                self.meta[key.casefold()] = content[:2000]
        elif lowered == "input":
            name = values.get("name", "")
            if not any(item in name.casefold() for item in SENSITIVE_KEYS):
                self.inputs.append(
                    {
                        "name": name,
                        "id": values.get("id", ""),
                        "type": values.get("type", "text"),
                        "value": values.get("value", "")[:500],
                    }
                )
        elif lowered == "time":
            self.times.append(
                {
                    "datetime": values.get("datetime", ""),
                    "class": values.get("class", ""),
                    "id": values.get("id", ""),
                }
            )
        elif lowered == "script":
            self._script_type = values.get("type", "")
            self._script_parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._anchor_parts.append(data)
        if self._heading_tag is not None:
            self._heading_parts.append(data)
        if self._script_type is not None:
            self._script_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if lowered == "a" and self._href is not None:
            text = " ".join("".join(self._anchor_parts).split())
            self.anchors.append({"href": self._href, "text": text[:800]})
            self._href = None
            self._anchor_parts = []
        elif lowered in {"h1", "h2", "h3"} and self._heading_tag is not None:
            text = " ".join("".join(self._heading_parts).split())
            self.headings.append({"tag": self._heading_tag, "text": text[:1200]})
            self._heading_tag = None
            self._heading_parts = []
        elif lowered == "script" and self._script_type is not None:
            if "ld+json" in self._script_type.casefold():
                text = "".join(self._script_parts).strip()
                if text:
                    try:
                        self.json_ld.append(json.loads(text))
                    except json.JSONDecodeError:
                        self.json_ld.append({"parse_error": True, "length": len(text)})
            self._script_type = None
            self._script_parts = []


def _get(url: str) -> tuple[str, dict[str, Any]]:
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "OpportunityEngine/Vareauksjonen-Listing-Probe-1.0",
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


def _first_listing_url(body: str) -> str:
    match = re.search(
        r'href=["\'](?P<url>/Listing/Details/\d+/[^"\']+)["\']',
        body,
        flags=re.I,
    )
    if not match:
        raise RuntimeError("active browse page contains no listing detail URL")
    return urljoin(BASE_URL, match.group("url"))


def _commercial_text(body: str) -> list[str]:
    plain = re.sub(r"<script\b.*?</script>", " ", body, flags=re.I | re.S)
    plain = re.sub(r"<style\b.*?</style>", " ", plain, flags=re.I | re.S)
    plain = re.sub(r"<[^>]+>", "\n", plain)
    markers = (
        "Objektnr",
        "Kjøp nå",
        "Bud",
        "Pris",
        "kr",
        "NOK",
        "Aktiv",
        "Avslut",
        "Slutter",
        "Beskrivelse",
        "Antall",
        "Kategori",
        "Tilstand",
    )
    lines: list[str] = []
    for raw in plain.splitlines():
        line = " ".join(raw.split())
        if not line or len(line) > 1000:
            continue
        lowered = line.casefold()
        if any(item in lowered for item in SENSITIVE_KEYS):
            continue
        if any(marker.casefold() in lowered for marker in markers):
            if line not in lines:
                lines.append(line)
        if len(lines) >= 120:
            break
    return lines


def _safe_json_shape(value: Any, depth: int = 0) -> Any:
    if depth > 5:
        return type(value).__name__
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            if any(item in str(key).casefold() for item in SENSITIVE_KEYS):
                continue
            result[str(key)] = _safe_json_shape(child, depth + 1)
        return result
    if isinstance(value, list):
        return [_safe_json_shape(item, depth + 1) for item in value[:10]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return type(value).__name__


def main() -> int:
    browse_html, browse_diag = _get(BROWSE_URL)
    listing_url = _first_listing_url(browse_html)
    time.sleep(CRAWL_DELAY_SECONDS)
    detail_html, detail_diag = _get(listing_url)
    parsed = DetailParser()
    parsed.feed(detail_html)

    report = {
        "browse": browse_diag,
        "listing": detail_diag,
        "listing_url": listing_url,
        "headings": parsed.headings,
        "meta": parsed.meta,
        "json_ld": _safe_json_shape(parsed.json_ld),
        "inputs": parsed.inputs[:100],
        "times": parsed.times[:50],
        "commercial_text": _commercial_text(detail_html),
        "crawl_delay_seconds": CRAWL_DELAY_SECONDS,
        "crawl_delay_respected": True,
        "contact_values_logged": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase_decision": False,
        "automatic_payment": False,
    }
    output = Path("artifacts/vareauksjonen-listing-detail-probe")
    output.mkdir(parents=True, exist_ok=True)
    path = output / "detail-report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Listing URL: {listing_url}")
    print(f"Listing HTTP: {detail_diag['http_status']}")
    print(f"Headings: {json.dumps(parsed.headings, ensure_ascii=False)}")
    print(f"Meta: {json.dumps(parsed.meta, ensure_ascii=False)}")
    print(f"JSON-LD: {json.dumps(report['json_ld'], ensure_ascii=False)}")
    print(f"Inputs: {json.dumps(parsed.inputs[:100], ensure_ascii=False)}")
    print(f"Times: {json.dumps(parsed.times[:50], ensure_ascii=False)}")
    print(f"Commercial text: {json.dumps(report['commercial_text'], ensure_ascii=False)}")
    print(f"Report: {path}")
    return 0 if detail_diag["http_status"] == 200 else 2


if __name__ == "__main__":
    raise SystemExit(main())
