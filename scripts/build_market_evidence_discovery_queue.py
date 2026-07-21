#!/usr/bin/env python3
"""Build a conservative market-evidence discovery queue.

This stage does not scrape marketplaces, mark evidence verified, or invent prices.
It prepares precise search tasks and source URLs for human or authorized-agent review.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus


def _clean(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _query(item: dict[str, object]) -> str:
    explicit = _clean(item.get("market_search_query"))
    return explicit or _clean(item.get("title"))


def _source_links(query: str) -> list[dict[str, object]]:
    encoded = quote_plus(query)
    return [
        {
            "source": "FINN Torget",
            "search_url": f"https://www.finn.no/bap/forsale/search.html?q={encoded}",
            "authorized": False,
            "status": "REVIEW_REQUIRED",
        },
        {
            "source": "Auksjonen.no",
            "search_url": f"https://www.auksjonen.no/auksjoner/?q={encoded}",
            "authorized": True,
            "status": "REVIEW_REQUIRED",
        },
        {
            "source": "Google Norway",
            "search_url": f"https://www.google.com/search?q={encoded}+pris+Norge",
            "authorized": False,
            "status": "REVIEW_REQUIRED",
        },
    ]


def _task(item: dict[str, object]) -> dict[str, object]:
    query = _query(item)
    return {
        "opportunity_id": _clean(item.get("opportunity_id")),
        "title": item.get("title"),
        "opportunity_url": item.get("url"),
        "asking_price_nok": item.get("asking_price_nok"),
        "market_search_query": query,
        "required_verified_comparables": 3,
        "accepted_comparable_fields": [
            "source",
            "url",
            "price_nok",
            "condition",
            "captured_at",
            "verified",
        ],
        "verification_rule": (
            "Accept only after a reviewer confirms material similarity, an accessible URL, "
            "and a directly observed NOK price."
        ),
        "candidate_sources": _source_links(query) if query else [],
        "status": "SEARCH_REQUIRED" if query else "QUERY_REQUIRED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default="data/opportunity_review_queue.json")
    parser.add_argument("--output", default="data/market_evidence_discovery_queue.json")
    args = parser.parse_args()

    payload = json.loads(Path(args.queue).read_text(encoding="utf-8"))
    queue = payload.get("queue", [])
    if not isinstance(queue, list):
        raise ValueError("review queue must be a list")

    tasks = [_task(item) for item in queue if isinstance(item, dict) and item.get("opportunity_id")]
    output_payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_queue": args.queue,
        "method": "discovery tasks only; no scraping, verification, prices, or costs are invented",
        "task_count": len(tasks),
        "search_required_count": sum(item["status"] == "SEARCH_REQUIRED" for item in tasks),
        "tasks": tasks,
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(output_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"task_count": len(tasks), "output": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
