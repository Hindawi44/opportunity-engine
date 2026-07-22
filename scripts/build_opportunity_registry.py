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
    tracking = {"fbclid", "gclid", "ref", "source"}
    query = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in tracking
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", parts.netloc.lower(), path, urlencode(sorted(query)), ""))


def raw_record_id(item: dict) -> str | None:
    for key in ("source_document_id", "opportunity_id", "lead_id", "id"):
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def identity(item: dict) -> str:
    """Use the normalized URL first so source-specific IDs cannot create duplicates."""
    url = canonical_url(item.get("canonical_url") or item.get("url"))
    if url:
        return "url-" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    record_id = raw_record_id(item)
    if record_id:
        return record_id
    fingerprint = "|".join(str(item.get(k) or "").strip().lower() for k in ("title", "city", "source"))
    return "item-" + hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:20]


def audit_aliases(audit: dict) -> dict[str, str]:
    aliases: dict[str, str] = {}
    matches = audit.get("matches") if isinstance(audit.get("matches"), list) else []
    for match in matches:
        if not isinstance(match, dict) or not match.get("automatic_merge"):
            continue
        ids = sorted({str(value) for value in match.get("source_record_ids", []) if value})
        if len(ids) < 2:
            continue
        group_id = "dedup-" + hashlib.sha256("|".join(ids).encode("utf-8")).hexdigest()[:20]
        for value in ids:
            aliases[value] = group_id
    return aliases


def resolved_identity(item: dict, aliases: dict[str, str]) -> str:
    url = canonical_url(item.get("canonical_url") or item.get("url"))
    if url:
        url_key = "url-" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
        record_id = raw_record_id(item)
        if record_id and record_id in aliases:
            return aliases[record_id]
        return url_key
    record_id = raw_record_id(item)
    if record_id and record_id in aliases:
        return aliases[record_id]
    return identity(item)


def extract_items(payload: dict) -> list[dict]:
    for key in ("opportunities", "items", "rows", "ranked", "top_opportunities"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def lifecycle(item: dict) -> str:
    recommendation = str(item.get("final_decision") or item.get("recommendation") or "").upper()
    if recommendation in {"BUY", "BUY_REVIEW"}:
        return "ACTIONABLE_REVIEW"
    if recommendation == "REJECT":
        return "REJECTED"
    if item.get("opportunity_score") is not None:
        return "SCORED"
    return "DISCOVERED"


def _as_list(value: object) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def provenance(item: dict) -> tuple[list[str], list[str]]:
    metadata = item.get("raw_metadata") if isinstance(item.get("raw_metadata"), dict) else {}
    names = _as_list(item.get("source_names") or metadata.get("merged_source_names"))
    ids = _as_list(item.get("source_record_ids") or metadata.get("merged_source_document_ids"))
    source = item.get("source_name") or item.get("source")
    record_id = raw_record_id(item)
    if source:
        names.append(str(source))
    if record_id:
        ids.append(record_id)
    return list(dict.fromkeys(names)), list(dict.fromkeys(ids))


def combine_items(previous: dict, current: dict) -> dict:
    combined = {**previous, **{k: v for k, v in current.items() if v is not None}}
    previous_names, previous_ids = provenance(previous)
    current_names, current_ids = provenance(current)
    combined["source_names"] = list(dict.fromkeys([*previous_names, *current_names]))
    combined["source_record_ids"] = list(dict.fromkeys([*previous_ids, *current_ids]))
    return combined


def merge_record(previous: dict | None, item: dict, now: str, registry_id: str) -> dict:
    previous = previous or {}
    record = combine_items(previous, item)
    record["registry_id"] = registry_id
    record["canonical_url"] = canonical_url(item.get("canonical_url") or item.get("url"))
    record["lifecycle_status"] = lifecycle(item)
    record["first_seen_at"] = previous.get("first_seen_at") or now
    record["last_seen_at"] = now
    record["runs_seen"] = int(previous.get("runs_seen") or 0) + 1
    return record


def build_registry(discovery: dict, scored: dict, existing: dict, audit: dict, generated_at: str) -> dict:
    aliases = audit_aliases(audit)
    current: dict[str, dict] = {}
    for item in [*extract_items(discovery), *extract_items(scored)]:
        key = resolved_identity(item, aliases)
        current[key] = combine_items(current.get(key, {}), item)

    old_records = existing.get("records", [])
    old_by_id = {
        str(item.get("registry_id")): item
        for item in old_records
        if isinstance(item, dict) and item.get("registry_id")
    } if isinstance(old_records, list) else {}

    records = [merge_record(old_by_id.get(key), item, generated_at, key) for key, item in sorted(current.items())]
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
        "schema_version": 3,
        "generated_at": generated_at,
        "record_count": len(records),
        "status_counts": counts,
        "cross_source_alias_count": len(set(aliases.values())),
        "records": sorted(records, key=lambda x: str(x.get("registry_id"))),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--discovery", default="data/discovery_leads.json")
    parser.add_argument("--scored", default="data/scored_opportunities.json")
    parser.add_argument("--existing", default="data/opportunity_registry.json")
    parser.add_argument("--audit", default="data/cross_source_deduplication_audit.json")
    parser.add_argument("--output", default="data/opportunity_registry.json")
    args = parser.parse_args()
    generated_at = utc_now()
    payload = build_registry(
        load_object(Path(args.discovery)),
        load_object(Path(args.scored)),
        load_object(Path(args.existing)),
        load_object(Path(args.audit)),
        generated_at,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "record_count": payload["record_count"], "status_counts": payload["status_counts"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
