#!/usr/bin/env python3
"""Inspect public Auksjonen item keys needed for truthful cross-source matching.

This temporary diagnostic prints field names and a bounded set of public source
identity values. It never logs addresses, contacts, bids, purchases, or payments.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.request import Request, urlopen

ENDPOINT = (
    "https://ny.auksjonen.no/api/category-search/search"
    "?category2=10110508&from=1&to=30&asc=true&orderBy=endTime"
)
IDENTITY_HINTS = (
    "seller",
    "customer",
    "company",
    "owner",
    "debtor",
    "debitor",
    "org",
    "account",
    "client",
    "auctioneer",
    "provider",
    "vendor",
    "business",
    "principal",
)
SAFE_SAMPLE_KEYS = {
    "title",
    "objectId",
    "auctionId",
    "status",
    "category1",
    "category2",
    "category3",
    "city",
    "principal",
    "organizationCode",
    "organizationId",
    "projectId",
}
IDENTITY_VALUE_KEYS = (
    "principal",
    "organizationCode",
    "organizationId",
    "projectId",
)


def _safe_value(key: str, value: object) -> object | None:
    lowered = key.casefold()
    if key in SAFE_SAMPLE_KEYS or any(hint in lowered for hint in IDENTITY_HINTS):
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, Mapping):
            return {str(k): type(v).__name__ for k, v in value.items()}
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return [type(item).__name__ for item in value[:5]]
    return None


def _identity_value_summary(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key in IDENTITY_VALUE_KEYS:
        values: list[object] = []
        for item in items:
            value = item.get(key)
            if value in (None, ""):
                continue
            if value not in values:
                values.append(value)
            if len(values) >= 10:
                break
        summary[key] = {
            "nonempty_count": sum(1 for item in items if item.get(key) not in (None, "")),
            "unique_values_bounded": values,
        }
    return summary


def main() -> int:
    request = Request(
        ENDPOINT,
        headers={
            "Accept": "application/json",
            "User-Agent": "OpportunityEngine/Auksjonen-Cross-Source-Schema-Probe-1.1",
        },
    )
    with urlopen(request, timeout=30) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, Mapping):
        raise RuntimeError("Auksjonen response is not a JSON object")
    items = payload.get("items")
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        raise RuntimeError("Auksjonen response lacks an items array")

    mappings = [item for item in items if isinstance(item, Mapping)]
    keys = sorted({str(key) for item in mappings for key in item})
    identity_keys = [
        key for key in keys if any(hint in key.casefold() for hint in IDENTITY_HINTS)
    ]
    identity_values = _identity_value_summary(mappings)
    samples: list[dict[str, Any]] = []
    for item in mappings[:5]:
        sample: dict[str, Any] = {}
        for key, value in item.items():
            safe = _safe_value(str(key), value)
            if safe is not None:
                sample[str(key)] = safe
        samples.append(sample)

    report = {
        "endpoint": ENDPOINT,
        "reported_size": payload.get("size"),
        "items_received": len(mappings),
        "raw_item_keys": keys,
        "identity_candidate_keys": identity_keys,
        "identity_value_summary": identity_values,
        "safe_samples": samples,
        "address_values_logged": False,
        "contact_values_logged": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase_decision": False,
        "automatic_payment": False,
    }
    output = Path("artifacts/auksjonen-cross-source-schema")
    output.mkdir(parents=True, exist_ok=True)
    path = output / "schema-report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Items received: {len(mappings)}")
    print(f"Raw item keys: {keys}")
    print(f"Identity candidate keys: {identity_keys}")
    print(
        "Identity value summary: "
        + json.dumps(identity_values, ensure_ascii=False, sort_keys=True)
    )
    for index, sample in enumerate(samples, start=1):
        print(f"Safe sample {index}: {json.dumps(sample, ensure_ascii=False, sort_keys=True)}")
    print(f"Report: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
