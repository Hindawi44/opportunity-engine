from __future__ import annotations

import json
from pathlib import Path

from opportunity_engine.discovery.multi_market_operator_checkpoint import (
    build_multi_market_checkpoint,
    render_phone_summary,
)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _empty_source(
    root: Path,
    name: str,
    *,
    market: str,
    currency: str,
    report: dict[str, object],
) -> dict[str, str]:
    directory = root / name
    _write(directory / "execution-status.json", {"exit_code": 0})
    _write(
        directory / "search-run-report.json",
        {
            "market_code": market,
            "currency": currency,
            "currency_conversion_performed": False,
            **report,
        },
    )
    _write(directory / "all-discovered-candidates.json", [])
    _write(directory / "discovery-top5.json", [])
    _write(
        directory / "unified-opportunity-report.json",
        {
            "market_code": market,
            "currency": currency,
            "record_count": 0,
            "conversion_error_count": 0,
            "records": [],
        },
    )
    _write(
        directory / "unified-persistence-summary.json",
        {"status": "SUCCESS", "persisted_record_count": 0},
    )
    return {
        "market_code": market,
        "source_name": name,
        "currency": currency,
        "artifact_dir": name,
    }


def test_cost_guard_skip_is_not_reported_as_valid_zero(tmp_path: Path) -> None:
    no_source = _empty_source(
        tmp_path,
        "no-cost-guarded",
        market="NO",
        currency="NOK",
        report={
            "status": "SUCCESS",
            "cost_guard_status": "SKIPPED_COST_GUARD",
            "cost_guard_reason": "MANUAL_WORKFLOW_PAID_BRAVE_BLOCKED",
            "queries_submitted": 0,
            "paid_brave_requests": 0,
        },
    )
    se_source = _empty_source(
        tmp_path,
        "se-valid-zero",
        market="SE",
        currency="SEK",
        report={"status": "PASS"},
    )
    de_source = _empty_source(
        tmp_path,
        "de-valid-zero",
        market="DE",
        currency="EUR",
        report={"status": "PASS"},
    )

    report = build_multi_market_checkpoint(
        {"sources": [no_source, se_source, de_source]},
        {
            "markets": [
                {"market_code": "NO", "sources": []},
                {"market_code": "SE", "sources": []},
                {"market_code": "DE", "sources": []},
            ]
        },
        root=tmp_path,
        generated_at="2026-08-28T08:00:00+00:00",
    )

    assert report["source_execution_counts"] == {
        "SKIPPED_COST_GUARD": 1,
        "VALID_ZERO_RESULT": 2,
    }
    no_run = next(item for item in report["sources"] if item["market_code"] == "NO")
    assert no_run["execution_status"] == "SKIPPED_COST_GUARD"
    assert report["markets"][0]["source_execution_counts"] == {
        "SKIPPED_COST_GUARD": 1
    }
    assert report["next_human_action"]["action"] == "NO_IMMEDIATE_ACTION"

    summary = render_phone_summary(report)
    assert "تخطي حماية التكلفة 1" in summary
    assert "صفر صحيح 2" in summary
