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
    "v2.6.6-live-dry-run.yml",
    "v2.7.1-real-dataset-validation.yml",
    "v2.7.2.2-internal-score-audit.yml",
    "v2.7.2.3-score-engine-trace-audit.yml",
    "v2.7.2.4.1-research-candidate-audit.yml",
    "v2.7.2.4.2-bootstrap-pipeline-integration.yml",
    "v2.7.2.4.3-external-evidence-execution-audit.yml",
    "v2.7.2.4.4-brave-transport-response-audit.yml",
    "v2.7.2.4.5-brave-response-content-audit.yml",
    "v2.7.2.4.7-comparable-acceptance-audit.yml",
    "v2.7.2.5-external-financial-final-score.yml",
    "v2.8.1-external-market-comparables.yml",
    "v2.8.2-comparable-evidence-integration.yml",
    "v2.8.2b-comparable-evidence-e2e-acceptance.yml",
    "v2.9-auction-cost-logistics-e2e.yml",
    "v2.10-verified-financial-integration.yml",
    "v2.11-live-opportunity-validation.yml",
    "v30-multi-opportunity-ranking.yml",
    "v31-live-batch-validation.yml",
    "v3.2-continuous-opportunity-monitoring.yml",
    "v3.3-live-source-ingestion.yml",
    "v3.4-persistent-opportunity-state.yml",
    "v3.5-opportunity-alert-review-queue.yml",
    "v3.6-multi-source-ingestion.yml",
    "v3.7-production-pilot.yml",
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
