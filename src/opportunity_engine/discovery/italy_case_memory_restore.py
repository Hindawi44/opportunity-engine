"""Restore only Italy case-memory state from an earlier successful live run."""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zipfile import BadZipFile, ZipFile


ARTIFACT_NAME = "italy-case-memory-v1"
WORKFLOW_FILE = "tests.yml"
DATABASE_RELATIVE_PATH = "it-market/opportunity_engine.db"


class ItalyMemoryRestoreError(RuntimeError):
    pass


def _origin(url: str) -> tuple[str, str, int]:
    parsed = urlsplit(url)
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    return parsed.scheme.lower(), (parsed.hostname or "").lower(), port


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None and _origin(req.full_url) != _origin(newurl):
            redirected.remove_header("Authorization")
        return redirected


def _request(url: str, token: str, *, accept: str) -> bytes:
    request = Request(
        url,
        headers={
            "Accept": accept,
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "opportunity-engine-italy-memory",
        },
    )
    opener = build_opener(_SafeRedirectHandler())
    with opener.open(request, timeout=60) as response:  # noqa: S310 - fixed GitHub API host
        return response.read()


def _request_json(url: str, token: str) -> dict[str, Any]:
    payload = json.loads(
        _request(url, token, accept="application/vnd.github+json").decode("utf-8")
    )
    if not isinstance(payload, dict):
        raise ItalyMemoryRestoreError("GitHub API response must be an object")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def extract_italy_memory_database(
    archive_bytes: bytes,
    state_root: str | Path,
) -> dict[str, str] | None:
    """Extract only the allow-listed Italy SQLite database from one artifact."""
    try:
        archive = ZipFile(BytesIO(archive_bytes))
    except BadZipFile as exc:
        raise ItalyMemoryRestoreError("Italy memory artifact is not a valid ZIP") from exc

    candidates = (
        f"artifacts/italy-case-memory/{DATABASE_RELATIVE_PATH}",
        f"italy-case-memory/{DATABASE_RELATIVE_PATH}",
        DATABASE_RELATIVE_PATH,
    )
    with archive:
        names = set(archive.namelist())
        member = next((name for name in candidates if name in names), None)
        if member is None:
            return None
        payload = archive.read(member)
        if not payload.startswith(b"SQLite format 3\x00"):
            raise ItalyMemoryRestoreError(f"Restored Italy memory is not SQLite: {member}")
        target = Path(state_root) / DATABASE_RELATIVE_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        return {"archive_member": member, "relative_path": target.as_posix()}


def restore_previous_italy_memory(
    *,
    repository: str,
    token: str,
    current_run_id: int,
    state_root: str | Path,
    status_path: str | Path,
    workflow_file: str = WORKFLOW_FILE,
    branch: str = "main",
    api_url: str = "https://api.github.com",
) -> dict[str, Any]:
    """Restore the newest previous successful Italy-memory artifact, if one exists."""
    output = Path(status_path)
    if not repository or "/" not in repository:
        raise ValueError("repository must use owner/name form")
    if not token:
        status = {"status": "UNAVAILABLE", "reason": "GITHUB_TOKEN_MISSING", "restored_database": None}
        _write_json(output, status)
        return status

    base = api_url.rstrip("/")
    try:
        query = urlencode({"branch": branch, "status": "success", "event": "push", "per_page": 40})
        runs = _request_json(
            f"{base}/repos/{repository}/actions/workflows/{workflow_file}/runs?{query}",
            token,
        ).get("workflow_runs") or []
        if not isinstance(runs, list):
            raise ItalyMemoryRestoreError("workflow_runs must be a list")

        for run in runs:
            if not isinstance(run, Mapping):
                continue
            run_id = run.get("id")
            if not isinstance(run_id, int) or run_id == current_run_id:
                continue
            artifacts = _request_json(
                f"{base}/repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100",
                token,
            ).get("artifacts") or []
            if not isinstance(artifacts, list):
                continue
            artifact = next(
                (
                    item for item in artifacts
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
            archive_bytes = _request(download_url, token, accept="application/vnd.github+json")
            restored = extract_italy_memory_database(archive_bytes, state_root)
            if restored is None:
                continue
            status = {
                "status": "RESTORED",
                "previous_run_id": run_id,
                "previous_artifact_id": artifact.get("id"),
                "restored_database": restored,
            }
            _write_json(output, status)
            return status

        status = {
            "status": "NO_PREVIOUS_STATE",
            "reason": "No previous successful Italy memory artifact was found",
            "restored_database": None,
        }
        _write_json(output, status)
        return status
    except Exception as exc:
        status = {
            "status": "UNAVAILABLE",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "restored_database": None,
        }
        _write_json(output, status)
        return status
