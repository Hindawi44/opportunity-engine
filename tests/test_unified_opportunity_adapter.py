from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from opportunity_engine.discovery.unified_opportunity_adapter import (
    opportunity_record_from_discovery_candidate,
)
from opportunity_engine.unified_models import (
    EvaluationStatus,
    ListingStatus,
    WorkflowStatus,
)


def _candidate(**overrides):
    data = {
        "title": "8 stk Blåkläder T-skjorter i størrelse XL",
        "scenario": "AUCTION",
        "opportunity_state": "CONFIRMED_SALE",
        "reason": "specific active sale confirmed",
        "page_role": "ITEM_LISTING",
        "opportunity_identity": "url-id:557914",
        "identity_stable": True,
        "top5_eligible": True,
        "analysis_eligible": True,
        "discovery_score": 81,
        "discovery_band": "HIGH",
        "location": None,
        "company_name": None,
        "inventory_type": "skjorte",
        "price_nok": 300.0,
        "bid_price_nok": None,
        "quantity": 8,
        "published_at": None,
        "listing_status": "ACTIVE",
        "source_urls": [
            "https://auksjonen.no/auksjon/overskuddsvarer/test/557914"
        ],
        "source_providers": ["Auksjonen Current Category"],
        "evidence_signals": ["auksjon", "skjorte", "høyeste bud"],
        "missing_information": ["location"],
        "textile_category": "CLOTHING_INVENTORY",
        "verification": [
            {
                "url": "https://auksjonen.no/auksjon/overskuddsvarer/test/557914",
                "title": "8 stk Blåkläder T-skjorter",
                "text": "Antall: 8 stk T-skjorter",
                "bounded_context": "Antall: 8 stk T-skjorter",
                "listing_status": "ACTIVE",
                "page_role": "ITEM_LISTING",
                "event_scenario": "AUCTION",
                "verified": True,
            }
        ],
    }
    data.update(overrides)
    return data


def _convert(candidate):
    return opportunity_record_from_discovery_candidate(
        candidate,
        discovered_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )


def test_converts_confirmed_discovery_candidate_to_qualified_record():
    record = _convert(_candidate())

    assert record.opportunity_id == "url-id:557914"
    assert record.listing_status == ListingStatus.ACTIVE
    assert record.evaluation_status == EvaluationStatus.QUALIFIED
    assert record.workflow_status == WorkflowStatus.QUALIFIED_OPPORTUNITY
    assert record.price == 300
    assert record.quantity == 8
    assert record.verified is True
    assert record.analysis_eligible is True
    assert record.evidence[0].verified is True
    assert record.missing_information[0].field_name == "location"


def test_missing_quantity_remains_none_without_estimation():
    record = _convert(_candidate(quantity=None, missing_information=["location", "quantity"]))

    assert record.quantity is None
    assert [item.field_name for item in record.missing_information] == [
        "location",
        "quantity",
    ]


def test_unverified_strong_lead_stays_requires_verification():
    record = _convert(
        _candidate(
            opportunity_state="STRONG_LEAD_REQUIRES_VERIFICATION",
            listing_status="UNKNOWN",
            analysis_eligible=False,
            top5_eligible=False,
            verification=[],
        )
    )

    assert record.verified is False
    assert record.evaluation_status == EvaluationStatus.REQUIRES_VERIFICATION
    assert record.workflow_status == WorkflowStatus.REQUIRES_VERIFICATION


def test_historical_market_evidence_maps_to_dedicated_non_current_workflow():
    candidate = _candidate(
        listing_status="ENDED",
        opportunity_state="HISTORICAL_MARKET_EVIDENCE",
        reason="verified ended listing retained in the Historical Market Evidence path only",
        historical_market_evidence_eligible=True,
        analysis_eligible=False,
        top5_eligible=False,
        verification=[{
            "url": "https://auksjonen.no/auksjon/overskuddsvarer/test/557914",
            "title": "8 stk Blåkläder T-skjorter",
            "text": "Antall: 8 stk T-skjorter. Auksjonen er avsluttet.",
            "bounded_context": "Antall: 8 stk T-skjorter.",
            "listing_status": "ENDED",
            "page_role": "ITEM_LISTING",
            "event_scenario": "AUCTION",
            "verified": True,
        }],
    )
    record = _convert(candidate)

    assert record.listing_status == ListingStatus.ENDED
    assert record.evaluation_status == EvaluationStatus.HISTORICAL_ONLY
    assert record.workflow_status == WorkflowStatus.HISTORICAL_MARKET_EVIDENCE
    assert record.analysis_eligible is False
    assert record.top5_eligible is False
    assert record.metadata["historical_market_evidence_eligible"] is True


def test_unrouted_ended_listing_falls_back_to_closed_workflow():
    candidate = _candidate(
        listing_status="ENDED",
        opportunity_state="STRONG_LEAD_REQUIRES_VERIFICATION",
        analysis_eligible=False,
        top5_eligible=False,
    )
    record = _convert(candidate)

    assert record.listing_status == ListingStatus.ENDED
    assert record.evaluation_status == EvaluationStatus.REQUIRES_VERIFICATION
    assert record.workflow_status == WorkflowStatus.CLOSED
    assert record.analysis_eligible is False


def test_rejected_noise_maps_to_rejected_workflow():
    record = _convert(
        _candidate(
            opportunity_state="REJECTED_NOISE",
            listing_status="UNKNOWN",
            analysis_eligible=False,
            top5_eligible=False,
            verification=[],
        )
    )

    assert record.evaluation_status == EvaluationStatus.REJECTED
    assert record.workflow_status == WorkflowStatus.REJECTED


def test_missing_source_url_fails_closed():
    with pytest.raises(ValueError, match="source URL"):
        _convert(_candidate(source_urls=[]))


def test_missing_identity_is_rejected_by_canonical_model():
    with pytest.raises(ValidationError):
        _convert(_candidate(opportunity_identity=None))