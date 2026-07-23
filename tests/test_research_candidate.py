from opportunity_engine.research_candidate import PreliminaryResearchCandidateScorer


def test_selects_only_top_eligible_candidates() -> None:
    payload = [
        {
            "opportunity_id": "a",
            "title": "Parti med nye varer",
            "source_url": "https://example.test/a",
            "location": "Namsos",
            "price": 1000,
            "score": 19,
            "score_breakdown": [
                "data_quality=10.0/15",
                "resale=15.0/15",
                "logistics=15.0/15",
                "warning_penalty=0.0",
                "risk_penalty=0.0",
            ],
        },
        {
            "opportunity_id": "b",
            "title": "Nytt lagerparti",
            "source_url": "https://example.test/b",
            "location": "Trondheim",
            "price": 2000,
            "score": 18,
            "score_breakdown": [
                "data_quality=8.0/15",
                "resale=12.0/15",
                "logistics=12.0/15",
                "warning_penalty=0.0",
                "risk_penalty=3.0",
            ],
        },
        {
            "opportunity_id": "c",
            "title": "Gravemaskin med motor",
            "source_url": "https://example.test/c",
            "score": 20,
            "score_breakdown": [
                "data_quality=10.0/15",
                "resale=15.0/15",
                "logistics=5.0/15",
                "warning_penalty=3.0",
                "risk_penalty=9.0",
            ],
        },
    ]

    report = PreliminaryResearchCandidateScorer(threshold=25, selection_limit=2).evaluate_payload(payload)

    assert report.record_count == 3
    assert report.selected_count == 2
    assert [record.opportunity_id for record in report.records[:2]] == ["a", "b"]
    assert all(record.selected_for_external_research for record in report.records[:2])
    assert report.records[2].research_eligible is False
    assert "heavy_or_complex_asset" in report.records[2].research_reasons


def test_final_investment_score_remains_separate() -> None:
    payload = [{
        "opportunity_id": "x",
        "title": "Lett omsettelig vareparti",
        "source_url": "https://example.test/x",
        "location": "Namsos",
        "price": 500,
        "score": 17,
        "score_breakdown": [
            "data_quality=10.0/15",
            "resale=15.0/15",
            "logistics=15.0/15",
            "warning_penalty=0.0",
            "risk_penalty=0.0",
        ],
    }]

    record = PreliminaryResearchCandidateScorer(threshold=25, selection_limit=1).evaluate_payload(payload).records[0]

    assert record.research_eligible is True
    assert record.final_investment_score == 17.0
    assert record.final_investment_threshold == 60.0
    assert record.research_candidate_score != record.final_investment_score
