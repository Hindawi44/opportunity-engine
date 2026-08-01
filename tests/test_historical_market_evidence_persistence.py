from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select

from opportunity_engine.discovery.unified_opportunity_adapter import (
    opportunity_record_from_discovery_candidate,
)
from opportunity_engine.persistence import (
    UnifiedOpportunityModel,
    UnifiedOpportunityRepository,
    create_database_engine,
    create_session_factory,
    persist_unified_opportunity_report,
    session_scope,
    upgrade_database,
)
from opportunity_engine.unified_models import (
    EvaluationStatus,
    WorkflowStatus,
)


ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_CONFIG = ROOT / "alembic.ini"


def _database_url(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'historical-market-evidence.db'}"


def _verification(
    *,
    url: str,
    quantity: int | None,
    content_match: bool,
) -> dict:
    return {
        "url": url,
        "title": "Blinto historical clothing lot",
        "text": "Parti med arbetsbyxor. Auktionen har avslutats.",
        "bounded_context": "Parti med arbetsbyxor. Auktionen har avslutats.",
        "location": "Växjö" if content_match else None,
        "inventory_type": "workwear_inventory" if content_match else None,
        "price_nok": None,
        "bid_price_nok": None,
        "quantity": quantity if content_match else None,
        "listing_status": "ENDED",
        "page_role": "ITEM_LISTING",
        "opportunity_identity": None,
        "identity_stable": True,
        "clothing_inventory_evidence": content_match,
        "sale_evidence": False,
        "event_scenario": "LARGE_LOT_SALE",
        "verified": True,
        "error": None,
        "verification_content_match": content_match,
        "historical_data_fields_trusted": content_match,
        "exclude_from_historical_price_analysis": not content_match,
    }


def _trusted_candidate(
    *,
    occurrence_id: str = "85260",
    bid: int = 5400,
) -> dict:
    url = f"https://blinto.se/auction/Blaklader-178629-{occurrence_id}"
    identity = f"blinto-auction:178629:{occurrence_id}"
    verification = _verification(url=url, quantity=38, content_match=True)
    verification["opportunity_identity"] = identity
    return {
        "title": "Arbetskläder - Blåkläder | Blinto auktioner",
        "scenario": "LARGE_LOT_SALE",
        "opportunity_state": "HISTORICAL_MARKET_EVIDENCE",
        "reason": "verified ended listing retained in the Historical Market Evidence path only",
        "page_role": "ITEM_LISTING",
        "opportunity_identity": identity,
        "identity_stable": True,
        "top5_eligible": False,
        "analysis_eligible": False,
        "discovery_score": 69,
        "discovery_band": "REVIEW",
        "location": "Växjö",
        "company_name": None,
        "inventory_type": "workwear_inventory",
        "price_nok": None,
        "bid_price_nok": None,
        "quantity": 38,
        "published_at": None,
        "listing_status": "ENDED",
        "source_urls": [url],
        "source_providers": ["Brave Search"],
        "evidence_signals": ["auksjon", "klær", "arbeidstøy", "vareparti"],
        "missing_information": ["price"],
        "verification": [verification],
        "verification_content_match": True,
        "historical_market_evidence_eligible": True,
        "historical_data_fields_trusted": True,
        "exclude_from_historical_price_analysis": False,
        "historical_price_analysis_exclusion_reason": None,
        "source_object_id": "178629",
        "auction_occurrence_id": occurrence_id,
        "bid_price_sek": bid,
        "bid_price_currency": "SEK",
        "bid_price_is_nok": False,
        "bid_price_trusted": True,
        "reference_value_sek": 50000,
        "reference_value_kind": "market_or_retail_reference",
        "reference_value_is_current_sale_price": False,
        "reference_value_trusted": True,
        "textile_category": "CLOTHING_INVENTORY",
    }


def _manual_review_candidate() -> dict:
    url = "https://blinto.se/auction/Arbetsbyxor-Double-W"
    identity = f"item-url:{url}"
    verification = _verification(url=url, quantity=None, content_match=False)
    verification["opportunity_identity"] = identity
    return {
        "title": "Blinto - Restparti - Arbetsbyxor Double W.",
        "scenario": "WAREHOUSE_SURPLUS",
        "opportunity_state": "HISTORICAL_EVIDENCE_REQUIRES_MANUAL_REVIEW",
        "reason": "verified ended item page does not contain matching bounded bulk clothing-inventory evidence",
        "page_role": "ITEM_LISTING",
        "opportunity_identity": identity,
        "identity_stable": True,
        "top5_eligible": False,
        "analysis_eligible": False,
        "discovery_score": 61,
        "discovery_band": "REVIEW",
        "location": None,
        "company_name": None,
        "inventory_type": None,
        "price_nok": None,
        "bid_price_nok": None,
        "quantity": None,
        "published_at": None,
        "listing_status": "ENDED",
        "source_urls": [url],
        "source_providers": ["Brave Search"],
        "evidence_signals": ["auksjon", "klær", "vareparti"],
        "missing_information": [
            "location",
            "price",
            "quantity",
            "matching bounded item description",
        ],
        "verification": [verification],
        "verification_content_match": False,
        "historical_market_evidence_eligible": False,
        "historical_data_fields_trusted": False,
        "exclude_from_historical_price_analysis": True,
        "historical_price_analysis_exclusion_reason": "verification_content_mismatch",
        "source_object_id": None,
        "auction_occurrence_id": None,
        "bid_price_sek": 2000,
        "bid_price_currency": "SEK",
        "bid_price_is_nok": False,
        "bid_price_trusted": False,
        "textile_category": "CLOTHING_INVENTORY",
    }


def _record(candidate: dict, *, observed_at: datetime) -> dict:
    return opportunity_record_from_discovery_candidate(
        candidate,
        discovered_at=observed_at,
        market_code="SE",
        currency="SEK",
        domain="CLOTHING_INVENTORY",
    ).model_dump(mode="json")


def _report(*records: dict, generated_at: str = "2026-08-01T16:30:00Z") -> dict:
    return {
        "schema_version": "1.1",
        "generated_at": generated_at,
        "market_code": "SE",
        "currency": "SEK",
        "record_count": len(records),
        "records": list(records),
        "conversion_error_count": 0,
        "conversion_errors": [],
    }


def test_adapter_preserves_trusted_historical_price_and_occurrence_metadata() -> None:
    record = opportunity_record_from_discovery_candidate(
        _trusted_candidate(),
        discovered_at=datetime(2026, 8, 1, 16, 30, tzinfo=timezone.utc),
        market_code="SE",
        currency="SEK",
        domain="CLOTHING_INVENTORY",
    )

    assert record.evaluation_status == EvaluationStatus.HISTORICAL_ONLY
    assert record.workflow_status == WorkflowStatus.HISTORICAL_MARKET_EVIDENCE
    assert record.currency == "SEK"
    assert record.bid_price == 5400
    assert record.analysis_eligible is False
    assert record.top5_eligible is False
    assert record.metadata["bid_price_trusted"] is True
    assert record.metadata["exclude_from_historical_price_analysis"] is False
    assert record.metadata["source_object_id"] == "178629"
    assert record.metadata["auction_occurrence_id"] == "85260"
    assert record.evidence[0].metadata["historical_data_fields_trusted"] is True


def test_sqlite_separates_trusted_history_from_manual_review(tmp_path: Path) -> None:
    database_url = _database_url(tmp_path)
    upgrade_database(database_url, config_path=ALEMBIC_CONFIG)
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    observed_at = datetime(2026, 8, 1, 16, 30, tzinfo=timezone.utc)
    trusted = _record(_trusted_candidate(), observed_at=observed_at)
    manual = _record(_manual_review_candidate(), observed_at=observed_at)

    with session_scope(factory) as session:
        summary = persist_unified_opportunity_report(
            _report(trusted, manual),
            UnifiedOpportunityRepository(session),
        )
        assert summary["schema_version"] == "1.1"
        assert summary["persisted_record_count"] == 2

    with session_scope(factory) as session:
        repository = UnifiedOpportunityRepository(session)
        trusted_evidence = repository.list_trusted_historical_market_evidence()
        trusted_prices = repository.list_trusted_historical_price_records()
        manual_review = repository.list_historical_evidence_manual_review()

        assert [item.opportunity_id for item in trusted_evidence] == [
            "blinto-auction:178629:85260"
        ]
        assert [item.bid_price for item in trusted_prices] == [5400]
        assert [item.opportunity_id for item in manual_review] == [
            "item-url:https://blinto.se/auction/Arbetsbyxor-Double-W"
        ]
        assert manual_review[0].bid_price is None
        metadata = manual_review[0].record_json["metadata"]
        assert metadata["bid_price_sek"] == 2000
        assert metadata["bid_price_trusted"] is False
        assert metadata["exclude_from_historical_price_analysis"] is True

    engine.dispose()


def test_same_occurrence_upserts_but_relisted_occurrence_creates_new_record(
    tmp_path: Path,
) -> None:
    database_url = _database_url(tmp_path)
    upgrade_database(database_url, config_path=ALEMBIC_CONFIG)
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    first_seen = datetime(2026, 8, 1, 16, 30, tzinfo=timezone.utc)
    later_seen = datetime(2026, 8, 2, 16, 30, tzinfo=timezone.utc)

    first = _record(_trusted_candidate(), observed_at=first_seen)
    repeated = _record(_trusted_candidate(), observed_at=later_seen)
    relisted = _record(
        _trusted_candidate(occurrence_id="99999", bid=6200),
        observed_at=later_seen,
    )

    with session_scope(factory) as session:
        repository = UnifiedOpportunityRepository(session)
        persist_unified_opportunity_report(_report(first), repository)
        persist_unified_opportunity_report(
            _report(repeated, generated_at="2026-08-02T16:30:00Z"),
            repository,
        )
        persist_unified_opportunity_report(
            _report(relisted, generated_at="2026-08-02T16:31:00Z"),
            repository,
        )

    with session_scope(factory) as session:
        repository = UnifiedOpportunityRepository(session)
        trusted_prices = repository.list_trusted_historical_price_records()
        assert [item.opportunity_id for item in trusted_prices] == [
            "blinto-auction:178629:85260",
            "blinto-auction:178629:99999",
        ]
        assert [item.bid_price for item in trusted_prices] == [5400, 6200]
        assert session.scalar(
            select(func.count()).select_from(UnifiedOpportunityModel)
        ) == 2

    engine.dispose()
