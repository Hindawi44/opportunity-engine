from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import func, select

from opportunity_engine.persistence.database import (
    create_database_engine,
    create_session_factory,
    session_scope,
)
from opportunity_engine.persistence.live_unified_persistence import (
    ERROR_FILENAME,
    PIPELINE_NAME,
    SUMMARY_FILENAME,
    UnifiedPersistenceExecutionError,
    persist_unified_report_with_artifacts,
)
from opportunity_engine.persistence.models import SourceRunModel, UnifiedOpportunityModel


ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_CONFIG = ROOT / "alembic.ini"
OPPORTUNITY_ID = "url-id:557914"


def _database_url(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'live-unified.db'}"


def _record() -> dict:
    return {
        "opportunity_id": OPPORTUNITY_ID,
        "market_code": "NO",
        "domain": "TEXTILE_AND_SEWING",
        "category": "CLOTHING_INVENTORY",
        "title": "8 stk Blåkläder T-skjorter i størrelse XL",
        "source_provider": "Auksjonen Current Category",
        "source_url": "https://example.test/opportunity/557914",
        "listing_status": "ACTIVE",
        "evaluation_status": "QUALIFIED",
        "workflow_status": "QUALIFIED_OPPORTUNITY",
        "scenario": "AUCTION",
        "company_name": None,
        "location": None,
        "inventory_type": "skjorte",
        "currency": "NOK",
        "price": 300.0,
        "bid_price": None,
        "quantity": 8,
        "published_at": None,
        "discovered_at": "2026-08-01T07:00:00Z",
        "identity_stable": True,
        "verified": True,
        "analysis_eligible": True,
        "top5_eligible": True,
        "market_signals": [],
        "evidence": [],
        "missing_information": [
            {
                "field_name": "location",
                "reason": None,
                "required_for": None,
            }
        ],
        "metadata": {},
    }


def _report(*records: dict) -> dict:
    return {
        "schema_version": "1.0",
        "generated_at": "2026-08-01T07:00:00Z",
        "record_count": len(records),
        "records": list(records),
        "conversion_error_count": 0,
        "conversion_errors": [],
    }


def _write_report(path: Path, report: dict) -> str:
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    return text


def test_optional_live_persistence_writes_summary_and_keeps_json_official(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "unified-opportunity-report.json"
    original_text = _write_report(report_path, _report(_record()))
    database_url = _database_url(tmp_path)

    summary, summary_path = persist_unified_report_with_artifacts(
        report_path,
        tmp_path,
        database_url=database_url,
        config_path=ALEMBIC_CONFIG,
    )

    assert summary_path == tmp_path / SUMMARY_FILENAME
    assert summary["persisted_record_count"] == 1
    assert summary["persisted_opportunity_ids"] == [OPPORTUNITY_ID]
    assert summary["pipeline_name"] == PIPELINE_NAME
    assert summary["json_reports_remain_official"] is True
    assert report_path.read_text(encoding="utf-8") == original_text

    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    with session_scope(factory) as session:
        assert session.scalar(
            select(func.count()).select_from(UnifiedOpportunityModel)
        ) == 1
        run = session.scalar(select(SourceRunModel))
        assert run is not None
        assert run.pipeline_name == PIPELINE_NAME
        assert run.zero_result is False
    engine.dispose()


def test_zero_record_report_is_saved_as_a_successful_zero_result_run(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "unified-opportunity-report.json"
    _write_report(report_path, _report())
    database_url = _database_url(tmp_path)

    summary, _ = persist_unified_report_with_artifacts(
        report_path,
        tmp_path,
        database_url=database_url,
        config_path=ALEMBIC_CONFIG,
    )

    assert summary["persisted_record_count"] == 0
    assert summary["zero_result"] is True

    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    with session_scope(factory) as session:
        run = session.scalar(select(SourceRunModel))
        assert run is not None
        assert run.status == "SUCCESS"
        assert run.zero_result is True
        assert session.scalar(
            select(func.count()).select_from(UnifiedOpportunityModel)
        ) == 0
    engine.dispose()


def test_repeating_the_same_report_is_idempotent_for_rows_and_run_identity(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "unified-opportunity-report.json"
    _write_report(report_path, _report(_record()))
    database_url = _database_url(tmp_path)

    first, _ = persist_unified_report_with_artifacts(
        report_path,
        tmp_path,
        database_url=database_url,
        config_path=ALEMBIC_CONFIG,
    )
    second, _ = persist_unified_report_with_artifacts(
        report_path,
        tmp_path,
        database_url=database_url,
        config_path=ALEMBIC_CONFIG,
    )

    assert first["run_id"] == second["run_id"]
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    with session_scope(factory) as session:
        assert session.scalar(
            select(func.count()).select_from(UnifiedOpportunityModel)
        ) == 1
        assert session.scalar(select(func.count()).select_from(SourceRunModel)) == 1
    engine.dispose()


def test_persistence_failure_writes_error_artifact_without_deleting_report(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "unified-opportunity-report.json"
    original_text = _write_report(
        report_path,
        {
            "schema_version": "1.0",
            "generated_at": "2026-08-01T07:00:00Z",
            "record_count": 1,
            "records": [],
            "conversion_error_count": 0,
            "conversion_errors": [],
        },
    )

    with pytest.raises(UnifiedPersistenceExecutionError) as captured:
        persist_unified_report_with_artifacts(
            report_path,
            tmp_path,
            database_url=_database_url(tmp_path),
            config_path=ALEMBIC_CONFIG,
        )

    assert captured.value.artifact_path == tmp_path / ERROR_FILENAME
    error = json.loads(captured.value.artifact_path.read_text(encoding="utf-8"))
    assert error["status"] == "FAILED"
    assert error["json_reports_remain_official"] is True
    assert error["report_deleted"] is False
    assert report_path.exists()
    assert report_path.read_text(encoding="utf-8") == original_text
