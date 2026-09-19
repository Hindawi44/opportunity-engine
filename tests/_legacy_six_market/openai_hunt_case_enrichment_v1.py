from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.discovery.openai_hunt_case_enrichment import (
    OpenAIResponsesHTTPClient,
    attach_hunt_case_intelligence,
    render_openai_hunt_case_enrichment,
    run_openai_hunt_case_enrichment,
    select_hunt_signals,
)


def _signal(index: int, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "signal_id": f"signal:{index}",
        "signal_type": "BUSINESS_CLOSURE",
        "value": f"Example clothing business closure {index}",
        "source": f"Source {index % 3}",
        "observed_at": "2026-08-05T10:00:00Z",
        "confidence": 0.7,
        "source_country": "NO",
        "source_url": f"https://example.test/signals/{index}",
        "title": f"Example Fashion AS closes branch {index}",
        "company_name": "Example Fashion AS",
        "seller_name": None,
        "location": "Trondheim",
        "first_observed_at": "2026-08-05T10:00:00Z",
        "latest_observed_at": "2026-08-05T10:00:00Z",
        "event_date": None,
        "evidence": [],
        "related_opportunity_id": None,
        "status": "WATCH",
        "metadata": {"signal_only": True},
    }
    payload.update(overrides)
    return payload


def _brief(signal_count: int = 2) -> dict[str, Any]:
    signals = [_signal(index) for index in range(signal_count)]
    return {
        "generated_at": "2026-08-05T10:00:00Z",
        "new_signals_today": signals[:1],
        "changed_signals_since_previous_checkpoint": signals[1:2],
        "early_signals_to_watch": signals,
        "counts": {"early_signals_to_watch": len(signals)},
        "selected_human_action": {
            "action": "NO_IMMEDIATE_ACTION",
            "reason": "No direct opportunity.",
        },
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def create_structured_response(
        self,
        *,
        model: str,
        instructions: str,
        input_text: str,
        schema_name: str,
        schema: Mapping[str, Any],
        reasoning_effort: str,
        max_output_tokens: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        self.calls.append(
            {
                "model": model,
                "instructions": instructions,
                "input_text": input_text,
                "schema_name": schema_name,
                "schema": schema,
                "reasoning_effort": reasoning_effort,
                "max_output_tokens": max_output_tokens,
            }
        )
        if schema_name == "market_hunt_case_triage":
            return (
                {
                    "cases": [
                        {
                            "case_title": "Example Fashion closure and inventory watch",
                            "market_code": "NO",
                            "normalized_company_name": "Example Fashion AS",
                            "organisation_number": "",
                            "signal_ids": ["signal:0", "signal:1"],
                            "connection_basis": ["same company and location"],
                            "inventory_likelihood": "HIGH",
                            "sale_channel_likelihood": "MEDIUM",
                            "missing_information": ["liquidator", "sale channel"],
                            "next_hunt_action": "FIND_SALE_CHANNEL",
                            "reason": "Two independent closure signals refer to the same company.",
                            "confidence": 0.91,
                        }
                    ],
                    "unassigned_signal_ids": [],
                },
                {"input_tokens": 500, "output_tokens": 250, "total_tokens": 750},
            )
        return (
            {
                "case_summary": "The company is closing and inventory may later be released.",
                "inventory_hypothesis": "Clothing stock may be consolidated before sale.",
                "likely_sale_channels": ["public auction", "liquidator sale"],
                "targeted_search_queries": [
                    '"Example Fashion AS" konkursbo varelager',
                    '"Example Fashion AS" auksjon klær',
                ],
                "missing_information": ["organisation number", "liquidator"],
                "recommended_next_action": "FIND_SALE_CHANNEL",
                "reasoning_summary": "The evidence supports monitoring, not a sale claim.",
                "confidence": 0.82,
                "requires_external_verification": False,
            },
            {"input_tokens": 600, "output_tokens": 300, "total_tokens": 900},
        )


def test_missing_key_skips_without_api_call() -> None:
    report = run_openai_hunt_case_enrichment(_brief(), environment={})
    assert report["status"] == "SKIPPED_NO_API_KEY"
    assert report["api_request_count"] == 0
    assert report["automatic_purchase"] is False


def test_no_eligible_signals_is_truthful_zero() -> None:
    report = run_openai_hunt_case_enrichment(
        {"generated_at": "2026-08-05T10:00:00Z", "early_signals_to_watch": []},
        environment={},
        client=FakeClient(),
    )
    assert report["status"] == "NO_ELIGIBLE_SIGNALS"
    assert report["cases"] == []


def test_signal_selection_is_bounded_to_ten() -> None:
    brief = _brief(14)
    selected = select_hunt_signals(brief, max_signals=10)
    assert len(selected) == 10
    assert selected[0]["signal_id"] in {"signal:0", "signal:1"}


def test_luna_triage_and_terra_deep_analysis_are_bounded_and_advisory() -> None:
    client = FakeClient()
    report = run_openai_hunt_case_enrichment(
        _brief(),
        environment={
            "OPENAI_HUNT_TRIAGE_MODEL": "gpt-5.6-luna",
            "OPENAI_HUNT_DEEP_MODEL": "gpt-5.6-terra",
            "OPENAI_HUNT_MAX_SIGNALS": "10",
            "OPENAI_HUNT_MAX_DEEP_CASES": "2",
            "OPENAI_HUNT_MAX_API_REQUESTS": "3",
            "OPENAI_HUNT_MAX_ESTIMATED_COST_USD": "0.16",
        },
        client=client,
    )

    assert report["status"] == "SUCCESS"
    assert [call["model"] for call in client.calls] == [
        "gpt-5.6-luna",
        "gpt-5.6-terra",
    ]
    assert len(client.calls) <= 3
    assert client.calls[0]["reasoning_effort"] == "low"
    assert client.calls[1]["reasoning_effort"] == "medium"
    assert report["selected_signal_count"] == 2
    assert report["deep_case_count"] == 1
    case = report["cases"][0]
    assert case["link_verification"]["verified"] is True
    assert case["link_verification"]["method"] == "EXACT_LEGAL_NAME_AND_LOCATION"
    assert case["deep_analysis"]["requires_external_verification"] is True
    assert case["promotion_to_opportunity_allowed"] is False
    assert case["analysis_eligible"] is False
    assert case["top5_eligible"] is False
    assert report["automatic_contact"] is False
    assert report["automatic_bid"] is False
    assert report["automatic_purchase"] is False
    assert report["automatic_payment"] is False
    assert 0 < report["estimated_cost_usd"] < 0.16


def test_model_claimed_org_number_is_not_trusted_without_source_evidence() -> None:
    class ClaimedOrgClient(FakeClient):
        def create_structured_response(self, **kwargs):
            payload, usage = super().create_structured_response(**kwargs)
            if kwargs["schema_name"] == "market_hunt_case_triage":
                payload["cases"][0]["organisation_number"] = "999999999"
            return payload, usage

    report = run_openai_hunt_case_enrichment(
        _brief(), environment={}, client=ClaimedOrgClient()
    )
    case = report["cases"][0]
    assert case["organisation_number"] is None
    assert case["model_claimed_organisation_number"] == "999999999"
    assert case["model_claimed_organisation_number_verified"] is False


def test_attach_preserves_existing_single_human_action() -> None:
    report = run_openai_hunt_case_enrichment(
        _brief(), environment={}, client=FakeClient()
    )
    enriched = attach_hunt_case_intelligence(_brief(), report)
    assert enriched["selected_human_action"]["action"] == "NO_IMMEDIATE_ACTION"
    assert enriched["counts"]["hunt_cases"] == 1
    assert enriched["hunt_case_intelligence"]["promotion_to_opportunity_allowed"] is False


def test_rendered_artifact_exposes_queries_and_safety() -> None:
    report = run_openai_hunt_case_enrichment(
        _brief(), environment={}, client=FakeClient()
    )
    rendered = render_openai_hunt_case_enrichment(report)
    assert "قضايا المطاردة" in rendered
    assert '"Example Fashion AS" konkursbo varelager' in rendered
    assert "ليست إثباتًا لوجود بيع أو مخزون" in rendered
    assert "لا شراء، لا مزايدة، لا اتصال، ولا دفع تلقائي" in rendered


class FakeHTTPResponse:
    status_code = 200
    headers: dict[str, str] = {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": '{"cases":[],"unassigned_signal_ids":[]}'},
                    ],
                }
            ],
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        }


class FakeSession:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] | None = None

    def post(self, *args, **kwargs):
        self.kwargs = kwargs
        return FakeHTTPResponse()


def test_http_client_disables_storage_and_uses_strict_schema() -> None:
    session = FakeSession()
    client = OpenAIResponsesHTTPClient(api_key="test-key", session=session)
    client.create_structured_response(
        model="gpt-5.6-luna",
        instructions="bounded",
        input_text="{}",
        schema_name="market_hunt_case_triage",
        schema={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        reasoning_effort="low",
        max_output_tokens=100,
    )
    assert session.kwargs is not None
    payload = session.kwargs["json"]
    assert payload["store"] is False
    assert payload["text"]["format"]["type"] == "json_schema"
    assert payload["text"]["format"]["strict"] is True
    assert session.kwargs["headers"]["Authorization"] == "Bearer test-key"


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"
BUILD_SCRIPT = ROOT / "scripts/build_domain_market_intelligence_feed.py"


def test_checkpoint_workflow_injects_secret_and_bounded_models() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}" in text
    assert "OPENAI_HUNT_TRIAGE_MODEL: gpt-5.6-luna" in text
    assert "OPENAI_HUNT_DEEP_MODEL: gpt-5.6-terra" in text
    assert 'OPENAI_HUNT_MAX_SIGNALS: "10"' in text
    assert 'OPENAI_HUNT_MAX_DEEP_CASES: "2"' in text
    assert 'OPENAI_HUNT_MAX_API_REQUESTS: "3"' in text
    assert 'OPENAI_HUNT_MAX_ESTIMATED_COST_USD: "0.16"' in text
    assert "openai-hunt-case-enrichment.json" in text
    assert "promotion_to_opportunity_allowed" in text


def test_build_script_writes_and_attaches_hunt_case_artifacts() -> None:
    text = BUILD_SCRIPT.read_text(encoding="utf-8")
    assert "run_openai_hunt_case_enrichment" in text
    assert "write_openai_hunt_case_artifacts" in text
    assert "attach_hunt_case_intelligence" in text
    assert 'openai-hunt-case-enrichment.json' in text
    assert 'openai-hunt-case-enrichment.txt' in text
