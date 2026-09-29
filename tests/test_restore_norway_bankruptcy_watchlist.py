"""Norway watchlist restoration reuses the audited checkpoint mechanism."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import scripts.restore_norway_bankruptcy_watchlist as restore
from scripts.run_norway_bankruptcy_watchlist import prepare_watchlist

NOW = datetime(2026, 9, 26, 6, tzinfo=timezone.utc)


def _watchlist() -> dict:
    events = {
        "schema_version": "norway-insolvency-event-sample-1",
        "scope": "NO_ONLY_OFFICIAL_BANKRUPTCY_ALL_SECTORS",
        "events": [
            {
                "organisation_number": "123456789",
                "company_name": "Nord Industri AS",
                "official_url": "https://data.brreg.no/enhetsregisteret/api/enheter/123456789",
                "source_country": "NO",
                "event_kinds": ["konkurs"],
                "event_date": "2026-09-25",
                "location": "Namsos",
            }
        ],
    }
    watchlist, _, _ = prepare_watchlist(events, now=NOW)
    return watchlist


def test_restore_configuration_is_narrow_and_temporary() -> None:
    checkpoint = restore.checkpoint_state_restore
    original_artifact = checkpoint.ARTIFACT_NAME
    with restore.configured_watchlist_restore():
        assert checkpoint.ARTIFACT_NAME == restore.ARTIFACT_NAME
        assert checkpoint.DATABASE_RELATIVE_PATHS == ()
        assert checkpoint.LEARNING_STATE_FILENAMES == ()
        assert checkpoint.FOLLOW_UP_SEED_MEMBERS == restore.WATCHLIST_MEMBERS
        assert checkpoint.RESTORABLE_EVENTS == {"workflow_dispatch", "schedule", "push"}
    assert checkpoint.ARTIFACT_NAME == original_artifact


def test_valid_restored_watchlist_is_validated_before_publish(
    monkeypatch, tmp_path
) -> None:
    def fake_restore(**kwargs):
        staged = Path(kwargs["status_path"]).parent / restore.WATCHLIST_FILENAME
        staged.write_text(json.dumps(_watchlist()), encoding="utf-8")
        assert restore.checkpoint_state_restore.ARTIFACT_NAME == restore.ARTIFACT_NAME
        return {
            "status": "RESTORED",
            "previous_run_id": 200,
            "previous_run_event": "schedule",
            "previous_artifact_id": 20,
            "restored_follow_up_seed": {
                "archive_member": "bankruptcy-watchlist.json",
                "relative_path": staged.as_posix(),
            },
        }

    monkeypatch.setattr(
        restore.checkpoint_state_restore,
        "restore_previous_checkpoint_databases",
        fake_restore,
    )
    target = tmp_path / "watchlist.json"
    status = restore.restore_previous_watchlist(
        repository="example/repo",
        token="token",
        current_run_id=300,
        target=target,
        status_path=tmp_path / "restore-status.json",
    )

    assert status["status"] == "RESTORED"
    assert status["previous_run_id"] == 200
    assert status["restored_case_count"] == 1
    assert (
        json.loads(target.read_text(encoding="utf-8"))["cases"][0][
            "organisation_number"
        ]
        == "123456789"
    )


def test_missing_prior_state_is_a_valid_first_run(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        restore.checkpoint_state_restore,
        "restore_previous_checkpoint_databases",
        lambda **kwargs: {
            "status": "NO_DATABASES_IN_ARTIFACT",
            "restored_follow_up_seed": None,
        },
    )
    target = tmp_path / "watchlist.json"
    status = restore.restore_previous_watchlist(
        repository="example/repo",
        token="token",
        current_run_id=300,
        target=target,
        status_path=tmp_path / "restore-status.json",
    )
    assert status["status"] == "NO_PREVIOUS_STATE"
    assert not target.exists()


def test_invalid_restored_state_does_not_overwrite_current_file(
    monkeypatch, tmp_path
) -> None:
    target = tmp_path / "watchlist.json"
    target.write_text("keep-me", encoding="utf-8")

    def fake_restore(**kwargs):
        staged = Path(kwargs["status_path"]).parent / restore.WATCHLIST_FILENAME
        staged.write_text('{"scope": "SE"}', encoding="utf-8")
        return {
            "status": "RESTORED",
            "restored_follow_up_seed": {
                "archive_member": "bankruptcy-watchlist.json",
                "relative_path": staged.as_posix(),
            },
        }

    monkeypatch.setattr(
        restore.checkpoint_state_restore,
        "restore_previous_checkpoint_databases",
        fake_restore,
    )
    status = restore.restore_previous_watchlist(
        repository="example/repo",
        token="token",
        current_run_id=300,
        target=target,
        status_path=tmp_path / "restore-status.json",
    )
    assert status["status"] == "UNAVAILABLE"
    assert target.read_text(encoding="utf-8") == "keep-me"
