from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from opportunity_engine.discovery.human_review_checkpoint import (
    reconcile_checkpoint_human_reviews,
)
from opportunity_engine.persistence import (
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
OPPORTUNITY_ID = "https://ny.auksjonen.no/auksjon/torget/test/528194"
NOW = datetime(2026, 8, 3, 8, 30, tzinfo=timezone.utc)


def _canonical_record() -> dict:
    return {
        "opportunity_id": OPPORTUNITY_ID,
        "market_code": "NO",
        "domain": "CLOTHING_INVENTORY",
        "category": "CLOTHING_INVENTORY",
        "title": "10 stk arbeidsplagg",
        "source_provider": "Auksjonen.no",
        "source_url": OPPORTUNITY_ID,
        "listing_status": "ACTIVE",
        "evaluation_status": "REQUIRES_VERIFICATION",
        "workflow_status": "REQUIRES_VERIFICATION",
        "scenario": "WAREHOUSE_SURPLUS",
        "company_name": None,
        "location": "Namsos",
        "inventory_type": "clothing_inventory_lot",
        "currency": "NOK",
        "price": 1000.0,
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
            "analysis_tasks": ["calculate final payable price"],
        },
    }


def _checkpoint() -> dict:
    return {
        "deduplicated_opportunities": [
            {
                "opportunity_identity": OPPORTUNITY_ID,
                "title": "10 stk arbeidsplagg",
                "market_code": "NO",
                "listing_status": "ACTIVE",
                "workflow_status": "REQUIRES_VERIFICATION",
                "evaluation_status": "REQUIRES_VERIFICATION",
                "top5_eligible": True,
                "analysis_eligible": False,
                "missing_evidence": ["verified exact item-page evidence"],
            }
        ],
        "deduplicated_record_count": 1,
        "status_counts": {
            "ACTIVE": 1,
            "ENDED": 0,
            "HISTORICAL": 0,
            "UNRESOLVED": 0,
            "UPCOMING": 0,
        },
        "top5_eligible_count": 1,
        "analysis_eligible_count": 0,
        "markets": [
            {
                "market_code": "NO",
                "active_count": 1,
                "top5_eligible_count": 1,
                "deduplicated_record_count": 1,
            }
        ],
        "next_human_action": {
            "action": "REVIEW_ONE_OPPORTUNITY",
            "opportunity_identity": OPPORTUNITY_ID,
        },
        "lifecycle": {
            "stage_counts": {
                "EARLY_SIGNAL": 0,
                "CANDIDATE": 0,
                "REQUIRES_VERIFICATION": 1,
                "ACTIVE_OPPORTUNITY": 0,
                "QUALIFIED_OPPORTUNITY": 0,
                "HISTORICAL_MARKET_EVIDENCE": 0,
                "CLOSED": 0,
                "REJECTED": 0,
            },
            "evaluation_status_counts": {"REQUIRES_VERIFICATION": 1},
            "requires_verification_count": 1,
        },
    }


def test_checkpoint_uses_persisted_verified_review(tmp_path: Path) -> None:
    directory = tmp_path / "artifacts/multi-market-inputs/no-auksjonen"
    directory.mkdir(parents=True)
    database = directory / "opportunity_engine.db"
    url = f"sqlite:///{database}"
    upgrade_database(url, config_path=ROOT / "alembic.ini")
    engine = create_database_engine(url)
    factory = create_session_factory(engine)
    report = {
        "schema_version": "1.1",
        "generated_at": NOW.isoformat(),
        "record_count": 1,
        "conversion_error_count": 0,
        "records": [_canonical_record()],
        "conversion_errors": [],
    }
    with session_scope(factory) as session:
        repository = UnifiedOpportunityRepository(session)
        persist_unified_opportunity_report(report, repository)
        apply_human_review_outcome(
            repository,
            opportunity_id=OPPORTUNITY_ID,
            outcome="VERIFIED",
            reviewed_at=NOW,
            reviewer="Hindawi44",
        )
    engine.dispose()

    manifest = {
        "sources": [
            {
                "market_code": "NO",
                "source_name": "Auksjonen.no",
                "artifact_dir": "artifacts/multi-market-inputs/no-auksjonen",
            }
        ]
    }
    result = reconcile_checkpoint_human_reviews(
        _checkpoint(), manifest, root=tmp_path
    )
    record = result["deduplicated_opportunities"][0]
    assert record["workflow_status"] == "ACTIVE_OPPORTUNITY"
    assert record["analysis_eligible"] is True
    assert record["verified"] is True
    assert record["missing_evidence"] == []
    assert record["analysis_tasks"] == ["calculate final payable price"]
    assert result["analysis_eligible_count"] == 1
    assert result["lifecycle"]["stage_counts"]["ACTIVE_OPPORTUNITY"] == 1
    assert result["lifecycle"]["requires_verification_count"] == 0
    assert result["next_human_action"]["workflow_status"] == "ACTIVE_OPPORTUNITY"
    assert "ready for human analysis" in result["next_human_action"]["reason"]
