#!/usr/bin/env python3
"""Collect conservative market-price candidates with Brave Search.

This stage discovers candidate comparables only. It never marks a comparable
verified and never feeds an estimated value into the buy decision automatically.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from statistics import median
from urllib.parse import urlparse

from opportunity_engine.ods.brave_search import BraveSearchClient

_PRICE_PATTERNS = (
    re.compile(r"(?:kr|nok)\s*([0-9][0-9 .\u00a0]{1,12})", re.IGNORECASE),
    re.compile(r"([0-9][0-9 .\u00a0]{1,12})\s*(?:kr|nok)\b", re.IGNORECASE),
)
_STOPWORDS = {"selges", "brukt", "norge", "komplett", "stk", "med", "for", "til", "og", "av"}


def _clean(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _tokens(value: object) -> set[str]:
    words = re.findall(r"[a-zA-ZæøåÆØÅ0-9]{3,}", _clean(value).casefold())
    return {word for word in words if word not in _STOPWORDS and not word.isdigit()}


def _query(item: dict[str, object]) -> str:
    base = _clean(item.get("market_search_query") or item.get("title"))
    return f"{base} brukt pris Norge" if base else ""


def _extract_price(text: str) -> float | None:
    for pattern in _PRICE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        digits = re.sub(r"[^0-9]", "", match.group(1))
        if not digits:
            continue
        value = float(digits)
        if 100 <= value <= 10_000_000:
            return value
    return None


def _similarity(query: str, title: str, snippet: str) -> float:
    wanted = _tokens(query)
    if not wanted:
        return 0.0
    observed = _tokens(f"{title} {snippet}")
    return round(len(wanted & observed) / len(wanted), 3)


def _candidate(item: dict[str, object], result: dict[str, object], query: str) -> dict[str, object] | None:
    title = _clean(result.get("title"))
    snippet = _clean(result.get("snippet"))
    url = _clean(result.get("url"))
    price = _extract_price(f"{title} {snippet}")
    similarity = _similarity(query, title, snippet)
    if not url or price is None or similarity < 0.2:
        return None
    return {
        "source": _clean(result.get("source")) or "Brave Search",
        "url": url,
        "domain": urlparse(url).netloc.casefold(),
        "title": title,
        "snippet": snippet,
        "price_nok": price,
        "similarity_score": similarity,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "verified": False,
        "verification_status": "REVIEW_REQUIRED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default="data/opportunity_review_queue.json")
    parser.add_argument("--output", default="data/market_price_candidates.json")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--results-per-query", type=int, default=10)
    args = parser.parse_args()

    api_key = os.getenv("BRAVE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("BRAVE_API_KEY is not configured")

    payload = json.loads(Path(args.queue).read_text(encoding="utf-8"))
    queue = payload.get("queue", [])
    if not isinstance(queue, list):
        raise ValueError("review queue must be a list")

    client = BraveSearchClient(api_key=api_key)
    records: list[dict[str, object]] = []
    errors: dict[str, str] = {}

    for raw_item in queue[: max(args.limit, 0)]:
        if not isinstance(raw_item, dict):
            continue
        opportunity_id = _clean(raw_item.get("opportunity_id"))
        query = _query(raw_item)
        candidates: list[dict[str, object]] = []
        if query:
            try:
                for result in client.search(query, count=args.results_per_query, country="NO", search_lang="no"):
                    candidate = _candidate(raw_item, dict(result), query)
                    if candidate and candidate["url"] != raw_item.get("url"):
                        candidates.append(candidate)
            except RuntimeError as exc:
                errors[opportunity_id or query] = str(exc)

        prices = [float(item["price_nok"]) for item in candidates]
        records.append({
            "opportunity_id": opportunity_id,
            "title": raw_item.get("title"),
            "asking_price_nok": raw_item.get("asking_price_nok"),
            "market_search_query": query,
            "candidate_count": len(candidates),
            "candidate_price_min_nok": min(prices) if prices else None,
            "candidate_price_median_nok": median(prices) if prices else None,
            "candidate_price_max_nok": max(prices) if prices else None,
            "required_verified_comparables": 3,
            "verified_comparable_count": 0,
            "market_value_status": "REVIEW_REQUIRED" if candidates else "NO_PRICE_CANDIDATES",
            "candidates": candidates,
        })

    output_payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "Brave Search candidate discovery; prices are unverified and never used automatically for a buy decision",
        "opportunity_count": len(records),
        "candidate_count": sum(int(item["candidate_count"]) for item in records),
        "errors": errors,
        "opportunities": records,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "opportunity_count": len(records), "candidate_count": output_payload["candidate_count"], "error_count": len(errors)}, ensure_ascii=False))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
