from __future__ import annotations

import json
from pathlib import Path

from opportunity_engine.discovery.unified_operator_report import (
    build_unified_operator_report,
    render_unified_operator_report,
    write_unified_operator_report,
)


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _inputs(root: Path) -> None:
    _write(
        root / "unified-six-market-pipeline-v1.json",
        {
            "generated_at": "2026-09-01T00:00:00+00:00",
            "pipeline_contract": "UNIFIED_SIX_MARKET_PIPELINE_V1",
            "markets": [{"market_code": code} for code in ("NO", "SE", "DE", "FR", "IT", "NL")],
        },
    )
    _write(root / "unified-search-runtime-v1.json", {"status": "SUCCESS"})
    _write(
        root / "multi-market-daily-checkpoint.json",
        {
            "source_execution_counts": {"SUCCESS": 4, "VALID_ZERO_RESULT": 2},
            "status_counts": {"ACTIVE": 1, "HISTORICAL": 3, "UNRESOLVED": 0},
            "top5_eligible_count": 1,
            "deduplicated_opportunities": [
                {"opportunity_id": "one", "top5_eligible": True},
                {"opportunity_id": "two", "top5_eligible": False},
            ],
            "next_human_action": {"action": "LEGACY_ACTION"},
        },
    )
    _write(
        root / "domain-market-intelligence-brief.json",
        {"selected_human_action": {"action": "DOMAIN_ACTION"}},
    )
    _write(
        root / "central-intelligence-brief.json",
        {
            "status": "SUCCESS",
            "primary_human_action": {
                "action_type": "REVIEW_TOP_ACTIONABLE_OPPORTUNITY",
                "target": "one",
                "reason": "Strongest verified candidate.",
            },
        },
    )


def test_report_uses_one_central_action_and_six_market_truth(tmp_path: Path) -> None:
    _inputs(tmp_path)

    report = build_unified_operator_report(tmp_path)

    assert report["authority"] == "UNIFIED_OPERATOR_REPORT_V1"
    assert report["market_coverage"] == ["NO", "SE", "DE", "FR", "IT", "NL"]
    assert report["primary_human_action"]["authority"] == "CENTRAL_INTELLIGENCE"
    assert report["primary_human_action"]["action"] == "REVIEW_TOP_ACTIONABLE_OPPORTUNITY"
    assert [row["opportunity_id"] for row in report["top5_opportunities"]] == ["one"]
    assert report["legacy_reports_are_not_operator_authority"] is True

    text = render_unified_operator_report(report)
    assert text.count("الإجراء البشري الوحيد:") == 1
    assert "NO | SE | DE | FR | IT | NL" in text
    assert "LEGACY_ACTION" not in text
    assert "DOMAIN_ACTION" not in text


def test_writer_emits_the_only_operator_authority_files(tmp_path: Path) -> None:
    _inputs(tmp_path)

    paths = write_unified_operator_report(tmp_path)

    assert paths["json"].name == "unified-operator-report-v1.json"
    assert paths["text"].name == "unified-operator-report-v1.txt"
    persisted = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert persisted["single_human_action_enforced"] is True
