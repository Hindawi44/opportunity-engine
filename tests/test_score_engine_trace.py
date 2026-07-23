from opportunity_engine.score_engine_trace import ScoreEngineTraceAuditor


def test_trace_parses_dashboard_score_breakdown():
    payload = {"rows": [{
        "opportunity_id": "opp-1",
        "title": "Office chairs",
        "score": 59,
        "decision": "monitor",
        "score_breakdown": [
            "financial=0.0/40",
            "confidence=5.0/15",
            "data_quality=15.0/15",
            "resale=13.0/15",
            "logistics=12.0/15",
            "evidence_gap_penalty=3.0",
            "warning_penalty=1.0",
            "risk_penalty=4.0",
        ],
    }]}

    report = ScoreEngineTraceAuditor().audit_payload(payload)
    record = report.records[0]

    assert report.scoring_function_called_count == 1
    assert report.breakdown_serialized_count == 1
    assert record.parsed_components["data_quality"] == 15.0
    assert record.component_sum_before_penalty == 45.0
    assert record.calculated_raw_score == 41.0
    assert record.trace_stage == "dataset_serialization"


def test_trace_identifies_projection_loss_when_only_total_survives():
    report = ScoreEngineTraceAuditor().audit_payload({"rows": [{
        "opportunity_id": "opp-2",
        "score": 16,
        "decision": "monitor",
    }]})

    record = report.records[0]
    assert report.scoring_function_called_count == 1
    assert report.missing_breakdown_count == 1
    assert record.trace_stage == "dashboard_projection"
    assert "score_engine_likely_called_but_details_dropped_in_projection" in record.diagnosis


def test_trace_supports_explicit_score_components():
    report = ScoreEngineTraceAuditor().audit_payload({"opportunities": [{
        "id": "opp-3",
        "opportunity_score": 30,
        "decision": "reject",
        "score_components": {
            "financial": 0,
            "confidence": 5,
            "data_quality": 10,
            "resale": 8,
            "logistics": 10,
            "risk_penalty": 3,
        },
    }]})

    record = report.records[0]
    assert record.component_sum_before_penalty == 33.0
    assert record.calculated_raw_score == 30.0
    assert record.cap_expected == 39.0
    assert record.cap_applied is False
