from __future__ import annotations

from io import BytesIO
import json
from zipfile import ZipFile

import pytest

from opportunity_engine.discovery.checkpoint_state_restore import (
    PreviousCheckpointRestoreError,
    extract_previous_follow_up_seed,
)


def _archive(member: str, payload: bytes) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(member, payload)
    return buffer.getvalue()


def test_restore_previous_cross_source_report_as_bounded_follow_up_seed(tmp_path) -> None:
    member = (
        "multi-market-daily-operator-checkpoint/cross-source-scent-v2/"
        "cross-source-scent-expansion-v2.json"
    )
    payload = {
        "status": "SUCCESS",
        "top_scents": [
            {"market_code": "DE", "label": "Adenauer & Co"},
            {"market_code": "SE", "label": "Stores For You AB"},
            {"market_code": "DE", "label": "Schümer Textil GmbH"},
        ],
        "signals": [{"signal_id": "example"}],
        "promotion_to_opportunity_allowed": False,
    }

    restored = extract_previous_follow_up_seed(
        _archive(member, json.dumps(payload).encode("utf-8")),
        tmp_path,
    )

    assert restored is not None
    target = tmp_path / "previous-cross-source-scent-v2.json"
    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8")) == payload
    assert restored["archive_member"] == member


def test_missing_seed_is_valid_and_does_not_restore_arbitrary_json(tmp_path) -> None:
    archive = _archive(
        "multi-market-daily-operator-checkpoint/unrelated.json",
        b'{"signals": [{"signal_id": "must-not-load"}]}',
    )

    restored = extract_previous_follow_up_seed(archive, tmp_path)

    assert restored is None
    assert not (tmp_path / "previous-cross-source-scent-v2.json").exists()


def test_invalid_allowlisted_seed_is_reported_as_integrity_error(tmp_path) -> None:
    member = (
        "multi-market-daily-operator-checkpoint/cross-source-scent-v2/"
        "cross-source-scent-expansion-v2.json"
    )

    with pytest.raises(PreviousCheckpointRestoreError, match="not valid JSON"):
        extract_previous_follow_up_seed(_archive(member, b"not-json"), tmp_path)
