from opportunity_engine.real_opportunity_validation import RealOpportunityValidator


def test_real_dataset_validation_counts_kpis_and_duplicates():
    payload = {
        "opportunities": [
            {
                "opportunity_id": "opp-1",
                "title": "Office furniture lot",
                "source": "auksjonen",
                "source_url": "https://example.test/1",
                "price_nok": 1000,
                "score": 82,
                "accepted_comparables": [{"price_nok": 2200}, {"price_nok": 2400}],
                "potential_buyers": [{"name": "Buyer A"}],
                "evidence": ["e1", "e2"],
                "scenarios": [{"id": "brokerage"}],
                "best_scenario": "brokerage",
            },
            {
                "opportunity_id": "opp-1",
                "title": "Duplicate row",
                "source_url": "https://example.test/duplicate",
                "score": 40,
            },
        ]
    }

    report = RealOpportunityValidator().validate_payload(payload)

    assert report.kpis.opportunities_discovered == 2
    assert report.kpis.unique_opportunities == 1
    assert report.kpis.duplicates_detected == 1
    assert report.kpis.external_research_eligible == 1
    assert report.kpis.blocked_below_score == 1
    assert report.kpis.accepted_comparables == 2
    assert report.kpis.potential_buyers == 1
    assert report.kpis.opportunities_with_best_scenario == 1
    assert report.kpis.average_internal_score == 61.0
    assert report.records[0].pipeline_stage_reached == "best_scenario"
    assert report.records[1].eligibility_reason == "internal_score_below_threshold"
    assert report.records[1].blocked_before == "external_research"


def test_missing_values_remain_missing_and_are_reported():
    report = RealOpportunityValidator().validate_payload({"rows": [{"name": "Unknown lot"}]})

    record = report.records[0]
    assert record.internal_score is None
    assert record.eligibility_reason == "missing_internal_score"
    assert record.required_score == 60.0
    assert record.pipeline_stage_reached == "eligibility"
    assert record.comparable_count == 0
    assert record.buyer_count == 0
    assert "opportunity_id" in record.missing_fields
    assert "source_url" in record.missing_fields
    assert report.kpis.blocked_missing_score == 1
    assert report.kpis.price_coverage_rate == 0.0
    assert report.warnings


def test_explicit_external_eligibility_overrides_score_threshold():
    report = RealOpportunityValidator(external_research_score_threshold=90).validate_payload(
        [{
            "id": "opp-2",
            "title": "Retail stock",
            "url": "https://example.test/2",
            "score": 20,
            "external_research_eligible": True,
        }]
    )

    record = report.records[0]
    assert report.kpis.external_research_eligible == 1
    assert record.eligibility_reason == "explicitly_eligible"
    assert record.required_score == 90
    assert record.blocked_before == "external_research_results"


def test_external_results_without_evidence_are_traced():
    report = RealOpportunityValidator().validate_payload([
        {
            "id": "opp-3",
            "title": "Equipment lot",
            "url": "https://example.test/3",
            "score": 75,
            "comparables": [{"price": 1000}],
            "buyers": [{"name": "Buyer"}],
        }
    ])

    record = report.records[0]
    assert record.pipeline_stage_reached == "external_research"
    assert record.blocked_before == "evidence_persistence"
    assert report.kpis.reached_external_research == 1
    assert report.kpis.reached_evidence == 0


def test_empty_dataset_produces_zero_rates_without_failure():
    report = RealOpportunityValidator().validate_payload({"opportunities": []})

    assert report.kpis.opportunities_discovered == 0
    assert report.kpis.average_internal_score is None
    assert report.kpis.source_coverage_rate == 0.0
    assert "No opportunity rows" in report.warnings[0]
