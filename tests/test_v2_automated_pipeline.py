from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_dry_run_writes_safe_audit_record(tmp_path: Path) -> None:
    root = tmp_path
    (root / "scripts").mkdir()
    source = Path(__file__).resolve().parents[1] / "scripts" / "run_v2_automated_pipeline.py"
    (root / "scripts" / "run_v2_automated_pipeline.py").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    (root / "scripts" / "run_p5_learning_pipeline.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    (root / "scripts" / "run_v2_smart_alert_pipeline.py").write_text("raise SystemExit(0)\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "scripts/run_v2_automated_pipeline.py", "--root", str(root), "--dry-run", "--trigger", "test"],
        cwd=root,
        check=False,
    )
    assert result.returncode == 0

    status = json.loads((root / "data" / "automated_pipeline_status.json").read_text(encoding="utf-8"))
    history = json.loads((root / "data" / "automated_pipeline_history.json").read_text(encoding="utf-8"))

    assert status["status"] == "SUCCESS"
    assert status["trigger"] == "test"
    assert status["safety"] == {
        "automatic_purchase": False,
        "automatic_bid": False,
        "automatic_external_action": False,
    }
    assert status["stages"][0]["name"] == "complete_sources_decisions_actions_learning"
    assert history["run_count"] == 1
    assert history["runs"][0]["run_id"] == status["run_id"]


def test_failed_stage_is_recorded(tmp_path: Path) -> None:
    root = tmp_path
    (root / "scripts").mkdir()
    source = Path(__file__).resolve().parents[1] / "scripts" / "run_v2_automated_pipeline.py"
    (root / "scripts" / "run_v2_automated_pipeline.py").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    (root / "scripts" / "run_p5_learning_pipeline.py").write_text("raise SystemExit(7)\n", encoding="utf-8")
    (root / "scripts" / "run_v2_smart_alert_pipeline.py").write_text("raise SystemExit(0)\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "scripts/run_v2_automated_pipeline.py", "--root", str(root), "--trigger", "test"],
        cwd=root,
        check=False,
    )
    assert result.returncode == 7
    status = json.loads((root / "data" / "automated_pipeline_status.json").read_text(encoding="utf-8"))
    assert status["status"] == "FAILED"
    assert status["failed_stage"] == "complete_sources_decisions_actions_learning"
    assert len(status["stages"]) == 1
