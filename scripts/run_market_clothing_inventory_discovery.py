#!/usr/bin/env python3
"""Run Clothing Inventory discovery for one explicitly selected market."""
from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)


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
    runner = select_market_runner(selected.market)
    persistence = _persistence_output_args(remaining)
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
