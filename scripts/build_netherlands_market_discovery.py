#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from opportunity_engine.discovery.netherlands_entity_identity_resolution import (
    resolve_netherlands_entity_identities,
)
from opportunity_engine.discovery.netherlands_market_discovery import (
    collect_netherlands_market_signals,
)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run bounded Netherlands clothing/bridal liquidation discovery."
    )
    parser.add_argument(
        "--output",
        default="artifacts/netherlands-market-discovery.json",
        help="Discovery JSON output path",
    )
    parser.add_argument(
        "--identity-output",
        default=None,
        help="Optional entity-identity resolution JSON output path",
    )
    parser.add_argument("--query-budget", type=int, default=None)
    parser.add_argument("--results-per-query", type=int, default=10)
    args = parser.parse_args()

    kwargs = {
        "environment": os.environ,
        "results_per_query": args.results_per_query,
    }
    if args.query_budget is not None:
        kwargs["query_budget"] = args.query_budget

    report = collect_netherlands_market_signals(**kwargs)
    output = Path(args.output)
    _write(output, report)

    identity_output = (
        Path(args.identity_output)
        if args.identity_output
        else output.with_name("netherlands-entity-identity-resolution.json")
    )
    identity = resolve_netherlands_entity_identities(
        [item for item in report.get("signals") or [] if isinstance(item, dict)],
        environment=os.environ,
    )
    identity["discovery_status"] = report.get("status")
    identity["discovery_accepted_signal_count"] = report.get("accepted_signal_count")
    _write(identity_output, identity)

    print(
        json.dumps(
            {
                "status": report.get("status"),
                "queries_attempted": report.get("queries_attempted"),
                "queries_succeeded": report.get("queries_succeeded"),
                "accepted_signal_count": report.get("accepted_signal_count"),
                "independent_domain_count": report.get("independent_domain_count"),
                "identity_resolution_status": identity.get("status"),
                "resolved_identity_count": identity.get("resolved_identity_count"),
                "officially_confirmed_identity_count": identity.get(
                    "officially_confirmed_identity_count"
                ),
                "discovery_output": output.as_posix(),
                "identity_output": identity_output.as_posix(),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    blocked = {"BLOCKED_RETRIEVAL"}
    return 2 if report.get("status") in blocked or identity.get("status") in blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
