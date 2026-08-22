from __future__ import annotations

from io import BytesIO
import json
from zipfile import ZipFile

import pytest

from opportunity_engine.discovery.checkpoint_state_restore import (
    PreviousCheckpointRestoreError,
    extract_previous_learning_state,
)


def archive_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


def test_restores_only_allowlisted_learning_state_into_input_root(tmp_path) -> None:
    missed = {
        "schema_version": "missed-opportunity-learning-loop-1.0",
        "case_count": 1,
        "cases": [{"case_id": "MISS-1"}],
    }
    overlay = {
        "schema_version": "learned-query-overlay-1.0",
        "markets": {"NO": [{"term": "sluttlager"}]},
    }
    archive = archive_bytes(
        {
            "artifacts/multi-market-inputs/learning/missed-opportunities.json": json.dumps(missed).encode(),
            "artifacts/multi-market-inputs/learning/active-keyword-overlay.json": json.dumps(overlay).encode(),
            "artifacts/multi-market-inputs/learning/not-allowlisted.json": b'{"secret": true}',
        }
    )

    restored = extract_previous_learning_state(archive, tmp_path)

    assert {item["filename"] for item in restored} == {
        "missed-opportunities.json",
        "active-keyword-overlay.json",
    }
    target = tmp_path / "learning"
    assert json.loads((target / "missed-opportunities.json").read_text()) == missed
    assert json.loads((target / "active-keyword-overlay.json").read_text()) == overlay
    assert not (target / "not-allowlisted.json").exists()


def test_learning_restore_accepts_artifact_flattened_prefix(tmp_path) -> None:
    overlay = {"schema_version": "learned-query-overlay-1.0", "markets": {}}
    archive = archive_bytes(
        {
            "multi-market-inputs/learning/active-keyword-overlay.json": json.dumps(overlay).encode()
        }
    )

    restored = extract_previous_learning_state(archive, tmp_path)

    assert len(restored) == 1
    assert (tmp_path / "learning" / "active-keyword-overlay.json").exists()


def test_missing_learning_state_is_valid(tmp_path) -> None:
    archive = archive_bytes({"unrelated.json": b'{"value": 1}'})

    assert extract_previous_learning_state(archive, tmp_path) == []
    assert not (tmp_path / "learning").exists()


def test_invalid_allowlisted_learning_json_is_integrity_error(tmp_path) -> None:
    archive = archive_bytes(
        {"learning/missed-opportunities.json": b"not-json"}
    )

    with pytest.raises(PreviousCheckpointRestoreError, match="learning state is not valid JSON"):
        extract_previous_learning_state(archive, tmp_path)


def test_learning_state_must_be_json_object(tmp_path) -> None:
    archive = archive_bytes(
        {"learning/active-keyword-overlay.json": b"[]"}
    )

    with pytest.raises(PreviousCheckpointRestoreError, match="must be a JSON object"):
        extract_previous_learning_state(archive, tmp_path)
