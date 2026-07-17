"""Run one scheduled ODS research cycle with SQLite-backed state."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile

from opportunity_engine.ods.autonomous_agent import AutonomousResearchAgent
from opportunity_engine.ods.brreg_collector import BrregSearchSlice
from opportunity_engine.ods.sqlite_state import SQLiteStateStore, StateFile


def _parse_subjects(raw: str) -> tuple[str, ...]:
    subjects = tuple(value.strip() for value in raw.split(",") if value.strip())
    if not subjects:
        raise ValueError("at least one search subject is required")
    return subjects


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one persistent ODS research cycle")
    parser.add_argument(
        "--database",
        default=os.getenv("ODS_STATE_DB", "data/ods_state.sqlite3"),
        help="SQLite state database path",
    )
    parser.add_argument(
        "--subjects",
        default=os.getenv("ODS_SEARCH_SUBJECTS", "butikk,konkurs,avvikling,varelager"),
        help="Comma-separated bounded Brreg search subjects",
    )
    parser.add_argument(
        "--municipality",
        default=os.getenv("ODS_MUNICIPALITY") or None,
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=int(os.getenv("ODS_PAGE_SIZE", "50")),
    )
    args = parser.parse_args()

    subjects = _parse_subjects(args.subjects)
    database_path = Path(args.database)
    store = SQLiteStateStore(database_path)

    with tempfile.TemporaryDirectory(prefix="ods-agent-") as directory:
        workdir = Path(directory)
        files = (
            StateFile("feed.json", workdir / "feed.json"),
            StateFile("memory.json", workdir / "memory.json"),
            StateFile("alerts.json", workdir / "alerts.json"),
            StateFile("runs.jsonl", workdir / "runs.jsonl"),
        )
        restored = store.materialize(files)
        agent = AutonomousResearchAgent(
            feed_path=workdir / "feed.json",
            memory_path=workdir / "memory.json",
            alert_state_path=workdir / "alerts.json",
            run_log_path=workdir / "runs.jsonl",
        )
        slices = tuple(
            BrregSearchSlice(
                subject=subject,
                municipality=args.municipality,
                page_size=args.page_size,
            )
            for subject in subjects
        )
        result = agent.run(slices)
        captured = store.capture(files)

    summary = {
        "run_id": result.run_id,
        "restored_snapshots": restored,
        "captured_snapshots": captured,
        "opportunities": len(result.decisions),
        "alerts": len(result.alerts),
        "suppressed": result.suppressed_count,
        "database": str(database_path),
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
