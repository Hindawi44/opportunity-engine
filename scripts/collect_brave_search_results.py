#!/usr/bin/env python3
"""Collect bounded Brave Search results for the Web Discovery Engine.

Explicitly promoted learned terms may consume a bounded share of the existing
Core query slots. They replace static requests one-for-one; they never increase
the baseline Brave request count. Shadow or otherwise unpromoted overlay rows
fail closed and cannot affect the Core query plan.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

from opportunity_engine.learned_query_overlay import load_learned_query_overlay
from opportunity_engine.ods.brave_search import BraveSearchClient


_OVERLAY_ENV = "OPPORTUNITY_LEARNED_QUERY_OVERLAY_PATH"
_DEFAULT_OVERLAY_PATH = Path("learning") / "active-keyword-overlay.json"


def _read_config(path: str) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Brave search config must be a JSON object")
    return payload


def _fold(value: object) -> str:
    return " ".join(str(value or "").casefold().split()).strip()


def _overlay_path(environment: Mapping[str, str] | None = None) -> Path:
    env = environment if environment is not None else os.environ
    configured = str(env.get(_OVERLAY_ENV) or "").strip()
    return Path(configured) if configured else _DEFAULT_OVERLAY_PATH


def _load_promoted_terms(
    market_code: str,
    *,
    environment: Mapping[str, str] | None = None,
) -> tuple[list[str], Path, str | None]:
    """Load only fail-closed, explicitly promoted terms for one market."""
    path = _overlay_path(environment)
    if not path.exists():
        return [], path, None
    try:
        overlay = load_learned_query_overlay(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [], path, f"{type(exc).__name__}: {exc}"

    if (
        overlay.get("promotion_gate_enforced") is not True
        or overlay.get("automatic_query_activation") is not False
    ):
        return [], path, "UNSAFE_OVERLAY_METADATA"

    markets = overlay.get("markets")
    if not isinstance(markets, Mapping):
        return [], path, "UNSAFE_OVERLAY_MARKETS"
    rows = markets.get(market_code.upper())
    if not isinstance(rows, list):
        return [], path, None

    terms: list[str] = []
    seen: set[str] = set()
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        if str(raw.get("source_verdict") or "").strip().upper() != "PROVEN":
            continue
        if str(raw.get("promotion_status") or "").strip().upper() != "PROMOTED":
            continue
        if (
            str(raw.get("activation_source") or "").strip().upper()
            != "EXPLICIT_PROMOTION"
        ):
            continue
        term = _fold(raw.get("term"))
        if not term or term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return terms, path, None


def _exact_learned_query(term: str) -> str:
    safe = str(term or "").replace('"', "").strip()
    return f'"{safe}"' if safe else ""


def _compose_query_plan(
    raw_queries: Sequence[object],
    promoted_terms: Sequence[str],
    *,
    max_queries: int,
) -> tuple[list[dict[str, str | None]], int]:
    """Replace a bounded share of static Core slots with promoted learned terms.

    The final plan is never larger than the static plan that would have run
    without learning. With the normal eight-query Core budget, at most two slots
    are learned slots. Exact learned queries intentionally avoid product/vertical
    anchors so a proven market phrase can generalize beyond the source case.
    """
    static_queries = [
        str(raw or "").strip()
        for raw in raw_queries
        if str(raw or "").strip()
    ]
    baseline_request_count = min(max(0, max_queries), len(static_queries))
    if baseline_request_count == 0:
        return [], 0

    cleaned_terms: list[str] = []
    seen_terms: set[str] = set()
    for raw in promoted_terms:
        term = _fold(raw)
        if not term or term in seen_terms:
            continue
        seen_terms.add(term)
        cleaned_terms.append(term)

    learned_slot_cap = max(1, baseline_request_count // 4)
    selected_terms = cleaned_terms[: min(len(cleaned_terms), learned_slot_cap)]

    plan: list[dict[str, str | None]] = []
    seen_queries: set[str] = set()
    for term in selected_terms:
        query = _exact_learned_query(term)
        folded_query = _fold(query)
        if not query or folded_query in seen_queries:
            continue
        seen_queries.add(folded_query)
        plan.append(
            {
                "query": query,
                "source": "LEARNED_PROMOTED",
                "learned_term": term,
            }
        )

    for query in static_queries:
        if len(plan) >= baseline_request_count:
            break
        folded_query = _fold(query)
        if folded_query in seen_queries:
            continue
        seen_queries.add(folded_query)
        plan.append(
            {
                "query": query,
                "source": "STATIC_CORE",
                "learned_term": None,
            }
        )

    return plan, baseline_request_count


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
    country = str(config.get("country") or "NO").strip().upper()
    search_lang = str(config.get("search_lang") or "nb")

    promoted_terms, overlay_path, overlay_error = _load_promoted_terms(country)
    query_plan, baseline_request_count = _compose_query_plan(
        queries,
        promoted_terms,
        max_queries=max_queries,
    )
    applied_terms = [
        str(item["learned_term"])
        for item in query_plan
        if item.get("source") == "LEARNED_PROMOTED" and item.get("learned_term")
    ]

    client = BraveSearchClient(api_key=api_key)
    combined: list[dict[str, object]] = []
    errors: dict[str, str] = {}
    request_count = 0

    for plan_item in query_plan:
        query = str(plan_item.get("query") or "").strip()
        if not query:
            continue
        request_count += 1
        try:
            for item in client.search(
                query,
                count=count,
                country=country,
                search_lang=search_lang,
            ):
                enriched = dict(item)
                enriched["discovery_query"] = query
                enriched["discovery_query_source"] = plan_item.get("source")
                if plan_item.get("learned_term"):
                    enriched["learned_term"] = plan_item.get("learned_term")
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

    payload: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": "Brave Search API",
        "request_count": request_count,
        "result_count": len(combined),
        "errors": errors,
        "results": combined,
        "query_plan": query_plan,
        "learned_query_overlay": {
            "path": overlay_path.as_posix(),
            "load_error": overlay_error,
            "active_terms": promoted_terms,
            "applied_terms": applied_terms,
            "learned_query_slot_count": len(applied_terms),
            "baseline_static_request_count": baseline_request_count,
            "planned_request_count": len(query_plan),
            "static_queries_displaced": len(applied_terms),
            "extra_search_requests": max(0, len(query_plan) - baseline_request_count),
            "request_budget_unchanged": len(query_plan) == baseline_request_count,
            "promotion_gate_enforced": True,
            "automatic_query_activation": False,
        },
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
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
                "learned_query_slot_count": len(applied_terms),
                "applied_learned_terms": applied_terms,
                "request_budget_unchanged": len(query_plan) == baseline_request_count,
            },
            ensure_ascii=False,
        )
    )
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
