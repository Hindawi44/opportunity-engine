#!/usr/bin/env python3
"""Run one bounded durable missed-opportunity learning cycle."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.cost_guard import manual_paid_brave_block_reason
from opportunity_engine.daily_learning_operator import (
    DailyLearningPolicy,
    run_daily_learning_cycle,
)
from opportunity_engine.discovery.brave_market_signal_radar import MARKET_QUERIES
from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.learned_query_overlay import (
    build_learned_query_overlay,
    load_learned_query_overlay,
    save_learned_query_overlay,
)
from opportunity_engine.missed_opportunity_learning import (
    MissedOpportunityCase,
    load_missed_opportunity_memory,
    save_missed_opportunity_memory,
)


HISTORY_SCHEMA = "keyword-learning-history-1.0"
INBOX_SCHEMA = "missed-opportunity-inbox-1.0"


def _read_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_object(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _load_inbox(path: Path) -> list[MissedOpportunityCase]:
    if not path.exists():
        return []
    payload = _read_object(path)
    if payload.get("schema_version") not in {None, INBOX_SCHEMA}:
        raise ValueError("unsupported missed-opportunity inbox schema")
    rows = payload.get("cases") or []
    if not isinstance(rows, list):
        raise ValueError("missed-opportunity inbox cases must be a list")
    return [
        MissedOpportunityCase.from_dict(row)
        for row in rows
        if isinstance(row, Mapping)
    ]


def _load_active_queries(path: Path) -> list[str]:
    queries: list[str] = []
    if path.exists():
        payload = _read_object(path)
        rows = payload.get("queries") or []
        if isinstance(rows, list):
            queries.extend(str(row).strip() for row in rows if str(row).strip())
    for market_rows in MARKET_QUERIES.values():
        queries.extend(item.query for item in market_rows)
    return queries


def _append_history(path: Path, report: Mapping[str, Any], *, limit: int = 100) -> None:
    if path.exists():
        payload = _read_object(path)
        runs = payload.get("runs") or []
        if not isinstance(runs, list):
            runs = []
    else:
        runs = []
    entry = {
        "generated_at": report.get("generated_at"),
        "known_missed_opportunity_count": report.get("known_missed_opportunity_count", 0),
        "candidate_count": report.get("candidate_count", 0),
        "evaluated_candidate_count": report.get("evaluated_candidate_count", 0),
        "learning_search_requests": report.get("learning_search_requests", 0),
        "proven_term_count_this_run": report.get("proven_term_count_this_run", 0),
        "active_learned_term_count": report.get("active_learned_term_count", 0),
        "recovered_case_count": report.get("recovered_case_count", 0),
        "search_status": report.get("search_status"),
    }
    runs.append(entry)
    _write_object(
        path,
        {
            "schema_version": HISTORY_SCHEMA,
            "run_count": min(len(runs), limit),
            "runs": runs[-limit:],
        },
    )


def _market_anchor(market_code: str) -> str:
    return {
        "NO": "(klær OR klesbutikk OR tekstil OR arbeidsklær OR vernesko)",
        "SE": "(kläder OR klädbutik OR textil OR arbetskläder)",
        "DE": "(Bekleidung OR Modegeschäft OR Textilien OR Arbeitskleidung)",
    }.get(market_code.upper(), "(clothing OR textile OR inventory)")


def _build_search(api_key: str, *, results_per_candidate: int):
    providers: dict[str, BraveSearchProvider] = {}

    def search(term: str, market_code: str):
        market = market_code.upper()
        provider = providers.get(market)
        if provider is None:
            provider = BraveSearchProvider(
                api_key,
                country=market,
                freshness=None,
                extra_snippets=True,
            )
            providers[market] = provider
        safe_term = term.replace('"', "").strip()
        query = f'"{safe_term}" {_market_anchor(market)}'
        hits = provider.search(query, count=results_per_candidate)
        return [
            {
                "url": hit.url,
                "title": hit.title,
                "description": hit.description,
                "provider": hit.provider,
                "learning_query": query,
            }
            for hit in hits
        ]

    return search


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--inbox",
        default="config/learning/missed_opportunity_inbox.json",
    )
    parser.add_argument("--learning-dir", required=True)
    parser.add_argument(
        "--active-query-config",
        default="config/brave_search_queries.json",
    )
    parser.add_argument("--report", required=True)
    parser.add_argument("--max-candidates", type=int, default=2)
    parser.add_argument("--results-per-candidate", type=int, default=5)
    parser.add_argument("--min-precision", type=float, default=0.20)
    parser.add_argument("--max-active-terms-per-market", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.results_per_candidate <= 10:
        raise ValueError("results-per-candidate must be between 1 and 10")

    learning_dir = Path(args.learning_dir)
    memory_path = learning_dir / "missed-opportunities.json"
    overlay_path = learning_dir / "active-keyword-overlay.json"
    history_path = learning_dir / "keyword-learning-history.json"
    report_path = Path(args.report)

    existing_cases = load_missed_opportunity_memory(memory_path)
    inbox_cases = _load_inbox(Path(args.inbox))
    active_queries = _load_active_queries(Path(args.active_query_config))
    existing_overlay = (
        load_learned_query_overlay(overlay_path)
        if overlay_path.exists()
        else build_learned_query_overlay([])
    )

    api_key = str(
        os.environ.get("BRAVE_SEARCH_API_KEY")
        or os.environ.get("BRAVE_API_KEY")
        or ""
    ).strip()
    cost_block = manual_paid_brave_block_reason(os.environ)
    if cost_block:
        search_enabled = False
        skip_reason = "SKIPPED_COST_GUARD"
    elif not api_key:
        search_enabled = False
        skip_reason = "SKIPPED_NO_API_KEY"
    else:
        search_enabled = True
        skip_reason = None

    search = (
        _build_search(api_key, results_per_candidate=args.results_per_candidate)
        if search_enabled
        else (lambda term, market: [])
    )
    outcome = run_daily_learning_cycle(
        existing_cases=existing_cases,
        inbox_cases=inbox_cases,
        active_queries=active_queries,
        search=search,
        existing_overlay=existing_overlay,
        policy=DailyLearningPolicy(
            max_candidates_per_run=args.max_candidates,
            min_recovered_cases=1,
            min_precision=args.min_precision,
            max_terms_per_market=args.max_active_terms_per_market,
        ),
        search_enabled=search_enabled,
        search_skip_reason=skip_reason,
    )

    generated_at = datetime.now(timezone.utc).isoformat()
    report = dict(outcome.report)
    report.update(
        {
            "generated_at": generated_at,
            "inbox_path": str(args.inbox),
            "memory_path": memory_path.as_posix(),
            "overlay_path": overlay_path.as_posix(),
            "history_path": history_path.as_posix(),
            "results_per_candidate": args.results_per_candidate,
            "max_possible_learning_search_requests": args.max_candidates,
            "cost_guard_reason": cost_block,
        }
    )

    save_missed_opportunity_memory(memory_path, outcome.cases)
    save_learned_query_overlay(overlay_path, outcome.overlay)
    _append_history(history_path, report)
    _write_object(report_path, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
