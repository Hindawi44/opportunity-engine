#!/usr/bin/env python3
"""Audit cross-source duplicates conservatively without automatic external actions."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_KEYS = {"fbclid", "gclid", "ref", "source"}


def load_items(path: Path) -> list[dict]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return []
    for key in ("opportunities", "items", "rows", "ranked", "top_opportunities"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def canonical_url(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parts = urlsplit(value.strip())
    if not parts.netloc:
        return None
    query = [
        (key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_KEYS
    ]
    path = re.sub(r"/+", "/", parts.path).rstrip("/") or "/"
    return urlunsplit(("https", parts.netloc.lower(), path, urlencode(sorted(query)), ""))


def normalize_text(value: object) -> str:
    return re.sub(r"[^a-z0-9æøå]+", " ", str(value or "").casefold()).strip()


def source_name(item: dict) -> str:
    return str(item.get("source_name") or item.get("source") or "UNKNOWN").strip() or "UNKNOWN"


def record_id(item: dict) -> str:
    return str(item.get("source_document_id") or item.get("opportunity_id") or item.get("lead_id") or item.get("id") or "").strip()


def price(item: dict) -> float | None:
    value = item.get("asking_price_nok", item.get("current_price_nok", item.get("price_nok")))
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def title_similarity(left: dict, right: dict) -> float:
    a = normalize_text(left.get("title"))
    b = normalize_text(right.get("title"))
    return SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def same_city(left: dict, right: dict) -> bool:
    a = normalize_text(left.get("city"))
    b = normalize_text(right.get("city"))
    return bool(a and b and a == b)


def close_price(left: dict, right: dict) -> bool:
    a, b = price(left), price(right)
    if a is None or b is None:
        return False
    tolerance = max(250.0, min(a, b) * 0.05)
    return abs(a - b) <= tolerance


def classify(left: dict, right: dict) -> str | None:
    left_url = canonical_url(left.get("canonical_url") or left.get("url"))
    right_url = canonical_url(right.get("canonical_url") or right.get("url"))
    if left_url and right_url and left_url == right_url:
        return "EXACT_URL"

    similarity = title_similarity(left, right)
    city_matches = same_city(left, right)
    price_matches = close_price(left, right)
    if city_matches and price_matches and similarity >= 0.88:
        return "STRONG_FINGERPRINT"
    if city_matches and similarity >= 0.72:
        return "POSSIBLE_DUPLICATE_REVIEW"
    return None


def build_audit(groups: list[tuple[str, list[dict]]]) -> dict:
    records: list[dict] = []
    for channel, items in groups:
        for item in items:
            enriched = dict(item)
            enriched["_audit_channel"] = channel
            records.append(enriched)

    matches: list[dict] = []
    merged_pairs = 0
    review_pairs = 0
    for index, left in enumerate(records):
        for right in records[index + 1:]:
            if source_name(left) == source_name(right):
                continue
            match_type = classify(left, right)
            if not match_type:
                continue
            auto_merge = match_type in {"EXACT_URL", "STRONG_FINGERPRINT"}
            merged_pairs += int(auto_merge)
            review_pairs += int(not auto_merge)
            matches.append({
                "match_type": match_type,
                "automatic_merge": auto_merge,
                "title_similarity": round(title_similarity(left, right), 4),
                "canonical_url": canonical_url(left.get("canonical_url") or left.get("url")) if match_type == "EXACT_URL" else None,
                "source_names": list(dict.fromkeys([source_name(left), source_name(right)])),
                "source_record_ids": list(dict.fromkeys([record_id(left), record_id(right)])),
                "titles": [str(left.get("title") or ""), str(right.get("title") or "")],
                "cities": [left.get("city"), right.get("city")],
                "prices_nok": [price(left), price(right)],
            })

    counts = {"EXACT_URL": 0, "STRONG_FINGERPRINT": 0, "POSSIBLE_DUPLICATE_REVIEW": 0}
    for item in matches:
        counts[item["match_type"]] += 1
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "conservative cross-source audit; weak similarity never auto-merges",
        "input_record_count": len(records),
        "source_names": sorted({source_name(item) for item in records}),
        "match_counts": counts,
        "automatic_merge_pair_count": merged_pairs,
        "possible_duplicate_review_count": review_pairs,
        "matches": matches,
        "automatic_purchase": False,
        "automatic_bid": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--daily", default="data/todays_opportunities.json")
    parser.add_argument("--discovery", default="data/discovery_leads.json")
    parser.add_argument("--events", default="data/public_auction_event_leads.json")
    parser.add_argument("--output", default="data/cross_source_deduplication_audit.json")
    args = parser.parse_args()
    payload = build_audit([
        ("daily", load_items(Path(args.daily))),
        ("discovery", load_items(Path(args.discovery))),
        ("public_auction_events", load_items(Path(args.events))),
    ])
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "match_counts": payload["match_counts"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
