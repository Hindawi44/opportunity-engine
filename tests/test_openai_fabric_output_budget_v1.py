from __future__ import annotations

import json

from opportunity_engine.discovery.openai_fabric_procurement_advisor import (
    MAX_OUTPUT_TOKENS,
    run_openai_fabric_procurement_advisor,
)


class BudgetProbeClient:
    def __init__(self) -> None:
        self.calls = []

    def create_structured_response(self, **kwargs):
        self.calls.append(kwargs)
        supplied = json.loads(kwargs["input_text"])["fabric_procurement_candidates"]
        return (
            {
                "assessments": [
                    {
                        "candidate_id": item["candidate_id"],
                        "review_priority": "MEDIUM",
                        "material_summary": "Stock fabric candidate.",
                        "source_facts": ["Supplier page mentions stock fabric."],
                        "missing_information": ["price", "MOQ"],
                        "operator_questions": ["What is the MOQ?"],
                        "norway_import_checks": ["Confirm delivered cost to Norway."],
                        "reason": "Commercial terms require verification.",
                        "confidence": 0.7,
                    }
                    for item in supplied
                ],
                "overall_note": "Manual verification required.",
            },
            {"input_tokens": 500, "output_tokens": 700, "total_tokens": 1200},
        )


def test_fabric_advisor_has_room_for_seven_structured_assessments() -> None:
    report = {
        "candidates": [
            {
                "candidate_id": f"candidate-{index}",
                "source_id": f"supplier-{index}",
                "source_name": f"Supplier {index}",
                "source_country": "IT",
                "title": f"Fabric stock {index}",
                "source_url": f"https://example.com/{index}",
                "procurement_relevance_score": 80 - index,
            }
            for index in range(7)
        ]
    }
    client = BudgetProbeClient()

    result = run_openai_fabric_procurement_advisor(
        report,
        environment={"OPENAI_FABRIC_ADVISOR_MAX_CANDIDATES": "7"},
        client=client,
    )

    assert result["status"] == "SUCCESS"
    assert result["selected_candidate_count"] == 7
    assert result["assessment_count"] == 7
    assert result["api_request_count"] == 1
    assert len(client.calls) == 1
    assert MAX_OUTPUT_TOKENS == 3600
    assert client.calls[0]["max_output_tokens"] == 3600
    assert "Keep every field concise" in client.calls[0]["instructions"]
    assert result["automatic_purchase"] is False
