from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import scripts.run_end_to_end_pipeline as pipeline


def test_dry_run_records_all_stages_without_execution(tmp_path: Path) -> None:
    result = pipeline.run_pipeline(tmp_path, dry_run=True)

    assert result == 0
    payload = json.loads((tmp_path / "data/pipeline_run_status.json").read_text())
    assert payload["status"] == "DRY_RUN"
    assert payload["failed_stage"] is None
    assert len(payload["stages"]) == len(pipeline.STAGES)
    assert all(item["status"] == "SKIPPED_DRY_RUN" for item in payload["stages"])


def test_pipeline_stops_at_first_failed_stage(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command, cwd, check):
        calls.append(command)
        return SimpleNamespace(returncode=7 if len(calls) == 2 else 0)

    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)
    stages = (
        ("first", ("scripts/first.py",)),
        ("second", ("scripts/second.py",)),
        ("third", ("scripts/third.py",)),
    )

    result = pipeline.run_pipeline(tmp_path, stages=stages)

    assert result == 7
    assert len(calls) == 2
    payload = json.loads((tmp_path / "data/pipeline_run_status.json").read_text())
    assert payload["status"] == "FAILED"
    assert payload["failed_stage"] == "second"
    assert [item["status"] for item in payload["stages"]] == ["SUCCESS", "FAILED"]


def test_success_publishes_canonical_outputs(tmp_path: Path, monkeypatch) -> None:
    data = tmp_path / "data"
    data.mkdir()
    fixtures = {
        "top5_opportunities.json": {"ranked": [{"id": "one"}]},
        "todays_opportunities.json": {"rows": [{"id": "one"}]},
        "opportunity_channels.json": {"sale": [], "bankruptcy": []},
        "source_funnel.json": {"sources": {}},
        "smart_alerts.json": {"alerts": []},
    }
    for name, payload in fixtures.items():
        (data / name).write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(
        pipeline.subprocess,
        "run",
        lambda command, cwd, check: SimpleNamespace(returncode=0),
    )

    result = pipeline.run_pipeline(
        tmp_path,
        stages=(("only", ("scripts/only.py",)),),
    )

    assert result == 0
    assert json.loads((data / "opportunities.json").read_text()) == fixtures[
        "top5_opportunities.json"
    ]
    assert json.loads((data / "dashboard.json").read_text()) == fixtures[
        "todays_opportunities.json"
    ]
    report = json.loads((data / "daily_report.json").read_text())
    assert report["status"] == "SUCCESS"
    status = json.loads((data / "pipeline_run_status.json").read_text())
    assert status["status"] == "SUCCESS"
    assert status["canonical_outputs"]["alerts"] == "data/smart_alerts.json"
