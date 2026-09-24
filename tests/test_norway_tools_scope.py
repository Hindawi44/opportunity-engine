from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_norway_openai_search_intelligence import build_norway_search_brief
from scripts.run_finn_email_intake import _parse_ingested_at


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"
FINN = ROOT / "scripts/run_finn_email_intake.py"


def _report(path: Path, *, market: str = "NO", identity: str = "lot-1") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.1",
                "generated_at": "2026-09-24T06:00:00Z",
                "record_count": 1,
                "records": [
                    {
                        "opportunity_id": identity,
                        "market_code": market,
                        "source_url": f"https://example.test/{identity}",
                        "source_provider": "fixture",
                        "title": "Fixture lot",
                        "listing_status": "ACTIVE",
                        "workflow_status": "REQUIRES_VERIFICATION",
                        "verified": False,
                        "analysis_eligible": False,
                        "top5_eligible": False,
                    }
                ],
                "conversion_error_count": 0,
                "conversion_errors": [],
            }
        ),
        encoding="utf-8",
    )


def test_daily_workflow_restores_existing_paid_and_gmail_tools_inside_norway_only() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    job = text.split("  norway-all-assets:\n", 1)[1].split("  norway-existing-engine:\n", 1)[0]

    assert 'cron: "47 6 * * *"' in text
    assert 'timezone: "Europe/Oslo"' in text
    assert "  workflow_dispatch:" in text

    for secret in (
        "EXA_API_KEY: ${{ secrets.EXA_API_KEY }}",
        "BRAVE_SEARCH_API_KEY: ${{ secrets.BRAVE_SEARCH_API_KEY }}",
        "GMAIL_CLIENT_ID: ${{ secrets.GMAIL_CLIENT_ID }}",
        "GMAIL_REFRESH_TOKEN: ${{ secrets.GMAIL_REFRESH_TOKEN }}",
        "OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}",
    ):
        assert secret in job

    assert "python scripts/run_exa_exact_lot_checkpoint.py" in job
    assert "--market NO" in job
    assert "--results-per-query 5" in job
    assert 'OPPORTUNITY_ALLOW_PAID_BRAVE_PUSH: "true"' in job
    assert 'OPPORTUNITY_ALLOW_PAID_BRAVE_MANUAL: "true"' in job

    assert "python scripts/run_finn_email_intake.py" in job
    assert "--gmail-api" in job
    assert "--max-messages 20" in job
    assert "newer_than:14d from:agent@finn.no" in job
    assert 'sqlite:///$INPUT_ROOT/no-finn-email/opportunity_engine.db' in job

    assert "python scripts/run_norway_openai_search_intelligence.py" in job
    assert 'OPENAI_HUNT_MAX_API_REQUESTS: "2"' in job
    assert 'OPENAI_HUNT_MAX_ESTIMATED_COST_USD: "0.08"' in job

    for foreign in ("--market SE", "--market DE", "--market FR", "--market IT", "--market NL"):
        assert foreign not in job


def test_openai_adapter_accepts_only_current_norway_source_reports(tmp_path: Path) -> None:
    root = tmp_path / "inputs"
    _report(root / "no-auksjonen" / "unified-opportunity-report.json", identity="auction-1")
    _report(root / "no-exa-exact-lot" / "unified-opportunity-report.json", identity="exa-1")
    _report(root / "no-finn-email" / "unified-opportunity-report.json", identity="finn-1")

    brief = build_norway_search_brief(root)

    assert brief["market_coverage"] == ["NO"]
    assert brief["counts"]["norway_search_signals"] == 3
    assert {row["source_country"] for row in brief["early_signals_to_watch"]} == {"NO"}
    assert brief["new_signals_today"] == []
    assert brief["automatic_purchase"] is False


def test_openai_adapter_fails_closed_if_foreign_record_leaks_into_no_path(tmp_path: Path) -> None:
    root = tmp_path / "inputs"
    _report(
        root / "no-exa-exact-lot" / "unified-opportunity-report.json",
        market="SE",
        identity="foreign-1",
    )
    with pytest.raises(ValueError, match="foreign record"):
        build_norway_search_brief(root)


def test_finn_gmail_runner_can_persist_to_existing_norway_sqlite() -> None:
    text = FINN.read_text(encoding="utf-8")
    assert 'parser.add_argument("--persist-unified", action="store_true")' in text
    assert 'parser.add_argument("--database-url", default="")' in text
    assert 'market_code="NO"' in text
    assert 'currency="NOK"' in text
    assert "persist_unified_report_with_artifacts" in text
    assert "_parse_ingested_at(collection.ingested_at)" in text


def test_finn_ingested_timestamp_is_converted_to_timezone_aware_datetime() -> None:
    parsed = _parse_ingested_at("2026-09-24T06:59:31.004223+00:00")
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() is not None


def test_workflow_surfaces_wrapped_source_failures_after_all_tools_run() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    job = text.split("  norway-all-assets:\n", 1)[1].split("  norway-existing-engine:\n", 1)[0]
    assert "Fail closed if a Norway source command failed" in job
    assert "no-auksjonen/execution-status.json" in job
    assert "no-exa-exact-lot/execution-status.json" in job
    assert "no-finn-email/execution-status.json" in job
    assert "Norway source command failure:" in job
