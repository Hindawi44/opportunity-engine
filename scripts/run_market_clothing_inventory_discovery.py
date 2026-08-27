#!/usr/bin/env python3
"""Run Clothing Inventory discovery for one explicitly selected market."""
from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from opportunity_engine.cost_guard import (
    MANUAL_PAID_BRAVE_BLOCK_REASON,
    ensure_paid_brave_allowed,
)


def select_market_runner(market: str) -> Callable[[], int]:
    """Return the existing market runner and fail closed for unsupported codes."""
    normalized = market.strip().upper()
    if normalized == "NO":
        from scripts.run_clothing_inventory_discovery_search import main

        return main
    if normalized == "SE":
        from scripts.run_sweden_clothing_inventory_discovery_search import main

        return main
    if normalized == "DE":
        from scripts.run_germany_clothing_inventory_discovery_search import main

        return main
    raise ValueError(f"unsupported market code: {market}")


def _persistence_output_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--persist-unified", action="store_true")
    parser.add_argument(
        "--database-url",
        default=os.environ.get(
            "OPPORTUNITY_DATABASE_URL",
            "sqlite:///data/opportunity_engine.db",
        ),
    )
    parser.add_argument("--output-dir", default="artifacts/clothing-inventory-discovery")
    parsed, _ = parser.parse_known_args(list(argv))
    return parsed


def _paid_brave_scope_args(argv: Sequence[str]) -> argparse.Namespace:
    """Read only the source/budget fields needed by the fail-closed cost guard."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--source", default="")
    parser.add_argument("--query-budget", type=int, default=0)
    parsed, _ = parser.parse_known_args(list(argv))
    return parsed


def _write_zero_cost_blocked_discovery(
    *,
    market: str,
    source: str,
    query_budget: int,
    output_dir: str | Path,
) -> dict[str, Path]:
    """Write canonical empty discovery inputs without making any paid request."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    discovered_at = datetime.now(timezone.utc).isoformat()
    normalized_source = str(source or "open-web").strip().upper().replace("-", "_")
    report = {
        "status": "SUCCESS",
        "discovered_at": discovered_at,
        "domain": "CLOTHING_INVENTORY",
        "market_code": market.strip().upper(),
        "source_mode": normalized_source,
        "queries_submitted": 0,
        "query_budget": int(query_budget or 0),
        "top5_count": 0,
        "cost_guard_status": "SKIPPED_COST_GUARD",
        "cost_guard_reason": MANUAL_PAID_BRAVE_BLOCK_REASON,
        "paid_brave_requests": 0,
        "currency_conversion_performed": False,
        "tax_calculation_performed": False,
        "customs_calculation_performed": False,
        "logistics_calculation_performed": False,
    }
    payloads = {
        "search-run-report.json": report,
        "all-discovered-candidates.json": [],
        "discovery-top5.json": [],
    }
    paths: dict[str, Path] = {}
    for filename, payload in payloads.items():
        path = directory / filename
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        paths[filename] = path
    summary = directory / "operator-summary.txt"
    summary.write_text(
        "Status: VALID_ZERO_COST_GUARD\n"
        f"Market: {market.strip().upper()}\n"
        f"Source: {normalized_source}\n"
        "Paid Brave requests: 0\n"
        f"Reason: {MANUAL_PAID_BRAVE_BLOCK_REASON}\n",
        encoding="utf-8",
    )
    paths["operator-summary.txt"] = summary
    return paths


def _write_post_persistence_report(
    *,
    database_url: str,
    output_dir: str | Path,
) -> tuple[Path, Path]:
    from opportunity_engine.persistence.database import (
        create_database_engine,
        create_session_factory,
        session_scope,
    )
    from opportunity_engine.persistence.historical_market_evidence_report import (
        write_historical_market_evidence_report,
    )
    from opportunity_engine.persistence.unified_repository import (
        UnifiedOpportunityRepository,
    )

    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            _, report_path, summary_path = write_historical_market_evidence_report(
                UnifiedOpportunityRepository(session),
                output_dir,
            )
    finally:
        engine.dispose()
    return report_path, summary_path


def main() -> int:
    selector = argparse.ArgumentParser(add_help=False)
    selector.add_argument("--market", choices=("NO", "SE", "DE"), default="NO")
    selected, remaining = selector.parse_known_args()
    paid_scope = _paid_brave_scope_args(remaining)
    persistence = _persistence_output_args(remaining)

    # workflow_dispatch executions, including bot-triggered merge/live-proof runs,
    # are zero-cost by default. Scheduled production runs remain paid-capable.
    try:
        ensure_paid_brave_allowed(
            market=selected.market,
            source=paid_scope.source,
            query_budget=paid_scope.query_budget,
        )
    except RuntimeError as exc:
        if MANUAL_PAID_BRAVE_BLOCK_REASON not in str(exc):
            raise
        paths = _write_zero_cost_blocked_discovery(
            market=selected.market,
            source=paid_scope.source,
            query_budget=paid_scope.query_budget,
            output_dir=persistence.output_dir,
        )
        print("Status: VALID_ZERO_COST_GUARD")
        print(f"Market: {selected.market}")
        print(f"Source: {paid_scope.source or 'open-web'}")
        print("Queries: 0")
        print("Top opportunities: 0")
        print("Paid Brave requests: 0")
        for name, path in paths.items():
            print(f"{name}: {path}")
        return 0

    runner = select_market_runner(selected.market)
    sys.argv = [sys.argv[0], *remaining]
    exit_code = runner()
    if exit_code != 0 or not persistence.persist_unified:
        return exit_code

    try:
        report_path, summary_path = _write_post_persistence_report(
            database_url=persistence.database_url,
            output_dir=persistence.output_dir,
        )
    except Exception as exc:
        print(f"Historical market evidence report failed: {exc}", file=sys.stderr)
        return 3

    print(f"historical_market_evidence_report: {report_path}")
    print(f"historical_market_evidence_summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())