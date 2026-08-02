from __future__ import annotations

from datetime import datetime, timezone

from opportunity_engine.discovery.unified_opportunity_adapter import (
    opportunity_record_from_discovery_candidate,
)
from opportunity_engine.opportunity_lifecycle import LifecycleReasonCode
from opportunity_engine.unified_models import EvaluationStatus, WorkflowStatus


def _candidate(**overrides):
    value = {
        "title": "Parti arbeidsklær",
        "scenario": "AUCTION",
        "opportunity_state": "STRONG_LEAD_REQUIRES_VERIFICATION",
        "page_role": "ITEM_LISTING",
        "opportunity_identity": "item:1",
        "identity_stable": True,
        "top5_eligible": True,
        "analysis_eligible": False,
        "listing_status": "ACTIVE",
        "source_urls": ["https://example.test/item/1"],
        "source_providers": ["Test Source"],
        "evidence_signals": ["parti arbeidsklær"],
        "missing_information": ["final_payable_price"],
        "textile_category": "CLOTHING_INVENTORY",
        "verification": [],
    }
    value.update(overrides)
    return value


def _convert(candidate):
    return opportunity_record_from_discovery_candidate(
        candidate,
        discovered_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
    )


def test_adapter_records_lifecycle_reason_and_normalized_eligibility():
    record = _convert(
        _candidate(
            listing_status="ENDED",
            top5_eligible=True,
            analysis_eligible=True,
            verification=[
                {
                    "url": "https://example.test/item/1",
                    "bounded_context": "Parti arbeidsklær",
                    "verified": True,
                }
            ],
        )
    )

    assert record.workflow_status == WorkflowStatus.CLOSED
    assert record.evaluation_status == EvaluationStatus.REQUIRES_VERIFICATION
    assert record.top5_eligible is False
    assert record.analysis_eligible is False
    assert (
        record.metadata["lifecycle_reason_code"]
        == LifecycleReasonCode.INACTIVE_LISTING_CLOSED.value
    )


def test_adapter_routes_event_lead_to_early_signal():
    record = _convert(
        _candidate(
            page_role="EVENT_LEAD",
            listing_status="UNKNOWN",
            analysis_eligible=True,
        )
    )

    assert record.workflow_status == WorkflowStatus.EARLY_SIGNAL
    assert record.evaluation_status == EvaluationStatus.NOT_EVALUATED
    assert record.top5_eligible is True
    assert record.analysis_eligible is False
    assert (
        record.metadata["lifecycle_reason_code"]
        == LifecycleReasonCode.TRACEABLE_EARLY_SIGNAL.value
    )
