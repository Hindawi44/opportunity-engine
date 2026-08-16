from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest

from opportunity_engine.discovery.italy_case_memory_restore import (
    ItalyMemoryRestoreError,
    extract_italy_memory_database,
)


def _archive(member: str, payload: bytes) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(member, payload)
    return buffer.getvalue()


def test_extracts_only_allowlisted_italy_sqlite(tmp_path: Path) -> None:
    sqlite_payload = b"SQLite format 3\x00" + b"test-memory"
    archive = _archive(
        "artifacts/italy-case-memory/it-market/opportunity_engine.db",
        sqlite_payload,
    )

    restored = extract_italy_memory_database(archive, tmp_path)

    assert restored is not None
    target = tmp_path / "it-market" / "opportunity_engine.db"
    assert target.read_bytes() == sqlite_payload
    assert restored["relative_path"] == target.as_posix()


def test_missing_database_is_valid_first_run(tmp_path: Path) -> None:
    archive = _archive("italy-case-memory/italy-case-memory-v1.json", b"{}")
    assert extract_italy_memory_database(archive, tmp_path) is None


def test_rejects_non_sqlite_payload(tmp_path: Path) -> None:
    archive = _archive("it-market/opportunity_engine.db", b"not-a-database")
    with pytest.raises(ItalyMemoryRestoreError, match="not SQLite"):
        extract_italy_memory_database(archive, tmp_path)
