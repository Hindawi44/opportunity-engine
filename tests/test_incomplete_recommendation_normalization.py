from scripts.normalize_incomplete_recommendations import (
    normalize_scored_payload,
    normalize_summary_payload,
)


def test_incomplete_financial_evidence_is_not_labeled_reject() -> None:
    payload = {
        "opportunities": [
            {
                "opportunity_id": "opp-1",
                "decision": "EVIDENCE_REQUIRED",
                "recommendation": "REJECT",
                "opportunity_score": 18.98,
            }
        ]
    }

    normalized = normalize_scored_payload(payload)
    item = normalized["opportunities"][0]

    assert item["recommendation"] == "EVIDENCE_REQUIRED"
    assert item["recommendation_ar"] == "يحتاج أدلة"
    assert item["score_status"] == "PRELIMINARY"
    assert normalized["evidence_required_count"] == 1
    assert normalized["reject_count"] == 0


def test_completed_negative_economics_remains_reject() -> None:
    payload = {
        "records": [
            {
                "opportunity_id": "opp-2",
                "decision": "REVIEW_NUMBERS",
                "recommendation": "REJECT",
                "expected_profit_nok": -1000,
            }
        ]
    }

    normalized = normalize_summary_payload(payload)
    item = normalized["records"][0]

    assert item["recommendation"] == "REJECT"
    assert item["score_status"] == "FINAL"
    assert normalized["economic_reject_count"] == 1
    assert normalized["evidence_required_count"] == 0
