from copy import deepcopy
from datetime import datetime, timezone
import json

from opportunity_engine.discovery.unified_opportunity_report import (
    build_unified_opportunity_report,
    serialize_unified_opportunity_report,
    write_unified_opportunity_report,
)

_GENERATED_AT = datetime(2026, 8, 1, tzinfo=timezone.utc)
_SOURCE_URL = "https://auksjonen.no/auksjon/overskuddsvarer/test/557914"


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
        "source_urls": [_SOURCE_URL],
        "source_providers": ["Auksjonen Current Category"],
        "evidence_signals": ["auksjon", "skjorte", "høyeste bud"],
        "missing_information": ["location"],
        "textile_category": "CLOTHING_INVENTORY",
        "verification": [
            {
                "url": _SOURCE_URL,
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


def _build(*candidates):
    return build_unified_opportunity_report(
        {"all_discovered_candidates": list(candidates)},
        generated_at=_GENERATED_AT,
    )


def test_confirmed_active_candidate_becomes_qualified_record():
    report = _build(_candidate())

    assert report["record_count"] == 1
    assert report["records"][0]["evaluation_status"] == "QUALIFIED"
    assert report["records"][0]["workflow_status"] == "QUALIFIED_OPPORTUNITY"
    assert report["records"][0]["quantity"] == 8


def test_requires_verification_candidate_is_preserved():
    report = _build(
        _candidate(
            opportunity_state="STRONG_LEAD_REQUIRES_VERIFICATION",
            listing_status="UNKNOWN",
            top5_eligible=False,
            analysis_eligible=False,
            verification=[],
        )
    )

    assert report["records"][0]["evaluation_status"] == "REQUIRES_VERIFICATION"
    assert report["records"][0]["workflow_status"] == "REQUIRES_VERIFICATION"


def test_ended_candidate_becomes_closed_record():
    report = _build(
        _candidate(
            opportunity_state="STRONG_LEAD_REQUIRES_VERIFICATION",
            listing_status="ENDED",
            top5_eligible=False,
            analysis_eligible=False,
        )
    )

    assert report["records"][0]["listing_status"] == "ENDED"
    assert report["records"][0]["workflow_status"] == "CLOSED"


def test_rejected_candidate_becomes_rejected_record():
    report = _build(
        _candidate(
            opportunity_state="REJECTED_NOISE",
            listing_status="UNKNOWN",
            top5_eligible=False,
            analysis_eligible=False,
            verification=[],
        )
    )

    assert report["records"][0]["evaluation_status"] == "REJECTED"
    assert report["records"][0]["workflow_status"] == "REJECTED"


def test_missing_identity_is_a_structured_conversion_error():
    report = _build(_candidate(opportunity_identity=None))

    assert report["record_count"] == 0
    assert report["conversion_error_count"] == 1
    assert report["conversion_errors"][0]["title"] == _candidate()["title"]
    assert report["conversion_errors"][0]["source_url"] == _SOURCE_URL
    assert report["conversion_errors"][0]["opportunity_identity"] is None
    assert "ValidationError" in report["conversion_errors"][0]["reason"]


def test_missing_source_url_is_a_structured_conversion_error():
    report = _build(_candidate(source_urls=[]))

    assert report["record_count"] == 0
    assert report["conversion_error_count"] == 1
    assert report["conversion_errors"][0]["source_url"] is None
    assert "source URL" in report["conversion_errors"][0]["reason"]


def test_invalid_candidate_does_not_prevent_valid_records():
    report = _build(_candidate(opportunity_identity=None), _candidate())

    assert report["record_count"] == 1
    assert report["conversion_error_count"] == 1
    assert report["records"][0]["opportunity_id"] == "url-id:557914"


def test_report_counts_match_records_and_errors():
    report = _build(
        _candidate(),
        _candidate(
            opportunity_identity="url-id:second",
            title="Second opportunity",
        ),
        _candidate(source_urls=[]),
    )

    assert report["record_count"] == len(report["records"]) == 2
    assert report["conversion_error_count"] == len(report["conversion_errors"]) == 1


def test_serialization_is_deterministic_for_fixed_input_and_timestamp():
    first = _build(_candidate())
    second = _build(_candidate())

    assert serialize_unified_opportunity_report(first) == serialize_unified_opportunity_report(second)
    assert first["generated_at"] == "2026-08-01T00:00:00Z"


def test_building_unified_report_does_not_mutate_existing_discovery_output():
    discovery_result = {
        "search_run_report": {"status": "SUCCESS", "top5_count": 1},
        "all_discovered_candidates": [_candidate()],
        "discovery_top5": [_candidate()],
    }
    original = deepcopy(discovery_result)

    build_unified_opportunity_report(discovery_result, generated_at=_GENERATED_AT)

    assert discovery_result == original


def test_writer_creates_separate_canonical_json_artifact(tmp_path):
    path = write_unified_opportunity_report(
        {"all_discovered_candidates": [_candidate()]},
        tmp_path,
        generated_at=_GENERATED_AT,
    )

    assert path.name == "unified-opportunity-report.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0"
    assert payload["record_count"] == 1
