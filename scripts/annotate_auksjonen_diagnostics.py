#!/usr/bin/env python3
"""Annotate an empty Auksjonen snapshot with safe page diagnostics.

This script does not bypass access controls. It requests only the public listing
page and records structural signals that help explain why zero listings were
parsed.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

AUKSJONEN_URL = "https://www.auksjonen.no/auksjoner/"


def inspect_public_page(url: str = AUKSJONEN_URL, timeout: float = 15.0) -> dict[str, object]:
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "Opportunity-Engine/1.0 (+public-listing-research)",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed HTTPS host
            charset = response.headers.get_content_charset() or "utf-8"
            html = response.read().decode(charset, errors="replace")
            final_url = response.geturl()
            status = getattr(response, "status", 200)
    except HTTPError as exc:
        return {"request_ok": False, "http_status": exc.code, "error": f"HTTP {exc.code}"}
    except URLError as exc:
        return {"request_ok": False, "error": f"Request failed: {exc.reason}"}

    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else None
    lowered = html.casefold()

    return {
        "request_ok": True,
        "http_status": status,
        "final_url": final_url,
        "html_length": len(html),
        "page_title": title,
        "contains_auction_link": "/auksjon" in lowered,
        "contains_json_ld": "application/ld+json" in lowered,
        "contains_next_data": "__next_data__" in lowered,
        "contains_nuxt_data": "__nuxt__" in lowered,
        "contains_cloudflare_marker": "cloudflare" in lowered or "cf-ray" in lowered,
    }


def annotate_snapshot(path: Path) -> bool:
    payload = json.loads(path.read_text(encoding="utf-8"))
    source_counts = payload.get("sources") or payload.get("source_counts") or {}
    auksjonen_count = int(source_counts.get("Auksjonen.no", 0) or 0)
    if auksjonen_count != 0:
        return False

    diagnostics = inspect_public_page()
    errors = dict(payload.get("source_errors") or {})
    errors["Auksjonen.no"] = (
        "Public page loaded but the connector parsed zero listings. "
        "The page structure may have changed or listings may be rendered by JavaScript."
    )
    payload["source_errors"] = errors
    payload["source_diagnostics"] = {
        **dict(payload.get("source_diagnostics") or {}),
        "Auksjonen.no": diagnostics,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"annotated": True, "Auksjonen.no": diagnostics}, ensure_ascii=False, sort_keys=True))
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", default="data/todays_opportunities.json")
    args = parser.parse_args()
    path = Path(args.snapshot)
    if not path.exists():
        raise FileNotFoundError(path)
    annotated = annotate_snapshot(path)
    if not annotated:
        print(json.dumps({"annotated": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
