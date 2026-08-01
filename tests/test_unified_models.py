from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from opportunity_engine.unified_models import (
    EvaluationStatus,
    Evidence,
    ListingStatus,
    MarketSignal,
    MissingInformation,
    OpportunityRecord,
    WorkflowStatus,
)


def _record(**overrides):
    data = {
        "opportunity_id": "url-id:557914",
        "market_code": "no",
        "domain": "TEXTILE_AND_SEWING",
        "category": "CLOTHING_INVENTORY",
        "title": "8 stk Blåkläder T-skjorter",
        "source_provider": "Auksjonen Current Category",
        "source_url": "https://auksjonen.no/auksjon/overskuddsvarer/test/557914",
        "listing_status": ListingStatus.ACTIVE,
        "evaluation_status": EvaluationStatus.QUALIFIED,
        "workflow_status": WorkflowStatus.QUALIFIED_OPPORTUNITY,
        "price": 300,
        "quantity": 8,
        "discovered_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
        "identity_stable": True,
        "verified": True,
        "analysis_eligible": True,
        "top5_eligible": True,
        "market_signals": [
            MarketSignal(signal_type="AUCTION", value="høyeste bud")
        ],
        "evidence": [
            Evidence(
                evidence_type="PUBLIC_PAGE",
                value="Antall: 8 stk",
                source_url="https://auksjonen.no/auksjon/overskuddsvarer/test/557914",
                verified=True,
            )
        ],
        "missing_information": [
            MissingInformation(field_name="location", required_for="logistics")
        ],
    }
    data.update(overrides)
    return OpportunityRecord(**data)


def test_builds_canonical_verified_opportunity_record():
    record = _record()

    assert record.market_code == "NO"
    assert record.currency == "NOK"
    assert record.quantity == 8
    assert record.listing_status == ListingStatus.ACTIVE
    assert record.workflow_status == WorkflowStatus.QUALIFIED_OPPORTUNITY
    assert record.missing_information[0].field_name == "location"


def test_missing_quantity_remains_none_without_guessing():
    record = _record(quantity=None)

    assert record.quantity is None


def test_rejects_zero_or_negative_quantity():
    with pytest.raises(ValidationError):
        _record(quantity=0)


def test_ended_listing_cannot_be_analysis_eligible():
    with pytest.raises(ValidationError, match="inactive listings"):
        _record(
            listing_status=ListingStatus.ENDED,
            evaluation_status=EvaluationStatus.REQUIRES_VERIFICATION,
            workflow_status=WorkflowStatus.CLOSED,
            verified=True,
            analysis_eligible=True,
        )


def test_qualified_evaluation_requires_verification():
    with pytest.raises(ValidationError, match="must be verified"):
        _record(verified=False)


def test_rejects_unknown_fields_to_keep_schema_stable():
    with pytest.raises(ValidationError):
        _record(unexpected_field="not allowed")
