"""Restore the newest executable MIND FORGE search hypothesis for the daily checkpoint.

This is a read-only GitHub Actions artifact bridge. It reuses the existing
mind-forge-creative-v2-open-live artifact and never creates another persistence
system. Only fast_learning_memory.json files that contain a READY
pending_search_experiment_spec are accepted.
"""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlencode
from zipfile import BadZipFile, ZipFile

from opportunity_engine.discovery.checkpoint_state_restore import (
    _request,
    _request_json,
)

WORKFLOW_FILE = "mind-forge-live-research-launcher.yaml"
ARTIFACT_NAME = "mind-forge-creative-v2-open-live"
OUTPUT_FILENAME = "mind-forge-fast-learning-memory.json"
MAX_RUNS_TO_INSPECT = 5


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _extract_fast_memory(archive_bytes: bytes) -> dict[str, Any] | None:
    try:
        archive = ZipFile(BytesIO(archive_bytes))
    except BadZipFile:
        return None
    with archive:
        candidates = [
            name
            for name in archive.namelist()
            if name == "fast_learning_memory.json"
            or name.endswith("/fast_learning_memory.json")
        ]
        for member in sorted(candidates, key=lambda value: (value.count("/"), len(value))):
            try:
                payload = json.loads(archive.read(member).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            spec = payload.get("pending_search_experiment_spec")
            if not isinstance(spec, Mapping) or str(spec.get("status") or "").upper() != "READY":
                continue
            return payload
    return None


def restore_latest_mind_forge_search_memory(
    *,
    repository: str,
    token: str,
    input_root: str | Path,
    branch: str = "main",
    api_url: str = "https://api.github.com",
) -> dict[str, Any]:
    target = Path(input_root) / "learning" / OUTPUT_FILENAME
    if not token:
        return {
            "status": "UNAVAILABLE",
            "reason": "GITHUB_TOKEN is not available",
            "restored": False,
        }
    if not repository or "/" not in repository:
        return {
            "status": "UNAVAILABLE",
            "reason": "repository must use owner/name form",
            "restored": False,
        }

    base = api_url.rstrip("/")
    try:
        query = urlencode(
            {
                "branch": branch,
                "status": "success",
                "per_page": MAX_RUNS_TO_INSPECT,
            }
        )
        runs = _request_json(
            f"{base}/repos/{repository}/actions/workflows/{WORKFLOW_FILE}/runs?{query}",
            token,
        ).get("workflow_runs") or []
        if not isinstance(runs, list):
            raise ValueError("workflow_runs must be a list")

        inspected = 0
        for run in runs:
            if not isinstance(run, Mapping):
                continue
            run_id = run.get("id")
            if not isinstance(run_id, int):
                continue
            inspected += 1
            artifacts = _request_json(
                f"{base}/repos/{repository}/actions/runs/{run_id}/artifacts",
                token,
            ).get("artifacts") or []
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
            archive = _request(
                download_url,
                token,
                accept="application/vnd.github+json",
            )
            fast_memory = _extract_fast_memory(archive)
            if fast_memory is None:
                continue
            _write_json(target, fast_memory)
            spec = fast_memory.get("pending_search_experiment_spec") or {}
            return {
                "status": "RESTORED",
                "restored": True,
                "mind_forge_run_id": run_id,
                "artifact_id": artifact.get("id"),
                "experiment_fingerprint": spec.get("experiment_fingerprint"),
                "market_code": spec.get("market_code"),
                "project_domain": spec.get("project_domain"),
                "slot_id": spec.get("slot_id"),
                "relative_path": target.as_posix(),
                "runs_inspected": inspected,
            }

        if target.exists():
            target.unlink()
        return {
            "status": "NO_PENDING_SEARCH_EXPERIMENT",
            "restored": False,
            "runs_inspected": inspected,
        }
    except Exception as exc:
        if target.exists():
            target.unlink()
        return {
            "status": "UNAVAILABLE",
            "restored": False,
            "error_type": type(exc).__name__,
            "error": str(exc)[:500],
        }
