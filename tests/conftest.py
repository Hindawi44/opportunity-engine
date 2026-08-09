from __future__ import annotations

from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]
_ARCHIVE = _ROOT / "docs" / "workflow-archive"
_ARCHIVED_WORKFLOW_NAMES = {
    "daily-opportunity-pipeline.yml",
    "scheduled-agent.yml",
    "discovery-v1-clothing-inventory.yml",
    "discovery-v1.1-live-search.yml",
    "discovery-v1.2-live-pilot.yml",
    "v3.2-continuous-opportunity-monitoring.yml",
    "v3.3-live-source-ingestion.yml",
}
_ORIGINAL_PATH_READ_TEXT = Path.read_text


def _is_archived_workflow_contract(path: Path) -> bool:
    if path.name not in _ARCHIVED_WORKFLOW_NAMES:
        return False
    normalized = path.as_posix().replace("//", "/")
    return ".github/workflows/" in normalized


def _read_text_with_workflow_archive_fallback(self: Path, *args, **kwargs):
    try:
        return _ORIGINAL_PATH_READ_TEXT(self, *args, **kwargs)
    except FileNotFoundError:
        if not _is_archived_workflow_contract(self):
            raise
        archived = _ARCHIVE / self.name
        return _ORIGINAL_PATH_READ_TEXT(archived, *args, **kwargs)


# Historical workflow-regression tests intentionally keep their old paths. The
# workflow YAMLs themselves now live outside .github/workflows so GitHub Actions
# will not register them as runnable workflows.
Path.read_text = _read_text_with_workflow_archive_fallback
