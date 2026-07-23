from opportunity_engine.internal_score_audit import InternalScoreAuditor


def test_audit_explains_low_score_components_and_gap():
    report = InternalScoreAuditor(required_score=60).audit_payload({
        "opportunities": [{
            "opportunity_id": "opp-1",
            "title": "Garage equipment",
            "opportunity_score": 16,
            "decision": "EVIDENCE_REQUIRED",
            "missing_evidence": ["market_comparables", "transport_cost"],
            "score_components": {
                "verified_economics": 0,
                "evidence": 0,
                "marketability": 7,
                "logistics": 6,
                "listing_quality": 3,
            },
            "score_reasons": ["verified_economics:0/35", "evidence_gate:EVIDENCE_REQUIRED"],
        }]
    })

    record = report.records[0]
    assert record.total_score == 16
    assert record.component_total == 16
    assert record.score_gap == 44
    assert not record.eligible
    assert "no_verified_economics_points" in record.diagnosis
    assert "no_evidence_points" in record.diagnosis
    assert "upstream_evidence_gate_active" in record.diagnosis
    assert report.below_threshold_count == 1


def test_audit_detects_gate_cap_difference():
    report = InternalScoreAuditor().audit_payload([{
        "id": "opp-2",
        "score": 29,
        "decision": "REVIEW_NUMBERS",
        "score_components": {
            "verified_economics": 25,
            "evidence": 15,
            "marketability": 10,
            "logistics": 8,
            "listing_quality": 8,
        },
    }])

    record = report.records[0]
    assert record.component_total == 66
    assert "component_total_differs_from_final_score_due_to_gate_or_cap" in record.diagnosis
    assert report.component_mismatch_count == 1


def test_audit_preserves_missing_score_as_unknown():
    report = InternalScoreAuditor().audit_payload([{"id": "opp-3", "title": "Unknown"}])

    record = report.records[0]
    assert record.total_score is None
    assert record.score_gap is None
    assert "missing_total_score" in record.diagnosis
    assert report.missing_score_count == 1
