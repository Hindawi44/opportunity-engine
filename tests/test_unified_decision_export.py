import json
from pathlib import Path
import sys

import pytest

from scripts.build_unified_opportunity_contracts import main as export_main
from opportunity_engine.discovery.unified_decision_export import (
    EXPORT_SCHEMA_VERSION,
    build_unified_decision_export,
)
from opportunity_engine.discovery.unified_opportunity_contract import (
    SCHEMA_VERSION,
    UnifiedOpportunityContractError,
    UnifiedOpportunityContractV1,
)


ROOT = Path(__file__).resolve().parents[1]


def _decision_record(**overrides):
    record = {
        "opportunity_id": "unified-auksjonen-123",
        "url": "https://www.auksjonen.no/auksjon/torget/example/123",
        "title": "Example opportunity",
        "city": "Namsos",
        "asking_price_nok": 10_000.0,
        "conservative_resale_value_nok": None,
        "total_cost_nok": None,
        "expected_profit_nok": None,
        "roi_percent": None,
        "maximum_safe_bid_nok": None,
        "target_profit_buffer_nok": None,
        "verified_operating_costs_nok": None,
        "decision_confidence": "LOW",
        "decision": "EVIDENCE_REQUIRED",
        "final_decision": "WATCH",
        "recommendation": "WATCH",
        "official_decision_field": "final_decision",
        "opportunity_score": 34.59,
        "relevance_score": 37,
        "score_grade": "E",
        "score_components": {"evidence": 0.0},
        "missing_evidence": ["transport_cost_nok"],
        "evidence_needed": ["transport_cost"],
        "reasons": ["target:lagerreol+15"],
        "score_reasons": ["evidence_gate:EVIDENCE_REQUIRED"],
        "decision_reasons_ar": ["البيانات الاقتصادية غير مكتملة."],
        "decision_warnings_ar": ["أدلة ناقصة: تكلفة النقل"],
        "next_actions_ar": ["توثيق تكلفة النقل."],
        "exclusion_reasons": [],
        "automatic_purchase": False,
    }
    record.update(overrides)
    return record


def test_official_watch_record_adapts_without_recomputing_decision_or_score() -> None:
    record = _decision_record()

    payload = UnifiedOpportunityContractV1.from_decision_intelligence_record(
        record
    ).to_dict()

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["final_decision"] == record["final_decision"]
    assert payload["risk"]["opportunity_score"] == record["opportunity_score"]
    assert payload["commercial_status"] == "WATCH"
    assert payload["verification_status"] == "REQUIRES_VERIFICATION"
    assert payload["listing_status"] == "UNKNOWN"
    assert payload["source"]["name"] == "auksjonen.no"
    assert payload["automatic_purchase_decision"] is False
    assert "transport_cost_nok" in payload["missing_information"]


def test_official_buy_review_maps_to_qualified_only_after_verified_decision() -> None:
    record = _decision_record(
        final_decision="BUY_REVIEW",
        recommendation="BUY_REVIEW",
        decision_confidence="HIGH",
        missing_evidence=[],
        evidence_needed=[],
        expected_profit_nok=8_000.0,
        roi_percent=66.67,
    )

    payload = UnifiedOpportunityContractV1.from_decision_intelligence_record(
        record
    ).to_dict()

    assert payload["final_decision"] == "BUY_REVIEW"
    assert payload["commercial_status"] == "QUALIFIED"
    assert payload["verification_status"] == "VERIFIED"


def test_export_rejects_legacy_recommendation_contradiction() -> None:
    payload = {
        "decision_count": 1,
        "decisions": [_decision_record(recommendation="REJECT")],
    }

    with pytest.raises(
        UnifiedOpportunityContractError,
        match="legacy recommendation contradicts final_decision",
    ):
        build_unified_decision_export(payload)


def test_current_decision_intelligence_exports_without_decision_score_or_count_drift() -> None:
    decision_payload = json.loads(
        (ROOT / "data" / "decision_intelligence.json").read_text(encoding="utf-8")
    )

    export_payload = build_unified_decision_export(decision_payload)

    assert export_payload["schema_version"] == EXPORT_SCHEMA_VERSION
    assert export_payload["opportunity_count"] == decision_payload["decision_count"]
    assert len(export_payload["contracts"]) == len(decision_payload["decisions"])

    for source_record, contract in zip(
        decision_payload["decisions"], export_payload["contracts"], strict=True
    ):
        assert contract["opportunity_id"] == source_record["opportunity_id"]
        assert contract["final_decision"] == source_record["final_decision"]
        assert contract["risk"]["opportunity_score"] == source_record[
            "opportunity_score"
        ]
        assert contract["risk"]["top5_eligible"] == source_record.get(
            "top5_eligible"
        )
        assert contract["risk"]["analysis_eligible"] == source_record.get(
            "analysis_eligible"
        )
        assert contract["automatic_purchase_decision"] is False


def test_export_cli_writes_a_deterministic_sidecar(tmp_path, monkeypatch) -> None:
    decisions_path = tmp_path / "decision_intelligence.json"
    output_path = tmp_path / "unified_opportunities_v1.json"
    decision_payload = {
        "schema_version": 2,
        "generated_at": "2026-07-31T09:00:00+00:00",
        "official_decision_field": "final_decision",
        "decision_count": 1,
        "decisions": [_decision_record()],
    }
    decisions_path.write_text(
        json.dumps(decision_payload, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_unified_opportunity_contracts.py",
            "--decisions",
            str(decisions_path),
            "--output",
            str(output_path),
            "--market",
            "NO",
        ],
    )

    assert export_main() == 0
    exported = json.loads(output_path.read_text(encoding="utf-8"))
    assert exported["opportunity_count"] == 1
    assert exported["source_generated_at"] == decision_payload["generated_at"]
    assert exported["contracts"][0]["final_decision"] == "WATCH"
