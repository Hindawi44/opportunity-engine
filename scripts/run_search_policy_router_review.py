#!/usr/bin/env python3
"""Write the review-only Search Policy Router V1 daily artifact.

This runner reads existing Unified Memory V2.  It performs no network search,
does not change query packs or request slots, and cannot mutate production.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from opportunity_engine.discovery.commercial_anchor_query_expansion import (
    MAX_COMMERCIAL_ANCHOR_QUERIES_PER_MARKET,
    build_commercial_anchor_queries,
)
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY
from opportunity_engine.search_policy_router_v1 import (
    SUPPORTED_MARKETS,
    build_search_policy_router_v1,
)
from scripts.run_exa_exact_lot_checkpoint import (
    MARKET_EXACT_LOT_QUERY_PACKS,
    MARKET_ZERO_YIELD_RECALL_QUERIES,
)


JSON_FILENAME = "search-policy-router-v1-review.json"
TEXT_FILENAME = "search-policy-router-v1-review.txt"


def _conditional_queries() -> dict[str, tuple[str, ...]]:
    output: dict[str, tuple[str, ...]] = {}
    for market in SUPPORTED_MARKETS:
        recall = tuple(MARKET_ZERO_YIELD_RECALL_QUERIES.get(market, ()))
        anchors = tuple(
            str(row["query"])
            for row in build_commercial_anchor_queries(
                market=market,
                project_domain=CLOTHING_INVENTORY,
                max_queries=MAX_COMMERCIAL_ANCHOR_QUERIES_PER_MARKET,
            )
        )
        output[market] = recall + anchors
    return output


def _display(value: object) -> str:
    return "Unknown" if value is None else str(value)


def _write_text(path: Path, router: Mapping[str, Any]) -> None:
    lines = [
        "SEARCH POLICY ROUTER V1 — REVIEW OUTPUT",
        "",
        "Mode: REVIEW_ONLY",
        "Provider scope: EXA_EXACT_LOT_ONLY",
        f"Cost: {_display(router.get('cost'))}",
        "Production mutation: disabled",
        "",
        "Market | Query Family | Provider/Path | Requests | Days | Fresh Candidates | Verified Candidates | Raw Exact-Lots | Unique Exact-Lots | Unique Fresh Yield/Request | Cost | Freshness | Decision | Reason",
    ]
    for row in router.get("recommendations") or []:
        lines.append(
            " | ".join(
                [
                    str(row["market_code"]),
                    str(row["query_family"]),
                    str(row["provider_or_direct_path"]),
                    str(row["search_request_count"]),
                    str(row["independent_checkpoint_day_count"]),
                    _display(row["fresh_candidate_count"]),
                    _display(row["verified_candidate_count"]),
                    str(row["fresh_strict_exact_lot_count"]),
                    str(row["unique_fresh_strict_exact_lot_count"]),
                    f"{row['unique_fresh_yield_per_request']:.6f}",
                    _display(row["cost"]),
                    _display(row["freshness"]),
                    str(row["decision"]),
                    str(row["reason"]),
                ]
            )
        )
        lines.append(f"  Query: {row['query']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_router_review(memory: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:
    router = build_search_policy_router_v1(
        memory,
        primary_queries=MARKET_EXACT_LOT_QUERY_PACKS,
        conditional_queries=_conditional_queries(),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / JSON_FILENAME
    text_path = output_dir / TEXT_FILENAME
    json_path.write_text(
        json.dumps(router, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_text(text_path, router)
    return {"json": json_path, "text": text_path}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--memory",
        default="artifacts/multi-market-inputs/learning/unified-memory-v2.json",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/multi-market-daily-operator-checkpoint",
    )
    args = parser.parse_args()
    memory = json.loads(Path(args.memory).read_text(encoding="utf-8"))
    paths = write_router_review(memory, Path(args.output_dir))
    print(f"search_policy_router_review_json: {paths['json']}")
    print(f"search_policy_router_review_text: {paths['text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
