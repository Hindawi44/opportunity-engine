from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
import pytest
from sqlalchemy import func, inspect, select

from opportunity_engine.persistence import (
    UnifiedOpportunityEvidenceModel,
    UnifiedOpportunityModel,
    UnifiedOpportunityRepository,
    UnifiedReportPersistenceError,
    build_alembic_config,
    create_database_engine,
    create_session_factory,
    persist_unified_opportunity_report,
    session_scope,
    upgrade_database,
)


ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_CONFIG = ROOT / "alembic.ini"
OPPORTUNITY_ID = "url-id:557914"


def _database_url(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'unified-opportunities.db'}"


def _record(**overrides) -> dict:
    record = {
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
        "market_signals": [
            {
                "signal_type": "AUCTION",
                "value": "høyeste bud",
                "source": "Auksjonen Current Category",
                "observed_at": None,
                "confidence": None,
            }
        ],
        "evidence": [
            {
                "evidence_type": "PUBLIC_PAGE",
                "value": "Antall: 8 stk T-skjorter",
                "source_url": "https://example.test/opportunity/557914",
                "captured_at": None,
                "verified": True,
                "metadata": {
                    "page_role": "ITEM_LISTING",
                    "listing_status": "ACTIVE",
                },
            }
        ],
        "missing_information": [
            {
                "field_name": "location",
                "reason": None,
                "required_for": None,
            }
        ],
        "metadata": {
            "discovery_score": 81,
            "discovery_band": "HIGH",
        },
    }
    record.update(overrides)
    return record


def _report(*records: dict, generated_at: str = "2026-08-01T07:00:00Z") -> dict:
    return {
        "schema_version": "1.0",
        "generated_at": generated_at,
        "record_count": len(records),
        "records": list(records),
        "conversion_error_count": 0,
        "conversion_errors": [],
    }


def _utcish(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def test_head_migration_adds_isolated_unified_tables(tmp_path: Path) -> None:
    database_url = _database_url(tmp_path)

    upgrade_database(database_url, config_path=ALEMBIC_CONFIG)
    engine = create_database_engine(database_url)
    tables = set(inspect(engine).get_table_names())

    assert "unified_opportunities" in tables
    assert "unified_opportunity_evidence" in tables
    assert "opportunities" in tables
    engine.dispose()


def test_persists_canonical_record_evidence_and_original_json(tmp_path: Path) -> None:
    database_url = _database_url(tmp_path)
    upgrade_database(database_url, config_path=ALEMBIC_CONFIG)
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    source_record = _record()

    with session_scope(factory) as session:
        summary = persist_unified_opportunity_report(
            _report(source_record),
            UnifiedOpportunityRepository(session),
            source_ref="artifacts/unified-opportunity-report.json",
        )
        assert summary["persisted_opportunity_ids"] == [OPPORTUNITY_ID]
        assert summary["zero_result"] is False

    with session_scope(factory) as session:
        repository = UnifiedOpportunityRepository(session)
        saved = repository.get(OPPORTUNITY_ID)
        evidence = repository.list_evidence(OPPORTUNITY_ID)
        history = repository.list_workflow_history(OPPORTUNITY_ID)

        assert saved is not None
        assert saved.workflow_status == "QUALIFIED_OPPORTUNITY"
        assert saved.price == 300.0
        assert saved.quantity == 8
        assert saved.location is None
        assert saved.record_json == source_record
        assert len(evidence) == 1
        assert evidence[0].value == "Antall: 8 stk T-skjorter"
        assert evidence[0].verified is True
        assert [(item.from_status, item.to_status) for item in history] == [
            (None, "QUALIFIED_OPPORTUNITY")
        ]

    engine.dispose()


def test_repeated_snapshot_is_idempotent_and_status_change_is_append_only(
    tmp_path: Path,
) -> None:
    database_url = _database_url(tmp_path)
    upgrade_database(database_url, config_path=ALEMBIC_CONFIG)
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    original = _record()

    with session_scope(factory) as session:
        repository = UnifiedOpportunityRepository(session)
        persist_unified_opportunity_report(_report(original), repository)
        persist_unified_opportunity_report(_report(original), repository)

    changed = deepcopy(original)
    changed.update(
        {
            "listing_status": "UNKNOWN",
            "evaluation_status": "REQUIRES_VERIFICATION",
            "workflow_status": "REQUIRES_VERIFICATION",
            "verified": False,
            "analysis_eligible": False,
            "top5_eligible": False,
            "price": None,
            "quantity": None,
        }
    )
    with session_scope(factory) as session:
        persist_unified_opportunity_report(
            _report(changed, generated_at="2026-08-01T08:00:00Z"),
            UnifiedOpportunityRepository(session),
        )

    with session_scope(factory) as session:
        repository = UnifiedOpportunityRepository(session)
        saved = repository.get(OPPORTUNITY_ID)
        history = repository.list_workflow_history(OPPORTUNITY_ID)

        assert saved is not None
        assert saved.workflow_status == "REQUIRES_VERIFICATION"
        assert saved.price is None
        assert saved.quantity is None
        assert _utcish(saved.first_seen_at) == datetime(
            2026, 8, 1, 7, 0, tzinfo=timezone.utc
        )
        assert _utcish(saved.last_seen_at) == datetime(
            2026, 8, 1, 8, 0, tzinfo=timezone.utc
        )
        assert session.scalar(
            select(func.count()).select_from(UnifiedOpportunityModel)
        ) == 1
        assert session.scalar(
            select(func.count()).select_from(UnifiedOpportunityEvidenceModel)
        ) == 1
        assert [(item.from_status, item.to_status) for item in history] == [
            (None, "QUALIFIED_OPPORTUNITY"),
            ("QUALIFIED_OPPORTUNITY", "REQUIRES_VERIFICATION"),
        ]

    engine.dispose()


def test_zero_record_report_is_valid_and_does_not_create_rows(tmp_path: Path) -> None:
    database_url = _database_url(tmp_path)
    upgrade_database(database_url, config_path=ALEMBIC_CONFIG)
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)

    with session_scope(factory) as session:
        summary = persist_unified_opportunity_report(
            _report(),
            UnifiedOpportunityRepository(session),
        )
        assert summary["persisted_record_count"] == 0
        assert summary["zero_result"] is True
        assert session.scalar(
            select(func.count()).select_from(UnifiedOpportunityModel)
        ) == 0

    engine.dispose()


def test_report_envelope_counts_and_duplicate_ids_fail_closed(tmp_path: Path) -> None:
    database_url = _database_url(tmp_path)
    upgrade_database(database_url, config_path=ALEMBIC_CONFIG)
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)

    bad_count = _report(_record())
    bad_count["record_count"] = 2
    with pytest.raises(UnifiedReportPersistenceError, match="record_count"):
        with session_scope(factory) as session:
            persist_unified_opportunity_report(
                bad_count,
                UnifiedOpportunityRepository(session),
            )

    with pytest.raises(UnifiedReportPersistenceError, match="duplicate opportunity_id"):
        with session_scope(factory) as session:
            persist_unified_opportunity_report(
                _report(_record(), _record()),
                UnifiedOpportunityRepository(session),
            )

    engine.dispose()


def test_migration_can_return_to_persistence_foundation_v1(tmp_path: Path) -> None:
    database_url = _database_url(tmp_path)
    upgrade_database(database_url, config_path=ALEMBIC_CONFIG)
    config = build_alembic_config(database_url, config_path=ALEMBIC_CONFIG)

    command.downgrade(config, "0001_persistence_foundation_v1")
    engine = create_database_engine(database_url)
    tables = set(inspect(engine).get_table_names())

    assert "unified_opportunities" not in tables
    assert "unified_opportunity_evidence" not in tables
    assert "opportunities" in tables
    engine.dispose()
