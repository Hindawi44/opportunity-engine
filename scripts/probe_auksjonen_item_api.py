#!/usr/bin/env python3
"""Observe public API calls made by one Auksjonen item page.

Temporary bounded diagnostic: one public item page, no login, no interaction, no
contact, no bid, no purchase, and no payment. Only API URLs, JSON keys, and
identity-related values are retained.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from opportunity_engine.discovery.auksjonen_public_api_adapter import (
    build_public_item_url,
)

TITLE = "TOLLAUKSJON - Smykkesett i 21k gull – flere sett (samlet)"
OBJECT_ID = 564704
ITEM_URL = build_public_item_url(TITLE, OBJECT_ID)
IDENTITY_HINTS = (
    "principal",
    "organization",
    "organisation",
    "seller",
    "customer",
    "company",
    "owner",
    "debtor",
    "debitor",
    "orgnr",
    "orgnumber",
    "business",
)
SENSITIVE_HINTS = (
    "address",
    "email",
    "phone",
    "mobile",
    "contact",
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


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is required for this temporary probe") from exc

    observations: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="OpportunityEngine/Auksjonen-Item-API-Probe-1.0"
        )
        page = context.new_page()

        def observe(response: Any) -> None:
            if not response.url.startswith("https://ny.auksjonen.no/api/"):
                return
            record: dict[str, Any] = {
                "url": response.url,
                "status": response.status,
                "content_type": response.headers.get("content-type", ""),
            }
            if "application/json" in record["content_type"].casefold():
                try:
                    payload = response.json()
                    record["json_shape"] = _shape(payload)
                    record["identity_values"] = _walk_identity(payload)[:50]
                except Exception as exc:  # diagnostic only
                    record["json_error"] = str(exc)
            observations.append(record)

        page.on("response", observe)
        page.goto(ITEM_URL, wait_until="domcontentloaded", timeout=45_000)
        page.wait_for_timeout(5_000)
        browser.close()

    by_url: dict[str, dict[str, Any]] = {}
    for observation in observations:
        by_url[observation["url"]] = observation
    report = {
        "item_url": ITEM_URL,
        "object_id": OBJECT_ID,
        "api_response_count": len(by_url),
        "api_responses": list(by_url.values()),
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

    print(f"Item URL: {ITEM_URL}")
    print(f"API response count: {len(by_url)}")
    for response in by_url.values():
        print(f"API: {response['status']} {response['url']}")
        print(
            "Identity values: "
            + json.dumps(response.get("identity_values", []), ensure_ascii=False)
        )
        shape = response.get("json_shape")
        if isinstance(shape, Mapping):
            print(f"Top-level JSON keys: {sorted(shape)}")
    print(f"Report: {path}")
    return 0 if by_url else 2


if __name__ == "__main__":
    raise SystemExit(main())
