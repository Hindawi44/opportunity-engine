#!/usr/bin/env python3
"""Persist the current operational opportunity and shipment tasks into SQLite."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from opportunity_engine.persistence import (
    DEFAULT_DATABASE_URL,
    OpportunityRepository,
    create_database_engine,
    create_session_factory,
    persist_operational_snapshots,
    session_scope,
    upgrade_database,
)


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _default_run_id(now: datetime) -> str:
    return f"operational-persistence-{now.strftime('%Y%m%dT%H%M%S%fZ')}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Persist operational opportunity state through OpportunityRepository"
    )
    parser.add_argument(
        "--decisions",
        type=Path,
        default=Path("data/decision_intelligence.json"),
    )
    parser.add_argument(
        "--shipment-evidence",
        type=Path,
        default=Path("data/shipment_evidence_queue_v1.json"),
    )
    parser.add_argument("--database-url", default=DEFAULT_DATABASE_URL)
    parser.add_argument("--alembic-config", type=Path, default=Path("alembic.ini"))
    parser.add_argument("--run-id")
    parser.add_argument("--market-code", default="NO")
    args = parser.parse_args()

    started_at = datetime.now(timezone.utc)
    run_id = args.run_id or _default_run_id(started_at)
    decisions = _load_json(args.decisions)
    shipment_queue = _load_json(args.shipment_evidence)

    upgrade_database(
        args.database_url,
        config_path=args.alembic_config,
    )
    engine = create_database_engine(args.database_url)
    try:
        factory = create_session_factory(engine)
        with session_scope(factory) as session:
            summary = persist_operational_snapshots(
                decisions,
                shipment_queue,
                OpportunityRepository(session),
                run_id=run_id,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                market_code=args.market_code,
                decision_source_ref=str(args.decisions),
                queue_source_ref=str(args.shipment_evidence),
            )
    finally:
        engine.dispose()

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
