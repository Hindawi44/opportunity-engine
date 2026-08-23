"""Restore durable checkpoint state from the last successful artifact.

The restore is read-only against GitHub Actions. It copies only explicitly
allow-listed SQLite databases, one read-only cross-source follow-up seed, and
explicitly allow-listed learning JSON state. Missing prior state is a valid
first-run condition. Network or permission failures are reported in a
structured status artifact and do not invent cross-run continuity.
"""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zipfile import BadZipFile, ZipFile


ARTIFACT_NAME = "multi-market-daily-operator-checkpoint"
RESTORABLE_EVENTS = {"workflow_dispatch", "schedule"}
DATABASE_RELATIVE_PATHS = (
    "no-auksjonen/opportunity_engine.db",
    "no-finn-email/opportunity_engine.db",
    "se-blinto/opportunity_engine.db",
    "de-riegermann/opportunity_engine.db",
    "de-venta/opportunity_engine.db",
    "de-dpv/opportunity_engine.db",
)
FOLLOW_UP_SEED_FILENAME = "previous-cross-source-scent-v2.json"
FOLLOW_UP_SEED_MEMBERS = (
    "multi-market-daily-operator-checkpoint/cross-source-scent-v2/cross-source-scent-expansion-v2.json",
    "cross-source-scent-v2/cross-source-scent-expansion-v2.json",
)
LEARNING_STATE_FILENAMES = (
    "missed-opportunities.json",
    "active-keyword-overlay.json",
    "keyword-learning-history.json",
    "parser-rescue-overlay.json",
    "search-success-memory.json",
)


class PreviousCheckpointRestoreError(RuntimeError):
    """Raised when an artifact exists but its allowed durable payload is invalid."""


def _origin(url: str) -> tuple[str, str, int | None]:
    parsed = urlsplit(url)
    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme.lower() == "https" else 80
    return parsed.scheme.lower(), (parsed.hostname or "").lower(), port


class _CrossOriginAuthorizationRedirectHandler(HTTPRedirectHandler):
    """Do not forward the GitHub bearer token to artifact blob storage.

    GitHub's artifact archive endpoint returns a temporary redirect to an external
    signed blob URL. ``urllib`` normally copies request headers across redirects,
    including ``Authorization``. External blob storage must receive only the signed
    URL, not the repository token.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None and _origin(req.full_url) != _origin(newurl):
            redirected.remove_header("Authorization")
        return redirected


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _request(url: str, token: str, *, accept: str) -> bytes:
    request = Request(
        url,
        headers={
            "Accept": accept,
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "opportunity-engine-lifecycle-checkpoint",
        },
    )
    opener = build_opener(_CrossOriginAuthorizationRedirectHandler())
    with opener.open(request, timeout=60) as response:  # noqa: S310 - fixed GitHub API URL
        return response.read()


def _request_json(url: str, token: str) -> dict[str, Any]:
    payload = json.loads(
        _request(url, token, accept="application/vnd.github+json").decode("utf-8")
    )
    if not isinstance(payload, dict):
        raise PreviousCheckpointRestoreError("GitHub API response must be an object")
    return payload


def extract_previous_databases(
    archive_bytes: bytes,
    input_root: str | Path,
) -> list[dict[str, str]]:
    """Copy only allow-listed checkpoint databases from one artifact archive."""
    destination_root = Path(input_root)
    restored: list[dict[str, str]] = []
    try:
        archive = ZipFile(BytesIO(archive_bytes))
    except BadZipFile as exc:
        raise PreviousCheckpointRestoreError(
            "Previous checkpoint artifact is not a valid ZIP archive"
        ) from exc

    with archive:
        names = set(archive.namelist())
        for relative in DATABASE_RELATIVE_PATHS:
            candidates = (
                f"artifacts/multi-market-inputs/{relative}",
                f"multi-market-inputs/{relative}",
                relative,
            )
            member = next((name for name in candidates if name in names), None)
            if member is None:
                continue
            payload = archive.read(member)
            if not payload.startswith(b"SQLite format 3\x00"):
                raise PreviousCheckpointRestoreError(
                    f"Restored database is not SQLite: {member}"
                )
            target = destination_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            restored.append(
                {
                    "archive_member": member,
                    "relative_path": target.as_posix(),
                }
            )
    return restored


def extract_previous_follow_up_seed(
    archive_bytes: bytes,
    output_dir: str | Path,
) -> dict[str, str] | None:
    """Restore only the prior V2 report used to bootstrap entity continuity."""
    try:
        archive = ZipFile(BytesIO(archive_bytes))
    except BadZipFile as exc:
        raise PreviousCheckpointRestoreError(
            "Previous checkpoint artifact is not a valid ZIP archive"
        ) from exc

    with archive:
        names = set(archive.namelist())
        member = next((name for name in FOLLOW_UP_SEED_MEMBERS if name in names), None)
        if member is None:
            return None
        try:
            payload = json.loads(archive.read(member).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PreviousCheckpointRestoreError(
                f"Previous follow-up seed is not valid JSON: {member}"
            ) from exc
        if not isinstance(payload, dict):
            raise PreviousCheckpointRestoreError(
                f"Previous follow-up seed must be a JSON object: {member}"
            )
        target = Path(output_dir) / FOLLOW_UP_SEED_FILENAME
        _write_json(target, payload)
        return {
            "archive_member": member,
            "relative_path": target.as_posix(),
        }


def extract_previous_learning_state(
    archive_bytes: bytes,
    input_root: str | Path,
) -> list[dict[str, str]]:
    """Restore only explicitly allow-listed learning JSON state.

    Learning survives between scheduled runs via the existing checkpoint
    artifact rather than by mutating repository files. Arbitrary JSON members
    are never restored.
    """
    try:
        archive = ZipFile(BytesIO(archive_bytes))
    except BadZipFile as exc:
        raise PreviousCheckpointRestoreError(
            "Previous checkpoint artifact is not a valid ZIP archive"
        ) from exc

    restored: list[dict[str, str]] = []
    destination_root = Path(input_root) / "learning"
    with archive:
        names = set(archive.namelist())
        for filename in LEARNING_STATE_FILENAMES:
            candidates = (
                f"artifacts/multi-market-inputs/learning/{filename}",
                f"multi-market-inputs/learning/{filename}",
                f"learning/{filename}",
            )
            member = next((name for name in candidates if name in names), None)
            if member is None:
                continue
            try:
                payload = json.loads(archive.read(member).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise PreviousCheckpointRestoreError(
                    f"Previous learning state is not valid JSON: {member}"
                ) from exc
            if not isinstance(payload, dict):
                raise PreviousCheckpointRestoreError(
                    f"Previous learning state must be a JSON object: {member}"
                )
            target = destination_root / filename
            _write_json(target, payload)
            restored.append(
                {
                    "filename": filename,
                    "archive_member": member,
                    "relative_path": target.as_posix(),
                }
            )
    return restored


def restore_previous_checkpoint_databases(
    *,
    repository: str,
    token: str,
    current_run_id: int,
    input_root: str | Path,
    status_path: str | Path,
    workflow_file: str = "multi-market-daily-operator-checkpoint.yaml",
    branch: str = "main",
    api_url: str = "https://api.github.com",
) -> dict[str, Any]:
    """Restore the newest successful manual or scheduled checkpoint artifact."""
    output = Path(status_path)
    base = api_url.rstrip("/")
    if not repository or "/" not in repository:
        raise ValueError("repository must use owner/name form")
    if not token:
        status = {
            "status": "UNAVAILABLE",
            "reason": "GITHUB_TOKEN is not available",
            "restored_databases": [],
            "restored_follow_up_seed": None,
            "restored_learning_state": [],
        }
        _write_json(output, status)
        return status

    try:
        query = urlencode(
            {
                "branch": branch,
                "status": "success",
                "per_page": 20,
            }
        )
        runs_url = (
            f"{base}/repos/{repository}/actions/workflows/{workflow_file}/runs?{query}"
        )
        runs_payload = _request_json(runs_url, token)
        runs = runs_payload.get("workflow_runs") or []
        if not isinstance(runs, list):
            raise PreviousCheckpointRestoreError("workflow_runs must be a list")

        for run in runs:
            if not isinstance(run, Mapping):
                continue
            event = str(run.get("event") or "").strip()
            if event not in RESTORABLE_EVENTS:
                continue
            run_id = run.get("id")
            if not isinstance(run_id, int) or run_id == current_run_id:
                continue
            artifacts_url = f"{base}/repos/{repository}/actions/runs/{run_id}/artifacts"
            artifacts_payload = _request_json(artifacts_url, token)
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
            artifact_id = artifact.get("id")
            if not isinstance(download_url, str) or not download_url:
                continue
            archive_bytes = _request(
                download_url,
                token,
                accept="application/vnd.github+json",
            )
            restored = extract_previous_databases(archive_bytes, input_root)
            follow_up_seed = extract_previous_follow_up_seed(
                archive_bytes,
                output.parent,
            )
            learning_state = extract_previous_learning_state(
                archive_bytes,
                input_root,
            )
            status = {
                "status": (
                    "RESTORED"
                    if restored or follow_up_seed or learning_state
                    else "NO_DATABASES_IN_ARTIFACT"
                ),
                "previous_run_id": run_id,
                "previous_run_event": event,
                "previous_artifact_id": artifact_id,
                "restored_databases": restored,
                "restored_follow_up_seed": follow_up_seed,
                "restored_learning_state": learning_state,
            }
            _write_json(output, status)
            return status

        status = {
            "status": "NO_PREVIOUS_STATE",
            "reason": "No earlier successful non-expired checkpoint artifact was found",
            "restored_databases": [],
            "restored_follow_up_seed": None,
            "restored_learning_state": [],
        }
        _write_json(output, status)
        return status
    except Exception as exc:  # keep discovery available while reporting lost continuity
        status = {
            "status": "UNAVAILABLE",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "restored_databases": [],
            "restored_follow_up_seed": None,
            "restored_learning_state": [],
        }
        _write_json(output, status)
        return status
