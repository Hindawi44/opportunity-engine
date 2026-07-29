#!/usr/bin/env python3
"""Read one discovered public Auksjonen clothing API endpoint without paid search."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

from opportunity_engine.discovery.auksjonen_live_probe import extract_candidate_objects

DEFAULT_ENDPOINT = (
    "https://ny.auksjonen.no/api/category-search/search"
    "?category2=10110508&from=1&to=30&asc=true&orderBy=endTime"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument(
        "--output-dir",
        default="artifacts/auksjonen-public-api-probe",
    )
    args = parser.parse_args()

    request = Request(
        args.endpoint,
        headers={
            "Accept": "application/json",
            "User-Agent": "OpportunityEngine/Auksjonen-Public-API-Probe-1.0",
        },
    )
    with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed public HTTPS endpoint
        raw = response.read()
        status = int(response.status)
        final_url = response.geturl()
        content_type = response.headers.get("content-type", "")

    payload = json.loads(raw.decode("utf-8"))
    candidates = extract_candidate_objects(payload, limit=50)
    items = payload.get("items", []) if isinstance(payload, dict) else []

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": "auksjonen-public-api-probe-1.0",
        "endpoint": args.endpoint,
        "final_url": final_url,
        "http_status": status,
        "content_type": content_type,
        "reported_size": payload.get("size") if isinstance(payload, dict) else None,
        "items_received": len(items) if isinstance(items, list) else 0,
        "first_item_keys": (
            sorted(str(key) for key in items[0].keys())
            if isinstance(items, list) and items and isinstance(items[0], dict)
            else []
        ),
        "candidate_count": len(candidates),
        "candidate_objects": candidates,
        "payload": payload,
        "paid_search_used": False,
        "openai_api_used": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase_decision": False,
        "automatic_payment": False,
    }
    report_path = output_dir / "auksjonen-public-api-probe.json"
    summary_path = output_dir / "operator-summary.txt"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(
        "\n".join([
            "Auksjonen public API probe",
            f"Endpoint: {args.endpoint}",
            f"HTTP status: {status}",
            f"Reported size: {report['reported_size']}",
            f"Items received: {report['items_received']}",
            f"Candidate objects: {len(candidates)}",
            f"First item keys: {', '.join(report['first_item_keys'])}",
            "Paid Brave/OpenAI calls: 0",
        ]) + "\n",
        encoding="utf-8",
    )
    print(summary_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
