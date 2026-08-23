#!/usr/bin/env python3
"""Persist review-only Search Success route learning across daily checkpoints.

This runner performs one bounded Exa exact-lot shadow observation for France,
verifies public pages, resolves bounded same-origin commercial navigation, and
updates durable Search Success memory. The memory is evidence only: it can mark
a route CANDIDATE or REPLICATED_FOR_REVIEW, but it cannot activate a provider,
promote a source, mutate production queries, or perform commercial actions.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.discovery.exact_lot_multihop_resolution import (
    resolve_exact_lot_multihop,
)
from opportunity_engine.discovery.provider_unique_page_verification import (
    verify_provider_unique_pages,
)
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY
from opportunity_engine.provider_route_success_learning import (
    build_provider_route_success_observation,
)
from opportunity_engine.search_success_learning import update_search_success_memory
from scripts.run_exa_brave_shadow_benchmark import run_benchmark


MEMORY_FILENAME = "search-success-memory.json"
DEFAULT_BOOTSTRAP_MEMORY = Path("config/learning/search-success-bootstrap-v1.json")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text.rstrip() + "\n", encoding="utf-8")
    temporary.replace(path)


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _load_existing_memory(
    memory_path: Path,
    *,
    bootstrap_memory_path: Path | None,
) -> tuple[dict[str, Any], str]:
    if memory_path.exists():
        return _load_json_object(memory_path), "RESTORED_DAILY_MEMORY"
    if bootstrap_memory_path is not None and bootstrap_memory_path.exists():
        return _load_json_object(bootstrap_memory_path), "VERIFIED_BOOTSTRAP_MEMORY"
    return {}, "EMPTY_FIRST_RUN_MEMORY"


def _assert_review_only_safety(*payloads: Mapping[str, Any]) -> None:
    for payload in payloads:
        if payload.get("automatic_provider_activation") not in {None, False}:
            raise ValueError("Search Success learning may not activate a provider")
        if payload.get("automatic_source_promotion") not in {None, False}:
            raise ValueError("Search Success learning may not promote a source")
        if payload.get("production_query_mutation") not in {None, False}:
            raise ValueError("Search Success learning may not mutate production queries")
        if payload.get("production_mutation") not in {None, False}:
            raise ValueError("Search Success learning may not mutate production")
        for field in (
            "automatic_contact",
            "automatic_bid",
            "automatic_reservation",
            "automatic_purchase",
            "automatic_payment",
        ):
            if payload.get(field) not in {None, False}:
                raise ValueError(f"Search Success learning must keep {field}=False")


def _build_review(
    *,
    run_id: str,
    memory_source: str,
    observation: Mapping[str, Any],
    memory: Mapping[str, Any],
) -> dict[str, Any]:
    route_learning = [
        dict(row)
        for row in memory.get("route_learning") or []
        if isinstance(row, Mapping)
    ]
    replicated = [
        row for row in route_learning if row.get("status") == "REPLICATED_FOR_REVIEW"
    ]
    candidates = [row for row in route_learning if row.get("status") == "CANDIDATE"]

    if replicated:
        review_status = "REPLICATED_FOR_REVIEW"
    elif candidates:
        review_status = "CANDIDATE"
    else:
        review_status = "NO_VERIFIED_ROUTE"

    return {
        "schema_version": "daily-search-success-review-1.0",
        "status": "SUCCESS",
        "run_id": str(run_id),
        "project_domain": CLOTHING_INVENTORY,
        "shadow_only": True,
        "memory_source": memory_source,
        "memory_run_count": int(memory.get("run_count") or 0),
        "current_run_successful_route_count": len(
            observation.get("successful_routes") or []
        ),
        "replicated_route_count": len(replicated),
        "candidate_route_count": len(candidates),
        "review_status": review_status,
        "routes_for_review": replicated,
        "candidate_routes": candidates,
        "provider_learning": dict(memory.get("provider_learning") or {}),
        "provider_comparison_status": observation.get(
            "provider_preference_status"
        ),
        "interpretation_guard": (
            "Search Success memory is review-only. REPLICATED_FOR_REVIEW may guide "
            "future shadow search review but cannot activate providers, promote "
            "sources, mutate production queries, contact sellers, bid, reserve, "
            "purchase, or pay."
        ),
        "automatic_provider_activation": False,
        "automatic_source_promotion": False,
        "production_query_mutation": False,
        "production_mutation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _render_review(review: Mapping[str, Any]) -> str:
    lines = [
        "Search Success Learning:",
        f"- status: {review.get('review_status')}",
        f"- memory runs: {review.get('memory_run_count')}",
        f"- current successful routes: {review.get('current_run_successful_route_count')}",
        f"- replicated routes for review: {review.get('replicated_route_count')}",
        f"- memory source: {review.get('memory_source')}",
    ]
    routes = review.get("routes_for_review") or []
    for row in routes[:5]:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            "- REVIEW: "
            f"{row.get('provider')} {row.get('market_code')} "
            f"{row.get('pathway')} {row.get('parent_domain') or row.get('result_domain')} "
            f"runs={row.get('independent_run_count')} status={row.get('status')}"
        )
    lines.append("- automatic production/provider/commercial actions: disabled")
    return "\n".join(lines)


def run_daily_search_success_learning(
    *,
    exa_api_key: str,
    input_root: str | Path,
    output_dir: str | Path,
    run_id: str,
    bootstrap_memory_path: str | Path | None = None,
    results_per_query: int = 5,
) -> dict[str, Any]:
    key = str(exa_api_key or "").strip()
    if not key:
        raise ValueError("EXA_API_KEY is required for daily Search Success shadow learning")
    if not str(run_id or "").strip():
        raise ValueError("run_id is required")

    input_root_path = Path(input_root)
    output = Path(output_dir)
    memory_path = input_root_path / "learning" / MEMORY_FILENAME
    bootstrap = Path(bootstrap_memory_path) if bootstrap_memory_path else None

    benchmark = run_benchmark(
        exa_api_key=key,
        brave_api_key=None,
        markets=["FR"],
        results_per_query=results_per_query,
        provider_mode="exa",
        query_mode="exact_lot",
    )
    if benchmark.get("project_domain") != CLOTHING_INVENTORY:
        raise ValueError("daily Search Success benchmark escaped CLOTHING_INVENTORY")

    verification = verify_provider_unique_pages(
        benchmark,
        provider="exa",
        max_page_fetches=5,
    )
    multihop = resolve_exact_lot_multihop(
        verification,
        max_root_parents=3,
        max_navigation_depth=3,
        max_links_per_page=12,
        max_navigation_page_fetches=18,
    )
    observation = build_provider_route_success_observation(
        run_id=str(run_id),
        provider="exa",
        benchmark=benchmark,
        provider_verification=verification,
        multihop_resolution=multihop,
    )

    existing_memory, memory_source = _load_existing_memory(
        memory_path,
        bootstrap_memory_path=bootstrap,
    )
    memory = update_search_success_memory(
        existing_memory,
        observation,
        min_independent_runs=2,
    )

    _assert_review_only_safety(benchmark, multihop, observation, memory)
    review = _build_review(
        run_id=str(run_id),
        memory_source=memory_source,
        observation=observation,
        memory=memory,
    )
    _assert_review_only_safety(review)

    # Write the durable memory only after the full bounded observation succeeds.
    # If the shadow search raises, the restored prior memory remains untouched and
    # is still uploaded with the checkpoint artifact for the next daily run.
    _write_json(memory_path, memory)
    _write_json(output / "search-success-benchmark.json", benchmark)
    _write_json(output / "search-success-verification.json", verification)
    _write_json(output / "search-success-multihop.json", multihop)
    _write_json(output / "search-success-observation.json", observation)
    _write_json(output / "search-success-review.json", review)
    _write_text(output / "search-success-review.txt", _render_review(review))

    return review


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", ""))
    parser.add_argument(
        "--bootstrap-memory",
        default=DEFAULT_BOOTSTRAP_MEMORY.as_posix(),
    )
    parser.add_argument("--results-per-query", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    review = run_daily_search_success_learning(
        exa_api_key=os.environ.get("EXA_API_KEY", ""),
        input_root=args.input_root,
        output_dir=args.output_dir,
        run_id=args.run_id,
        bootstrap_memory_path=args.bootstrap_memory,
        results_per_query=args.results_per_query,
    )
    print(f"status={review['status']}")
    print(f"review_status={review['review_status']}")
    print(f"memory_source={review['memory_source']}")
    print(f"memory_run_count={review['memory_run_count']}")
    print(f"replicated_route_count={review['replicated_route_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
