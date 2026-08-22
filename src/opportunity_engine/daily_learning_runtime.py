"""Filesystem/runtime adapter for the bounded daily learning operator."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from opportunity_engine.cost_guard import manual_paid_brave_block_reason
from opportunity_engine.daily_learning_operator import (
    DailyLearningPolicy,
    run_daily_learning_cycle,
)
from opportunity_engine.discovery.brave_market_signal_radar import MARKET_QUERIES
from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.learning_promotion_gate import load_query_promotion_decisions
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
from opportunity_engine.safe_learning_proof import build_query_gap_safe_learning_proof

HISTORY_SCHEMA = "keyword-learning-history-1.1"
INBOX_SCHEMA = "missed-opportunity-inbox-1.0"
RuntimeSearch = Callable[[str, str], Sequence[Mapping[str, Any]]]


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


def load_missed_opportunity_inbox(path: str | Path) -> list[MissedOpportunityCase]:
    target = Path(path)
    if not target.exists():
        return []
    payload = _read_object(target)
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


def load_active_learning_queries(path: str | Path) -> list[str]:
    target = Path(path)
    queries: list[str] = []
    if target.exists():
        payload = _read_object(target)
        rows = payload.get("queries") or []
        if isinstance(rows, list):
            queries.extend(str(row).strip() for row in rows if str(row).strip())
    for market_rows in MARKET_QUERIES.values():
        queries.extend(item.query for item in market_rows)
    return queries


def append_learning_history(
    path: str | Path,
    report: Mapping[str, Any],
    *,
    limit: int = 100,
) -> None:
    target = Path(path)
    if target.exists():
        payload = _read_object(target)
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
        "shadow_proven_term_count": report.get("shadow_proven_term_count", 0),
        "active_learned_term_count": report.get("active_learned_term_count", 0),
        "promoted_term_count": report.get("promoted_term_count", 0),
        "recovered_case_count": report.get("recovered_case_count", 0),
        "search_status": report.get("search_status"),
        "promotion_gate_enforced": report.get("promotion_gate_enforced", False),
        "safe_learning_proof_status": report.get("safe_learning_proof_status"),
    }
    runs.append(entry)
    _write_object(
        target,
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


def build_learning_search(
    api_key: str,
    *,
    results_per_candidate: int,
) -> RuntimeSearch:
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


def run_daily_learning_runtime(
    *,
    learning_dir: str | Path,
    inbox_path: str | Path = "config/learning/missed_opportunity_inbox.json",
    active_query_config: str | Path = "config/brave_search_queries.json",
    promotion_config_path: str | Path = "config/learning/query_promotions.json",
    report_path: str | Path | None = None,
    runtime_overlay_path: str | Path | None = None,
    environment: Mapping[str, str] | None = None,
    policy: DailyLearningPolicy | None = None,
    results_per_candidate: int = 5,
    search_override: RuntimeSearch | None = None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Load durable state, run one bounded cycle, and persist the next state.

    Proven learning is stored in ``shadow-keyword-overlay.json``. Only exact
    terms explicitly PROMOTED by ``promotion_config_path`` are written to the
    production ``active-keyword-overlay.json`` and optional runtime copy.
    A read-only ``safe-learning-proof.json`` is also written so operators can
    see whether a real QUERY_GAP miss was recovered in shadow before promotion.
    """
    if not 1 <= results_per_candidate <= 10:
        raise ValueError("results_per_candidate must be between 1 and 10")
    env = environment if environment is not None else os.environ
    active_policy = policy or DailyLearningPolicy()
    root = Path(learning_dir)
    memory_path = root / "missed-opportunities.json"
    active_overlay_path = root / "active-keyword-overlay.json"
    shadow_overlay_path = root / "shadow-keyword-overlay.json"
    proof_path = root / "safe-learning-proof.json"
    history_path = root / "keyword-learning-history.json"

    existing_cases = load_missed_opportunity_memory(memory_path)
    inbox_cases = load_missed_opportunity_inbox(inbox_path)
    active_queries = load_active_learning_queries(active_query_config)
    existing_active_overlay = (
        load_learned_query_overlay(active_overlay_path)
        if active_overlay_path.exists()
        else build_learned_query_overlay([])
    )
    existing_shadow_overlay = (
        load_learned_query_overlay(shadow_overlay_path)
        if shadow_overlay_path.exists()
        else build_learned_query_overlay([])
    )
    promotion_decisions = load_query_promotion_decisions(promotion_config_path)

    api_key = str(
        env.get("BRAVE_SEARCH_API_KEY") or env.get("BRAVE_API_KEY") or ""
    ).strip()
    cost_block = manual_paid_brave_block_reason(env)
    if search_override is not None:
        search_enabled = True
        skip_reason = None
        search = search_override
    elif cost_block:
        search_enabled = False
        skip_reason = "SKIPPED_COST_GUARD"
        search = lambda term, market: []
    elif not api_key:
        search_enabled = False
        skip_reason = "SKIPPED_NO_API_KEY"
        search = lambda term, market: []
    else:
        search_enabled = True
        skip_reason = None
        search = build_learning_search(
            api_key,
            results_per_candidate=results_per_candidate,
        )

    outcome = run_daily_learning_cycle(
        existing_cases=existing_cases,
        inbox_cases=inbox_cases,
        active_queries=active_queries,
        search=search,
        existing_overlay=existing_active_overlay,
        existing_shadow_overlay=existing_shadow_overlay,
        promotion_decisions=promotion_decisions,
        policy=active_policy,
        search_enabled=search_enabled,
        search_skip_reason=skip_reason,
    )

    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    generated_at = now.astimezone(timezone.utc).isoformat()

    proof = build_query_gap_safe_learning_proof(
        outcome.cases,
        shadow_overlay=outcome.shadow_overlay,
        active_overlay=outcome.overlay,
        min_precision=active_policy.min_precision,
    )
    proof["generated_at"] = generated_at
    _write_object(proof_path, proof)

    report = dict(outcome.report)
    report.update(
        {
            "generated_at": generated_at,
            "inbox_path": Path(inbox_path).as_posix(),
            "memory_path": memory_path.as_posix(),
            "overlay_path": active_overlay_path.as_posix(),
            "shadow_overlay_path": shadow_overlay_path.as_posix(),
            "promotion_config_path": Path(promotion_config_path).as_posix(),
            "safe_learning_proof_path": proof_path.as_posix(),
            "safe_learning_proof_status": proof.get("status"),
            "safe_learning_shadow_recovered_case_count": proof.get(
                "shadow_recovered_case_count", 0
            ),
            "safe_learning_promotion_eligible_count": proof.get(
                "promotion_eligible_count", 0
            ),
            "history_path": history_path.as_posix(),
            "results_per_candidate": results_per_candidate,
            "max_possible_learning_search_requests": active_policy.max_candidates_per_run,
            "cost_guard_reason": cost_block,
        }
    )

    save_missed_opportunity_memory(memory_path, outcome.cases)
    save_learned_query_overlay(shadow_overlay_path, outcome.shadow_overlay)
    save_learned_query_overlay(active_overlay_path, outcome.overlay)
    append_learning_history(history_path, report)
    if runtime_overlay_path is not None:
        save_learned_query_overlay(runtime_overlay_path, outcome.overlay)
        report["runtime_overlay_path"] = Path(runtime_overlay_path).as_posix()
    if report_path is not None:
        _write_object(Path(report_path), report)
    return report
