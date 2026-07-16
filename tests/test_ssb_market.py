from opportunity_engine.ods import SSBMarketEvidenceService


def test_market_evidence_normalizes_official_table_payloads() -> None:
    info = {
        "label": "Wholesale and retail trade principal figures",
        "firstPeriod": "2017",
        "lastPeriod": "2024",
        "variableNames": ["contents", "year", "industry"],
    }
    data = {"value": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]}

    evidence = SSBMarketEvidenceService.from_payloads(info, data)

    assert evidence.table_id == "12938"
    assert evidence.last_period == "2024"
    assert evidence.value_count == 10
    assert evidence.evidence_score == 100
    assert evidence.source_url.endswith("/12938")
    assert evidence.interpretation


def test_market_evidence_handles_metadata_only_payload() -> None:
    evidence = SSBMarketEvidenceService.from_payloads(
        {"title": "Retail table", "variableNames": []},
        {},
    )

    assert evidence.title == "Retail table"
    assert evidence.value_count == 0
    assert evidence.evidence_score == 50
