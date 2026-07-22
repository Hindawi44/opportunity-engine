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
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from opportunity_engine.ods.brave_search import BraveSearchClient

_PRICE_NUMBER = r"(?:[0-9]{1,3}(?:[ .,'\u00a0][0-9]{3})+|[0-9]{3,8})"
_PRICE_PATTERNS = (
    re.compile(rf"(?:kr|nok)\s*({_PRICE_NUMBER})(?![0-9])", re.IGNORECASE),
    re.compile(rf"(?<![0-9])({_PRICE_NUMBER})\s*(?:kr|nok)\b", re.IGNORECASE),
)
_STOPWORDS = {
    "selges", "brukt", "norge", "komplett", "stk", "med", "for", "til", "og", "av",
    "pris", "bud", "artikler", "timer", "time", "min", "sek",
}
_MIN_SIMILARITY = 0.35
_REQUIRED_COMPARABLES = 3
_MAX_QUERY_VARIANTS = 3
_TRACKING_QUERY_KEYS = {"fbclid", "gclid", "ref", "source", "utm_campaign", "utm_content", "utm_medium", "utm_source", "utm_term"}


def _clean(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _tokens(value: object) -> set[str]:
    words = re.findall(r"[a-zA-ZæøåÆØÅ0-9]{3,}", _clean(value).casefold())
    return {word for word in words if word not in _STOPWORDS and not word.isdigit()}


def _base_query(item: dict[str, object]) -> str:
    return _clean(item.get("market_search_query") or item.get("title"))


def _query(item: dict[str, object]) -> str:
    base = _base_query(item)
    return f"{base} brukt pris Norge" if base else ""


def _query_variants(item: dict[str, object]) -> list[str]:
    base = _base_query(item)
    if not base:
        return []
    core_words = [word for word in re.findall(r"[a-zA-ZæøåÆØÅ0-9]{3,}", base) if word.casefold() not in _STOPWORDS]
    compact = " ".join(core_words[:8]) or base
    variants = [
        f"{base} brukt pris Norge",
        f'"{compact}" selges kr',
        f"{compact} bruktmarked NOK",
    ]
    unique: list[str] = []
    seen: set[str] = set()
    for value in variants:
        normalized = _clean(value)
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            unique.append(normalized)
    return unique[:_MAX_QUERY_VARIANTS]


def _canonical_url(value: object) -> str:
    raw = _clean(value)
    if not raw:
        return ""
    parsed = urlparse(raw)
    host = parsed.netloc.casefold()
    path = re.sub(r"/{2,}", "/", parsed.path or "/").rstrip("/") or "/"
    query = urlencode(sorted((key, val) for key, val in parse_qsl(parsed.query, keep_blank_values=True) if key.casefold() not in _TRACKING_QUERY_KEYS))
    return urlunparse((parsed.scheme.casefold() or "https", host, path, "", query, ""))


def _extract_prices(text: str) -> list[float]:
    values: list[float] = []
    seen: set[float] = set()
    for pattern in _PRICE_PATTERNS:
        for match in pattern.finditer(text):
            digits = re.sub(r"[^0-9]", "", match.group(1))
            if not digits:
                continue
            value = float(digits)
            if 100 <= value <= 10_000_000 and value not in seen:
                seen.add(value)
                values.append(value)
    return values


def _extract_price(text: str) -> float | None:
    prices = _extract_prices(text)
    return prices[0] if prices else None


def _similarity(query: str, title: str, snippet: str) -> float:
    wanted = _tokens(query)
    if not wanted:
        return 0.0
    observed = _tokens(f"{title} {snippet}")
    return round(len(wanted & observed) / len(wanted), 3)


def _quantity(value: object) -> int | None:
    text = _clean(value).casefold()
    patterns = (
        re.compile(r"\b([1-9][0-9]?)\s*(?:stk|stykk|stykker)\b"),
        re.compile(r"\bpakke\s+med\s+([1-9][0-9]?)\b"),
        re.compile(r"\bsett\s+av\s+([1-9][0-9]?)\b"),
    )
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return int(match.group(1))
    return None


def _evaluate_candidate(item: dict[str, object], result: dict[str, object], query: str) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    title = _clean(result.get("title"))
    snippet = _clean(result.get("snippet"))
    url = _clean(result.get("url"))
    canonical_url = _canonical_url(url)
    observed_text = f"{title} {snippet}"
    prices = _extract_prices(observed_text)
    similarity = _similarity(query, title, snippet)
    source_quantity = _quantity(item.get("title") or item.get("market_search_query"))
    comparable_quantity = _quantity(observed_text)

    reasons: list[str] = []
    if not url:
        reasons.append("missing_url")
    if not prices:
        reasons.append("missing_observed_nok_price")
    if similarity < _MIN_SIMILARITY:
        reasons.append(f"similarity_below_{_MIN_SIMILARITY}")
    if source_quantity and comparable_quantity and source_quantity != comparable_quantity:
        reasons.append("quantity_mismatch")

    if reasons:
        return None, {
            "url": url or None,
            "canonical_url": canonical_url or None,
            "title": title or None,
            "similarity_score": similarity,
            "source_quantity": source_quantity,
            "comparable_quantity": comparable_quantity,
            "rejection_reasons": reasons,
        }

    quantity_status = "MATCHED" if source_quantity and comparable_quantity else "UNKNOWN"
    candidate = {
        "source": _clean(result.get("source")) or "Brave Search",
        "url": url,
        "canonical_url": canonical_url,
        "domain": urlparse(url).netloc.casefold(),
        "title": title,
        "snippet": snippet,
        "price_nok": prices[0],
        "observed_prices_nok": prices,
        "similarity_score": similarity,
        "source_quantity": source_quantity,
        "comparable_quantity": comparable_quantity,
        "quantity_status": quantity_status,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "verified": False,
        "verification_status": "REVIEW_REQUIRED",
    }
    return candidate, None


def _candidate(item: dict[str, object], result: dict[str, object], query: str) -> dict[str, object] | None:
    candidate, _ = _evaluate_candidate(item, result, query)
    return candidate


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
        queries = _query_variants(raw_item)
        candidates_by_url: dict[str, dict[str, object]] = {}
        rejected_candidates: list[dict[str, object]] = []
        source_url = _canonical_url(raw_item.get("url"))
        for query in queries:
            try:
                for result in client.search(query, count=args.results_per_query, country="NO", search_lang="no"):
                    candidate, rejection = _evaluate_candidate(raw_item, dict(result), query)
                    if candidate:
                        key = str(candidate.get("canonical_url") or candidate.get("url"))
                        if key and key != source_url:
                            candidate["matched_query"] = query
                            previous = candidates_by_url.get(key)
                            if previous is None or float(candidate["similarity_score"]) > float(previous["similarity_score"]):
                                candidates_by_url[key] = candidate
                    elif rejection:
                        rejection["matched_query"] = query
                        rejected_candidates.append(rejection)
            except RuntimeError as exc:
                errors[f"{opportunity_id or 'unknown'}:{query}"] = str(exc)

        candidates = sorted(candidates_by_url.values(), key=lambda item: (-float(item["similarity_score"]), str(item["domain"])))
        prices = [float(item["price_nok"]) for item in candidates]
        enough_candidates = len(candidates) >= _REQUIRED_COMPARABLES
        distinct_domains = len({str(item["domain"]) for item in candidates})
        records.append({
            "opportunity_id": opportunity_id,
            "title": raw_item.get("title"),
            "asking_price_nok": raw_item.get("asking_price_nok"),
            "market_search_query": queries[0] if queries else "",
            "market_search_queries": queries,
            "query_count": len(queries),
            "candidate_count": len(candidates),
            "distinct_domain_count": distinct_domains,
            "candidate_price_min_nok": min(prices) if prices else None,
            "candidate_price_median_nok": median(prices) if prices else None,
            "candidate_price_max_nok": max(prices) if prices else None,
            "candidate_market_value_nok": median(prices) if enough_candidates else None,
            "required_verified_comparables": _REQUIRED_COMPARABLES,
            "verified_comparable_count": 0,
            "eligible_for_market_value": enough_candidates,
            "market_value_status": (
                "REVIEW_REQUIRED" if enough_candidates else
                "INSUFFICIENT_PRICE_CANDIDATES" if candidates else
                "NO_PRICE_CANDIDATES"
            ),
            "candidates": candidates,
            "rejected_candidate_count": len(rejected_candidates),
            "rejected_candidates": rejected_candidates,
        })

    output_payload = {
        "schema_version": 3,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": (
            "Brave Search multi-query candidate discovery with strict NOK parsing, URL deduplication, "
            "similarity and quantity checks; prices are unverified and never used automatically for a buy decision"
        ),
        "minimum_similarity": _MIN_SIMILARITY,
        "required_comparables": _REQUIRED_COMPARABLES,
        "max_query_variants": _MAX_QUERY_VARIANTS,
        "opportunity_count": len(records),
        "candidate_count": sum(int(item["candidate_count"]) for item in records),
        "rejected_candidate_count": sum(int(item["rejected_candidate_count"]) for item in records),
        "errors": errors,
        "opportunities": records,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "opportunity_count": len(records),
        "candidate_count": output_payload["candidate_count"],
        "rejected_candidate_count": output_payload["rejected_candidate_count"],
        "error_count": len(errors),
    }, ensure_ascii=False))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
