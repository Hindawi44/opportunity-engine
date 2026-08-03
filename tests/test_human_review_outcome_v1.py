from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select

from opportunity_engine.persistence import (
    HumanReviewOutcomeModel,
    LifecycleEventModel,
    UnifiedOpportunityRepository,
    apply_human_review_outcome,
    create_database_engine,
    create_session_factory,
    session_scope,
    upgrade_database,
)
from opportunity_engine.persistence.unified_report_adapter import (
    persist_unified_opportunity_report,
)


ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_CONFIG = ROOT / "alembic.ini"
NOW = datetime(2026, 8, 3, 8, 30, tzinfo=timezone.utc)
OPPORTUNITY_ID = "https://ny.auksjonen.no/auksjon/torget/test/528194"


def _record() -> dict:
    return {
        "opportunity_id": OPPORTUNITY_ID,
        "market_code": "NO",
        "domain": "CLOTHING_INVENTORY",
        "category": "CLOTHING_INVENTORY",
        "title": "10 stk GSA multinorm arbeidsplagg",
        "source_provider": "Auksjonen.no",
        "source_url": OPPORTUNITY_ID,
        "listing_status": "ACTIVE",
        "evaluation_status": "REQUIRES_VERIFICATION",
        "workflow_status": "REQUIRES_VERIFICATION",
        "scenario": "WAREHOUSE_SURPLUS",
        "company_name": None,
        "location": "7800, Namsos",
        "inventory_type": "clothing_inventory_lot",
        "currency": "NOK",
        "price": 5000.0,
        "bid_price": None,
        "quantity": 10,
        "published_at": None,
        "discovered_at": NOW.isoformat(),
        "identity_stable": True,
        "verified": False,
        "analysis_eligible": False,
        "top5_eligible": True,
        "market_signals": [],
        "evidence": [],
        "missing_information": [
            {"field_name": "verified exact item-page evidence"}
        ],
        "metadata": {
            "lifecycle_reason_code": "MISSING_REQUIRED_VERIFICATION",
            "verification_blockers": ["verified exact item-page evidence"],
            "analysis_tasks": [
                "calculate final payable price including auction fees and VAT"
            ],
        },
    }


def _report(record: dict | None = None, *, generated_at: datetime = NOW) -> dict:
    records = [deepcopy(record or _record())]
    return {
        "schema_version": "1.1",
        "generated_at": generated_at.isoformat(),
        "record_count": len(records),
        "conversion_error_count": 0,
        "records": records,
        "conversion_errors": [],
    }


def _database(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'opportunity_engine.db'}"
    upgrade_database(url, config_path=ALEMBIC_CONFIG)
    engine = create_database_engine(url)
    return engine, create_session_factory(engine)


def test_verified_review_promotes_and_survives_source_refresh(tmp_path: Path) -> None:
    engine, factory = _database(tmp_path)
    with session_scope(factory) as session:
        repository = UnifiedOpportunityRepository(session)
        persist_unified_opportunity_report(_report(), repository)
        result = apply_human_review_outcome(
            repository,
            opportunity_id=OPPORTUNITY_ID,
            outcome="VERIFIED",
            reviewed_at=NOW + timedelta(minutes=1),
            reviewer="Hindawi44",
            note="Exact item page checked manually.",
            request_id="github-run:1",
        )
        assert result["workflow_status"] == "ACTIVE_OPPORTUNITY"
        assert result["evaluation_status"] == "NOT_EVALUATED"
        assert result["verified"] is True
        assert result["analysis_eligible"] is True
        assert result["remaining_missing_information"] == []
        assert result["lifecycle_transition_created"] is True

    with session_scope(factory) as session:
        repository = UnifiedOpportunityRepository(session)
        replay = persist_unified_opportunity_report(
            _report(generated_at=NOW + timedelta(minutes=2)),
            repository,
        )
        saved = repository.get(OPPORTUNITY_ID)
        assert replay["lifecycle_events_created"] == 0
        assert saved is not None
        assert saved.workflow_status == "ACTIVE_OPPORTUNITY"
        assert saved.analysis_eligible is True
        assert saved.record_json["metadata"]["human_review"]["outcome"] == "VERIFIED"
        assert session.scalar(select(func.count()).select_from(HumanReviewOutcomeModel)) == 1
        assert session.scalar(select(func.count()).select_from(LifecycleEventModel)) == 2
    engine.dispose()


def test_same_review_request_is_idempotent(tmp_path: Path) -> None:
    engine, factory = _database(tmp_path)
    with session_scope(factory) as session:
        repository = UnifiedOpportunityRepository(session)
        persist_unified_opportunity_report(_report(), repository)
        first = apply_human_review_outcome(
            repository,
            opportunity_id=OPPORTUNITY_ID,
            outcome="NEEDS_MORE_INFORMATION",
            reviewed_at=NOW + timedelta(minutes=1),
            reviewer="Hindawi44",
            note="Need a clearer condition photo.",
            request_id="github-run:2",
        )
        second = apply_human_review_outcome(
            repository,
            opportunity_id=OPPORTUNITY_ID,
            outcome="NEEDS_MORE_INFORMATION",
            reviewed_at=NOW + timedelta(minutes=1),
            reviewer="Hindawi44",
            note="Need a clearer condition photo.",
            request_id="github-run:2",
        )
        assert first["lifecycle_transition_created"] is True
        assert second["lifecycle_transition_created"] is False
        assert session.scalar(select(func.count()).select_from(HumanReviewOutcomeModel)) == 1
        assert session.scalar(select(func.count()).select_from(LifecycleEventModel)) == 2
    engine.dispose()


def test_rejected_review_removes_current_top5_eligibility(tmp_path: Path) -> None:
    engine, factory = _database(tmp_path)
    with session_scope(factory) as session:
        repository = UnifiedOpportunityRepository(session)
        persist_unified_opportunity_report(_report(), repository)
        result = apply_human_review_outcome(
            repository,
            opportunity_id=OPPORTUNITY_ID,
            outcome="REJECTED",
            reviewed_at=NOW + timedelta(minutes=1),
            reviewer="Hindawi44",
            note="Not a commercially useful clothing lot.",
        )
        assert result["workflow_status"] == "REJECTED"
        assert result["evaluation_status"] == "REJECTED"
        assert result["top5_eligible"] is False
        assert result["analysis_eligible"] is False
    engine.dispose()


def test_real_source_closure_outranks_previous_verified_review(tmp_path: Path) -> None:
    engine, factory = _database(tmp_path)
    with session_scope(factory) as session:
        repository = UnifiedOpportunityRepository(session)
        persist_unified_opportunity_report(_report(), repository)
        apply_human_review_outcome(
            repository,
            opportunity_id=OPPORTUNITY_ID,
            outcome="VERIFIED",
            reviewed_at=NOW + timedelta(minutes=1),
        )

    ended = _record()
    ended.update(
        {
            "listing_status": "ENDED",
            "evaluation_status": "REQUIRES_VERIFICATION",
            "workflow_status": "CLOSED",
            "verified": False,
            "analysis_eligible": False,
            "top5_eligible": False,
        }
    )
    ended["metadata"]["lifecycle_reason_code"] = "INACTIVE_LISTING_CLOSED"
    with session_scope(factory) as session:
        repository = UnifiedOpportunityRepository(session)
        summary = persist_unified_opportunity_report(
            _report(ended, generated_at=NOW + timedelta(minutes=2)),
            repository,
        )
        saved = repository.get(OPPORTUNITY_ID)
        assert summary["lifecycle_events_created"] == 1
        assert saved is not None
        assert saved.listing_status == "ENDED"
        assert saved.workflow_status == "CLOSED"
        assert saved.analysis_eligible is False
    engine.dispose()
