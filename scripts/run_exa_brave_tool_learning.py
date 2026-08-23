#!/usr/bin/env python3
"""Verify Exa and Brave symmetrically and build a read-only Tool Learning artifact."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_engine.discovery.provider_unique_page_verification import verify_provider_unique_pages
from opportunity_engine.discovery.search_tool_learning import build_search_tool_learning_scorecard


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("benchmark must be a JSON object")
    return payload


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def run_tool_learning(
    benchmark: dict,
    *,
    max_page_fetches_per_provider: int = 18,
    min_successful_pages_per_provider: int = 5,
) -> dict:
    exa = verify_provider_unique_pages(
        benchmark,
        provider="exa",
        max_page_fetches=max_page_fetches_per_provider,
    )
    brave = verify_provider_unique_pages(
        benchmark,
        provider="brave",
        max_page_fetches=max_page_fetches_per_provider,
    )
    scorecard = build_search_tool_learning_scorecard(
        exa,
        brave,
        min_successful_pages_per_provider=min_successful_pages_per_provider,
    )
    status = "SUCCESS" if exa.get("status") == "SUCCESS" and brave.get("status") == "SUCCESS" else "BLOCKED_INPUT"
    return {
        "schema_version": "exa-brave-tool-learning-proof-1.0",
        "status": status,
        "shadow_only": True,
        "exa_verification": exa,
        "brave_verification": brave,
        "tool_learning": scorecard,
        "automatic_provider_activation": False,
        "production_mutation": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-page-fetches-per-provider", type=int, default=18)
    parser.add_argument("--min-successful-pages-per-provider", type=int, default=5)
    args = parser.parse_args()

    payload = run_tool_learning(
        _load_json(Path(args.benchmark)),
        max_page_fetches_per_provider=args.max_page_fetches_per_provider,
        min_successful_pages_per_provider=args.min_successful_pages_per_provider,
    )
    _write_json(Path(args.output), payload)
    print(f"status={payload['status']}")
    print(f"decision={payload['tool_learning']['decision']}")
    print(f"exa_verified={payload['exa_verification'].get('page_fetches_succeeded', 0)}")
    print(f"brave_verified={payload['brave_verification'].get('page_fetches_succeeded', 0)}")
    return 0 if payload["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
