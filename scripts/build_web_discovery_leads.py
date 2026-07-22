#!/usr/bin/env python3
"""Build discovery_leads.json from an authorized search-provider export.

Input schema:
{
  "results": [
    {"title": "...", "url": "https://...", "snippet": "...", ...}
  ]
}

This script does not scrape Google, Facebook, FINN, or other sites directly.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path

from opportunity_engine.ods.web_discovery import WebSearchResult, build_discovery_leads


def _read_results(path: str) -> tuple[WebSearchResult, ...]:
    file_path = Path(path)
    if not file_path.exists():
        return ()
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    items = payload.get("results", payload) if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise RuntimeError("web discovery input must be a list or contain a results list")
    results: list[WebSearchResult] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        results.append(
            WebSearchResult(
                title=str(item.get("title") or ""),
                url=str(item.get("url") or ""),
                snippet=str(item.get("snippet") or item.get("description") or ""),
                source=str(item.get("source") or "").strip() or None,
                city=str(item.get("city") or "").strip() or None,
                published_at=str(item.get("published_at") or "").strip() or None,
                image_count=item.get("image_count") if isinstance(item.get("image_count"), int) else None,
                price_nok=float(item["price_nok"]) if isinstance(item.get("price_nok"), (int, float)) else None,
            )
        )
    return tuple(results)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/web_search_results.json")
    parser.add_argument("--output", default="data/discovery_leads.json")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    if args.limit <= 0:
        raise ValueError("limit must be positive")

    raw_results = _read_results(args.input)
    leads = build_discovery_leads(raw_results)[: args.limit]
    source_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for lead in leads:
        source_counts[lead.source] = source_counts.get(lead.source, 0) + 1
        for category in lead.categories:
            category_counts[category] = category_counts.get(category, 0) + 1

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "authorized search-provider results are normalized, classified, deduplicated by canonical URL, and ranked without inventing missing facts",
        "input_result_count": len(raw_results),
        "deduplicated_lead_count": len(leads),
        "source_counts": source_counts,
        "category_counts": category_counts,
        "items": [asdict(lead) for lead in leads],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "lead_count": len(leads)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
