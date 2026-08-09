from io import BytesIO
from zipfile import ZipFile

import opportunity_engine.discovery.checkpoint_state_restore as restore


def _artifact_zip() -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(
            "multi-market-inputs/no-auksjonen/opportunity_engine.db",
            b"SQLite format 3\x00scheduled-state",
        )
    return buffer.getvalue()


def test_restore_uses_latest_successful_scheduled_checkpoint(monkeypatch, tmp_path) -> None:
    requested_urls: list[str] = []

    def fake_request_json(url: str, token: str):
        requested_urls.append(url)
        if "/actions/workflows/" in url:
            return {
                "workflow_runs": [
                    {"id": 300, "event": "pull_request"},
                    {"id": 200, "event": "schedule"},
                    {"id": 100, "event": "workflow_dispatch"},
                ]
            }
        if "/actions/runs/200/artifacts" in url:
            return {
                "artifacts": [
                    {
                        "id": 999,
                        "name": restore.ARTIFACT_NAME,
                        "expired": False,
                        "archive_download_url": "https://example.invalid/artifact.zip",
                    }
                ]
            }
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(restore, "_request_json", fake_request_json)
    monkeypatch.setattr(
        restore,
        "_request",
        lambda url, token, *, accept: _artifact_zip(),
    )

    status = restore.restore_previous_checkpoint_databases(
        repository="example/repo",
        token="token",
        current_run_id=400,
        input_root=tmp_path / "inputs",
        status_path=tmp_path / "restore-status.json",
    )

    assert status["status"] == "RESTORED"
    assert status["previous_run_id"] == 200
    assert status["previous_run_event"] == "schedule"
    assert status["previous_artifact_id"] == 999
    assert len(status["restored_databases"]) == 1
    assert "event=" not in requested_urls[0]
    assert "status=success" in requested_urls[0]
    assert "branch=main" in requested_urls[0]
