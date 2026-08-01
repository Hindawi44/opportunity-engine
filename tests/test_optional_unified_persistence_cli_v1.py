from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import scripts.run_clothing_inventory_discovery_search as runner
from opportunity_engine.persistence import live_unified_persistence


class _FakeSourceProvider:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def diagnostics(self) -> dict:
        return {
            "requests_made": 1,
            "request_budget": 1,
            "raw_hits": 0,
            "accepted_hits": 0,
            "rejected_hits": 0,
        }


def _patch_discovery(monkeypatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "test-key")
    monkeypatch.setattr(
        runner,
        "build_structured_discovery_queries",
        lambda _budget: [SimpleNamespace(query_id="q1", query="query")],
    )
    monkeypatch.setattr(runner, "BraveSearchProvider", lambda *_a, **_k: object())
    monkeypatch.setattr(runner, "SourceTargetedSearchProvider", _FakeSourceProvider)
    monkeypatch.setattr(
        runner,
        "run_clothing_inventory_discovery",
        lambda *_a, **_k: {
            "search_run_report": {
                "status": "SUCCESS",
                "queries_submitted": 1,
                "norway_textile_page_verification_accepted": 0,
                "top5_count": 0,
            },
            "all_discovered_candidates": [],
            "discovery_top5": [],
        },
    )
    monkeypatch.setattr(runner, "apply_early_opportunity_gate", lambda value: value)
    monkeypatch.setattr(
        runner,
        "apply_post_verification_top5_hard_gate",
        lambda value: value,
    )
    monkeypatch.setattr(
        runner,
        "apply_norway_textile_page_verification_policy",
        lambda value: value,
    )

    def write_discovery(_result, output_dir):
        path = Path(output_dir) / "search-run-report.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
        return {"search_run_report": path}

    def write_unified(_result, output_dir):
        path = Path(output_dir) / "unified-opportunity-report.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "generated_at": "2026-08-01T07:00:00Z",
                    "record_count": 0,
                    "records": [],
                    "conversion_error_count": 0,
                    "conversion_errors": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    monkeypatch.setattr(runner, "write_discovery_artifacts", write_discovery)
    monkeypatch.setattr(runner, "write_unified_opportunity_report", write_unified)
    return tmp_path / "unified-opportunity-report.json"


def test_default_cli_remains_json_only(monkeypatch, tmp_path: Path) -> None:
    report_path = _patch_discovery(monkeypatch, tmp_path)
    called = False

    def unexpected_persistence(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("persistence must remain opt-in")

    monkeypatch.setattr(
        live_unified_persistence,
        "persist_unified_report_with_artifacts",
        unexpected_persistence,
    )
    monkeypatch.setattr(
        runner.sys,
        "argv",
        ["run_clothing_inventory_discovery_search.py", "--output-dir", str(tmp_path)],
    )

    assert runner.main() == 0
    assert report_path.exists()
    assert called is False
    assert not (tmp_path / "unified-persistence-summary.json").exists()


def test_persist_flag_runs_after_json_and_surfaces_failure_without_deletion(
    monkeypatch,
    tmp_path: Path,
) -> None:
    report_path = _patch_discovery(monkeypatch, tmp_path)

    def failing_persistence(source_path, output_dir, **_kwargs):
        assert Path(source_path).exists()
        error_path = Path(output_dir) / "unified-persistence-error.json"
        error_path.write_text('{"status":"FAILED"}\n', encoding="utf-8")
        raise live_unified_persistence.UnifiedPersistenceExecutionError(
            "database unavailable",
            artifact_path=error_path,
        )

    monkeypatch.setattr(
        live_unified_persistence,
        "persist_unified_report_with_artifacts",
        failing_persistence,
    )
    monkeypatch.setattr(
        runner.sys,
        "argv",
        [
            "run_clothing_inventory_discovery_search.py",
            "--output-dir",
            str(tmp_path),
            "--persist-unified",
            "--database-url",
            f"sqlite:///{tmp_path / 'database.db'}",
        ],
    )

    assert runner.main() == 2
    assert report_path.exists()
    assert (tmp_path / "unified-persistence-error.json").exists()
