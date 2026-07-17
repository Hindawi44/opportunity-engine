"""Run one scheduled ODS research cycle with SQLite-backed state."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

from opportunity_engine.ods.autonomous_agent import AutonomousResearchAgent
from opportunity_engine.ods.brreg_collector import BrregSearchSlice
from opportunity_engine.ods.notifications import EmailNotifier
from opportunity_engine.ods.sqlite_state import SQLiteStateStore, StateFile


def _parse_subjects(raw: str) -> tuple[str, ...]:
    subjects = tuple(value.strip() for value in raw.split(",") if value.strip())
    if not subjects:
        raise ValueError("at least one search subject is required")
    return subjects


def _append_delivery_log(path: Path, run_id: str, delivery) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "run_id": run_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        **asdict(delivery),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


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
        delivery_log = workdir / "deliveries.jsonl"
        files = (
            StateFile("feed.json", workdir / "feed.json"),
            StateFile("memory.json", workdir / "memory.json"),
            StateFile("alerts.json", workdir / "alerts.json"),
            StateFile("runs.jsonl", workdir / "runs.jsonl"),
            StateFile("deliveries.jsonl", delivery_log),
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
        notifier = EmailNotifier(
            smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
            smtp_port=os.getenv("SMTP_PORT", "465"),
            username=os.getenv("SMTP_USERNAME"),
            password=os.getenv("SMTP_PASSWORD"),
            recipient=os.getenv("EMAIL_TO"),
            sender=os.getenv("EMAIL_FROM") or os.getenv("SMTP_USERNAME"),
        )
        delivery = notifier.send(result.alerts)
        _append_delivery_log(delivery_log, result.run_id, delivery)
        captured = store.capture(files)

    summary = {
        "run_id": result.run_id,
        "restored_snapshots": restored,
        "captured_snapshots": captured,
        "opportunities": len(result.decisions),
        "alerts": len(result.alerts),
        "suppressed": result.suppressed_count,
        "delivery": asdict(delivery),
        "database": str(database_path),
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
