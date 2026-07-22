#!/usr/bin/env python3
"""Collect bounded Brave Search results for the Web Discovery Engine."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from opportunity_engine.ods.brave_search import BraveSearchClient


def _read_config(path: str) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Brave search config must be a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/brave_search_queries.json")
    parser.add_argument("--output", default="data/web_search_results.json")
    args = parser.parse_args()

    api_key = os.getenv("BRAVE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("BRAVE_API_KEY is not configured")

    config = _read_config(args.config)
    queries = config.get("queries", [])
    if not isinstance(queries, list):
        raise RuntimeError("queries must be a list")
    max_queries = int(config.get("max_queries_per_run", 10) or 10)
    count = int(config.get("results_per_query", 10) or 10)
    country = str(config.get("country") or "NO")
    search_lang = str(config.get("search_lang") or "no")

    client = BraveSearchClient(api_key=api_key)
    combined: list[dict[str, object]] = []
    errors: dict[str, str] = {}
    request_count = 0

    for raw_query in queries[:max_queries]:
        query = str(raw_query or "").strip()
        if not query:
            continue
        request_count += 1
        try:
            for item in client.search(query, count=count, country=country, search_lang=search_lang):
                enriched = dict(item)
                enriched["discovery_query"] = query
                combined.append(enriched)
        except RuntimeError as exc:
            message = str(exc)
            errors[query] = message
            print(
                json.dumps(
                    {
                        "event": "brave_search_error",
                        "query": query,
                        "error": message,
                    },
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": "Brave Search API",
        "request_count": request_count,
        "result_count": len(combined),
        "errors": errors,
        "results": combined,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "output": str(output),
                "request_count": request_count,
                "result_count": len(combined),
                "error_count": len(errors),
            },
            ensure_ascii=False,
        )
    )
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
