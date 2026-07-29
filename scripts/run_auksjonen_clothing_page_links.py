#!/usr/bin/env python3
"""Capture exact public auction URLs from the live Auksjonen clothing page."""
from __future__ import annotations

import json
import re
from pathlib import Path

ENTRY_URL = "https://ny.auksjonen.no/auksjoner/klaerkosmetikk"
OUTPUT_DIR = Path("artifacts/auksjonen-clothing-page-links")
CLOTHING_PATTERN = re.compile(
    r"klær|jakke|bukse|sko|kjole|skjorte|genser|frakk|dress|vest|tøy|arbeids|mc-|mote|tekstil|veske",
    re.I,
)


def main() -> int:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="OpportunityEngine/Auksjonen-Clothing-Link-Probe-1.0"
        )
        page = context.new_page()
        page.set_default_navigation_timeout(30_000)
        try:
            page.goto(ENTRY_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(7_000)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2_000)
            final_url = page.url
            rows = page.locator("a[href]").evaluate_all(
                """anchors => anchors.map(a => {
                  const card = a.closest('article, li, [class*="card"], [data-testid*="auction"]') || a.parentElement;
                  return {
                    url: a.href || '',
                    text: (card?.innerText || a.innerText || a.getAttribute('aria-label') || '').trim()
                  };
                })"""
            )
        finally:
            context.close()
            browser.close()

    unique: dict[str, dict[str, str]] = {}
    for row in rows:
        url = " ".join(str(row.get("url") or "").split())
        text = " ".join(str(row.get("text") or "").split())[:4000]
        if not url or not CLOTHING_PATTERN.search(text):
            continue
        if "ny.auksjonen.no" not in url:
            continue
        unique.setdefault(url, {"url": url, "text": text})

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": "auksjonen-clothing-page-links-1.0",
        "entry_url": ENTRY_URL,
        "final_url": final_url,
        "links": list(unique.values()),
        "link_count": len(unique),
        "paid_search_used": False,
        "openai_api_used": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase_decision": False,
        "automatic_payment": False,
    }
    (OUTPUT_DIR / "auksjonen-clothing-page-links.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUTPUT_DIR / "operator-summary.txt").write_text(
        "\n".join([
            "Auksjonen clothing-page link capture",
            f"Entry URL: {ENTRY_URL}",
            f"Final URL: {final_url}",
            f"Clothing links found: {len(unique)}",
            "Paid Brave/OpenAI calls: 0",
            "",
            *(f"- {item['url']} | {item['text'][:180]}" for item in list(unique.values())[:20]),
        ]) + "\n",
        encoding="utf-8",
    )
    print((OUTPUT_DIR / "operator-summary.txt").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
