"""SQLite-backed snapshots for ODS agent state files.

The existing ODS components use JSON/JSONL paths. This adapter keeps those components
unchanged while making their state portable across ephemeral runners: materialize files
before a run, then capture them back into one SQLite database afterwards.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Iterable


@dataclass(frozen=True)
class StateFile:
    name: str
    path: Path


class SQLiteStateStore:
    """Persist named UTF-8 state files in a transactional SQLite database."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS state_snapshots (
                    name TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def materialize(self, files: Iterable[StateFile]) -> int:
        """Restore known snapshots to working files and return the restored count."""
        restored = 0
        with self._connect() as connection:
            for state_file in files:
                row = connection.execute(
                    "SELECT content FROM state_snapshots WHERE name = ?",
                    (state_file.name,),
                ).fetchone()
                if row is None:
                    continue
                state_file.path.parent.mkdir(parents=True, exist_ok=True)
                state_file.path.write_text(str(row[0]), encoding="utf-8")
                restored += 1
        return restored

    def capture(self, files: Iterable[StateFile]) -> int:
        """Atomically save existing working files and return the captured count."""
        now = datetime.now(timezone.utc).isoformat()
        captured = 0
        with self._connect() as connection:
            for state_file in files:
                if not state_file.path.exists():
                    continue
                content = state_file.path.read_text(encoding="utf-8")
                connection.execute(
                    """
                    INSERT INTO state_snapshots(name, content, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        content = excluded.content,
                        updated_at = excluded.updated_at
                    """,
                    (state_file.name, content, now),
                )
                captured += 1
        return captured

    def snapshot_names(self) -> tuple[str, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT name FROM state_snapshots ORDER BY name"
            ).fetchall()
        return tuple(str(row[0]) for row in rows)
