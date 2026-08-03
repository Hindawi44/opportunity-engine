"""Download the latest successful one-opportunity checkpoint analysis artifact."""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlencode
from zipfile import BadZipFile, ZipFile

from .checkpoint_state_restore import (
    ARTIFACT_NAME,
    PreviousCheckpointRestoreError,
    _request,
    _request_json,
)

ANALYSIS_MEMBERS = (
    "one-opportunity-daily-analysis.json",
    "one-opportunity-daily-analysis.txt",
    "multi-market-daily-checkpoint.json",
)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def extract_checkpoint_analysis(archive_bytes: bytes, output_dir: str | Path) -> list[dict[str, str]]:
    """Extract only allow-listed daily-analysis files from one checkpoint ZIP."""
    target_root = Path(output_dir)
    extracted: list[dict[str, str]] = []
    try:
        archive = ZipFile(BytesIO(archive_bytes))
    except BadZipFile as exc:
        raise PreviousCheckpointRestoreError("Checkpoint artifact is not a valid ZIP archive") from exc

    with archive:
        names = set(archive.namelist())
        for filename in ANALYSIS_MEMBERS:
            candidates = (
                f"artifacts/multi-market-daily-operator-checkpoint/{filename}",
                f"multi-market-daily-operator-checkpoint/{filename}",
                filename,
            )
            member = next((name for name in candidates if name in names), None)
            if member is None:
                continue
            payload = archive.read(member)
            destination = target_root / filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
            extracted.append(
                {
                    "archive_member": member,
                    "output_path": destination.as_posix(),
                }
            )

    analysis_path = target_root / "one-opportunity-daily-analysis.json"
    if not analysis_path.exists():
        raise PreviousCheckpointRestoreError(
            "Latest checkpoint artifact does not contain one-opportunity-daily-analysis.json"
        )
    payload = json.loads(analysis_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PreviousCheckpointRestoreError("Daily analysis JSON must be an object")
    return extracted


def download_latest_checkpoint_analysis(
    *,
    repository: str,
    token: str,
    output_dir: str | Path,
    status_path: str | Path,
    workflow_file: str = "multi-market-daily-operator-checkpoint.yaml",
    branch: str = "main",
    api_url: str = "https://api.github.com",
) -> dict[str, Any]:
    """Download the newest successful non-expired checkpoint artifact."""
    output = Path(status_path)
    base = api_url.rstrip("/")
    if not repository or "/" not in repository:
        raise ValueError("repository must use owner/name form")
    if not token:
        status = {"status": "UNAVAILABLE", "reason": "GITHUB_TOKEN is not available"}
        _write_json(output, status)
        return status

    try:
        query = urlencode(
            {
                "branch": branch,
                "event": "workflow_dispatch",
                "status": "success",
                "per_page": 10,
            }
        )
        runs_url = f"{base}/repos/{repository}/actions/workflows/{workflow_file}/runs?{query}"
        runs_payload = _request_json(runs_url, token)
        runs = runs_payload.get("workflow_runs") or []
        if not isinstance(runs, list):
            raise PreviousCheckpointRestoreError("workflow_runs must be a list")

        for run in runs:
            if not isinstance(run, Mapping):
                continue
            run_id = run.get("id")
            if not isinstance(run_id, int):
                continue
            artifacts_payload = _request_json(
                f"{base}/repos/{repository}/actions/runs/{run_id}/artifacts",
                token,
            )
            artifacts = artifacts_payload.get("artifacts") or []
            if not isinstance(artifacts, list):
                continue
            artifact = next(
                (
                    item
                    for item in artifacts
                    if isinstance(item, Mapping)
                    and item.get("name") == ARTIFACT_NAME
                    and item.get("expired") is not True
                ),
                None,
            )
            if not isinstance(artifact, Mapping):
                continue
            download_url = artifact.get("archive_download_url")
            if not isinstance(download_url, str) or not download_url:
                continue
            extracted = extract_checkpoint_analysis(
                _request(download_url, token, accept="application/vnd.github+json"),
                output_dir,
            )
            status = {
                "status": "RESTORED",
                "checkpoint_run_id": run_id,
                "checkpoint_artifact_id": artifact.get("id"),
                "extracted_files": extracted,
            }
            _write_json(output, status)
            return status

        status = {
            "status": "NO_SUCCESSFUL_CHECKPOINT_ARTIFACT",
            "reason": "No successful non-expired checkpoint artifact was found",
        }
        _write_json(output, status)
        return status
    except Exception as exc:
        status = {
            "status": "UNAVAILABLE",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        _write_json(output, status)
        return status
