#!/usr/bin/env python3
"""Maintain a persistent, deduplicated lifecycle registry for discovered opportunities."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_object(path: Path) -> dict:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def canonical_url(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parts = urlsplit(value.strip())
    if not parts.netloc:
        return value.strip()
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not k.lower().startswith("utm_")]
    return urlunsplit((parts.scheme.lower() or "https", parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), ""))


def identity(item: dict) -> str:
    for key in ("opportunity_id", "lead_id", "id"):
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    url = canonical_url(item.get("canonical_url") or item.get("url"))
    if url:
        return "url-" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    fingerprint = "|".join(str(item.get(k) or "").strip().lower() for k in ("title", "city", "source"))
    return "item-" + hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:20]


def extract_items(payload: dict) -> list[dict]:
    for key in ("opportunities", "items", "rows", "ranked", "top_opportunities"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def lifecycle(item: dict) -> str:
    recommendation = str(item.get("recommendation") or "").upper()
    if recommendation in {"BUY", "BUY_REVIEW"}:
        return "ACTIONABLE_REVIEW"
    if recommendation == "REJECT":
        return "REJECTED"
    if item.get("opportunity_score") is not None:
        return "SCORED"
    return "DISCOVERED"


def merge_record(previous: dict | None, item: dict, now: str) -> dict:
    previous = previous or {}
    record = dict(previous)
    record.update({k: v for k, v in item.items() if v is not None})
    record["registry_id"] = identity(item)
    record["canonical_url"] = canonical_url(item.get("canonical_url") or item.get("url"))
    record["lifecycle_status"] = lifecycle(item)
    record["first_seen_at"] = previous.get("first_seen_at") or now
    record["last_seen_at"] = now
    record["runs_seen"] = int(previous.get("runs_seen") or 0) + 1
    return record


def build_registry(discovery: dict, scored: dict, existing: dict, generated_at: str) -> dict:
    current: dict[str, dict] = {}
    for item in [*extract_items(discovery), *extract_items(scored)]:
        current[identity(item)] = {**current.get(identity(item), {}), **item}

    old_records = existing.get("records", [])
    old_by_id = {
        str(item.get("registry_id")): item
        for item in old_records
        if isinstance(item, dict) and item.get("registry_id")
    } if isinstance(old_records, list) else {}

    records = [merge_record(old_by_id.get(key), item, generated_at) for key, item in sorted(current.items())]
    active_ids = set(current)
    for key, item in old_by_id.items():
        if key not in active_ids:
            stale = dict(item)
            stale["lifecycle_status"] = "NOT_SEEN_THIS_RUN"
            records.append(stale)

    counts: dict[str, int] = {}
    for record in records:
        status = str(record.get("lifecycle_status") or "UNKNOWN")
        counts[status] = counts.get(status, 0) + 1
    return {
        "schema_version": 1,
        "generated_at": generated_at,
        "record_count": len(records),
        "status_counts": counts,
        "records": sorted(records, key=lambda x: str(x.get("registry_id"))),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--discovery", default="data/discovery_leads.json")
    parser.add_argument("--scored", default="data/scored_opportunities.json")
    parser.add_argument("--existing", default="data/opportunity_registry.json")
    parser.add_argument("--output", default="data/opportunity_registry.json")
    args = parser.parse_args()
    generated_at = utc_now()
    payload = build_registry(
        load_object(Path(args.discovery)),
        load_object(Path(args.scored)),
        load_object(Path(args.existing)),
        generated_at,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "record_count": payload["record_count"], "status_counts": payload["status_counts"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
