#!/usr/bin/env python3
"""Record one explicit human review outcome in the matching source SQLite DB."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

from opportunity_engine.persistence.database import (
    create_database_engine,
    create_session_factory,
    session_scope,
    upgrade_database,
)
from opportunity_engine.persistence.human_review import (
    HumanReviewOutcome,
    apply_human_review_outcome,
)
from opportunity_engine.persistence.unified_repository import UnifiedOpportunityRepository


def _timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("--reviewed-at must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _contains_opportunity(path: Path, opportunity_id: str) -> bool:
    try:
        connection = sqlite3.connect(path)
        try:
            table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='unified_opportunities'"
            ).fetchone()
            if table is None:
                return False
            row = connection.execute(
                "SELECT 1 FROM unified_opportunities WHERE opportunity_id = ?",
                (opportunity_id,),
            ).fetchone()
            return row is not None
        finally:
            connection.close()
    except sqlite3.Error:
        return False


def _find_database(input_root: Path, opportunity_id: str) -> Path:
    matches = [
        path
        for path in sorted(input_root.glob("*/opportunity_engine.db"))
        if _contains_opportunity(path, opportunity_id)
    ]
    if not matches:
        raise ValueError(f"opportunity_id was not found in source SQLite: {opportunity_id}")
    if len(matches) != 1:
        raise ValueError(
            f"opportunity_id exists in multiple source databases: {opportunity_id}"
        )
    return matches[0]


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _update_persistence_summary(database_path: Path, transition_created: bool) -> None:
    path = database_path.parent / "unified-persistence-summary.json"
    if not path.exists():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("status") != "SUCCESS":
        return
    current = payload.get("lifecycle_events_created", 0)
    if isinstance(current, bool) or not isinstance(current, int):
        current = 0
    payload["lifecycle_events_created"] = current + int(transition_created)
    payload["human_review_outcome_applied"] = True
    _write_json(path, payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    location = parser.add_mutually_exclusive_group(required=True)
    location.add_argument("--database-url")
    location.add_argument("--input-root")
    parser.add_argument("--opportunity-id", required=True)
    parser.add_argument(
        "--outcome",
        required=True,
        choices=[item.value for item in HumanReviewOutcome],
    )
    parser.add_argument("--reviewer")
    parser.add_argument("--note")
    parser.add_argument("--reviewed-at")
    parser.add_argument("--request-id")
    parser.add_argument("--source-ref")
    parser.add_argument("--output")
    parser.add_argument("--config", default="alembic.ini")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    database_path: Path | None = None
    if args.input_root:
        database_path = _find_database(Path(args.input_root), args.opportunity_id)
        database_url = f"sqlite:///{database_path}"
    else:
        database_url = args.database_url
        prefix = "sqlite:///"
        if str(database_url).startswith(prefix):
            database_path = Path(str(database_url)[len(prefix) :])

    upgrade_database(database_url, config_path=args.config)
    engine = create_database_engine(database_url)
    try:
        factory = create_session_factory(engine)
        with session_scope(factory) as session:
            result = apply_human_review_outcome(
                UnifiedOpportunityRepository(session),
                opportunity_id=args.opportunity_id,
                outcome=args.outcome,
                reviewed_at=_timestamp(args.reviewed_at),
                reviewer=args.reviewer,
                note=args.note,
                source_ref=args.source_ref,
                request_id=args.request_id,
            )
    finally:
        engine.dispose()

    result["database_path"] = str(database_path) if database_path else None
    if database_path is not None:
        _update_persistence_summary(
            database_path,
            bool(result["lifecycle_transition_created"]),
        )
    if args.output:
        _write_json(Path(args.output), result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
