#!/usr/bin/env python3
"""Observe public identity evidence exposed by two Auksjonen item pages.

Temporary bounded diagnostic: two public item pages, no login, no interaction, no
contact, no bid, no purchase, and no payment. It retains only API URLs, JSON keys,
public identity-related text lines, and bounded structured-data snippets.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from opportunity_engine.discovery.auksjonen_public_api_adapter import (
    build_public_item_url,
)

ITEMS = (
    (
        "TOLLAUKSJON - Smykkesett i 21k gull – flere sett (samlet)",
        564704,
    ),
    (
        "Fxr jakke snøscooter, strl XL",
        609460,
    ),
)
IDENTITY_HINTS = (
    "principal",
    "organization",
    "organisation",
    "seller",
    "selger",
    "oppdragsgiver",
    "customer",
    "company",
    "firma",
    "owner",
    "debtor",
    "debitor",
    "orgnr",
    "orgnumber",
    "organisasjonsnummer",
    "business",
    "på vegne av",
    "salg på vegne",
    "konkursbo",
)
SENSITIVE_HINTS = (
    "address",
    "adresse",
    "email",
    "e-post",
    "phone",
    "telefon",
    "mobile",
    "contact",
    "kontakt",
    "person",
)


def _walk_identity(value: object, *, path: str = "", depth: int = 0) -> list[dict[str, Any]]:
    if depth > 5:
        return []
    found: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key)
            child_path = f"{path}.{key}" if path else key
            lowered = key.casefold()
            if any(hint in lowered for hint in SENSITIVE_HINTS):
                continue
            if any(hint in lowered for hint in IDENTITY_HINTS):
                if isinstance(child, (str, int, float, bool)) or child is None:
                    found.append({"path": child_path, "value": child})
                elif isinstance(child, Mapping):
                    found.append(
                        {
                            "path": child_path,
                            "value_type": "object",
                            "keys": sorted(str(item) for item in child.keys()),
                        }
                    )
                elif isinstance(child, Sequence) and not isinstance(child, (str, bytes)):
                    found.append(
                        {
                            "path": child_path,
                            "value_type": "array",
                            "length": len(child),
                        }
                    )
            found.extend(_walk_identity(child, path=child_path, depth=depth + 1))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, child in enumerate(value[:10]):
            found.extend(_walk_identity(child, path=f"{path}[{index}]", depth=depth + 1))
    return found


def _shape(value: object, *, depth: int = 0) -> object:
    if depth > 3:
        return type(value).__name__
    if isinstance(value, Mapping):
        return {
            str(key): _shape(child, depth=depth + 1)
            for key, child in list(value.items())[:80]
            if not any(hint in str(key).casefold() for hint in SENSITIVE_HINTS)
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_shape(child, depth=depth + 1) for child in value[:2]]
    return type(value).__name__


def _identity_text_lines(body_text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in body_text.splitlines():
        line = " ".join(raw_line.split())
        lowered = line.casefold()
        if not line or len(line) > 500:
            continue
        if any(hint in lowered for hint in SENSITIVE_HINTS):
            continue
        if any(hint in lowered for hint in IDENTITY_HINTS):
            if line not in lines:
                lines.append(line)
        if len(lines) >= 40:
            break
    return lines


def _bounded_script_snippets(scripts: Sequence[Mapping[str, Any]], object_id: int) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    markers = (str(object_id),) + IDENTITY_HINTS
    for script in scripts:
        text = str(script.get("text") or "")
        lowered = text.casefold()
        matched = [marker for marker in markers if marker.casefold() in lowered]
        if not matched:
            continue
        snippets: list[str] = []
        for marker in matched[:8]:
            index = lowered.find(marker.casefold())
            if index < 0:
                continue
            start = max(0, index - 120)
            end = min(len(text), index + len(marker) + 180)
            snippet = re.sub(r"\s+", " ", text[start:end]).strip()
            if not any(hint in snippet.casefold() for hint in SENSITIVE_HINTS):
                snippets.append(snippet)
        observations.append(
            {
                "id": script.get("id"),
                "type": script.get("type"),
                "src": script.get("src"),
                "text_length": len(text),
                "matched_markers": matched[:12],
                "snippets": snippets[:12],
            }
        )
        if len(observations) >= 20:
            break
    return observations


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is required for this temporary probe") from exc

    page_reports: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="OpportunityEngine/Auksjonen-Item-Identity-Probe-1.1"
        )
        page = context.new_page()

        for title, object_id in ITEMS:
            item_url = build_public_item_url(title, object_id)
            observations: list[dict[str, Any]] = []

            def observe(response: Any) -> None:
                content_type = response.headers.get("content-type", "")
                if not (
                    response.url.startswith("https://ny.auksjonen.no/api/")
                    or "application/json" in content_type.casefold()
                    or str(object_id) in response.url
                ):
                    return
                record: dict[str, Any] = {
                    "url": response.url,
                    "status": response.status,
                    "content_type": content_type,
                }
                if "application/json" in content_type.casefold():
                    try:
                        payload = response.json()
                        record["json_shape"] = _shape(payload)
                        record["identity_values"] = _walk_identity(payload)[:50]
                    except Exception as exc:  # diagnostic only
                        record["json_error"] = str(exc)
                observations.append(record)

            page.on("response", observe)
            page.goto(item_url, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(4_000)
            body_text = page.locator("body").inner_text(timeout=10_000)
            scripts = page.locator("script").evaluate_all(
                """nodes => nodes.map(node => ({
                    id: node.id || '',
                    type: node.type || '',
                    src: node.src || '',
                    text: node.textContent || ''
                }))"""
            )
            meta = page.evaluate(
                """() => ({
                    title: document.title || '',
                    description: document.querySelector('meta[name="description"]')?.content || '',
                    ogTitle: document.querySelector('meta[property="og:title"]')?.content || '',
                    ogDescription: document.querySelector('meta[property="og:description"]')?.content || ''
                })"""
            )
            page.remove_listener("response", observe)

            by_url: dict[str, dict[str, Any]] = {}
            for observation in observations:
                by_url[observation["url"]] = observation
            page_reports.append(
                {
                    "title": title,
                    "object_id": object_id,
                    "item_url": item_url,
                    "meta": meta,
                    "identity_text_lines": _identity_text_lines(body_text),
                    "script_observations": _bounded_script_snippets(scripts, object_id),
                    "network_observations": list(by_url.values()),
                }
            )
        browser.close()

    report = {
        "page_count": len(page_reports),
        "pages": page_reports,
        "address_values_logged": False,
        "contact_values_logged": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase_decision": False,
        "automatic_payment": False,
    }
    output = Path("artifacts/auksjonen-item-api-probe")
    output.mkdir(parents=True, exist_ok=True)
    path = output / "item-api-report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for page_report in page_reports:
        print(f"Item URL: {page_report['item_url']}")
        print(
            "Identity text lines: "
            + json.dumps(page_report["identity_text_lines"], ensure_ascii=False)
        )
        print(
            "Script observations: "
            + json.dumps(page_report["script_observations"], ensure_ascii=False)
        )
        print(f"Observed network responses: {len(page_report['network_observations'])}")
    print(f"Report: {path}")
    return 0 if page_reports else 2


if __name__ == "__main__":
    raise SystemExit(main())
