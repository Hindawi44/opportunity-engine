from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from mind_forge.contracts_v1 import EvidenceClassification, EvidenceStance, TopicInput
from mind_forge.creative_engine_v1 import generate_ideas
from mind_forge.critique_engine_v1 import critique_survivors
from mind_forge.expert_minds_v1 import evaluate_with_expert_minds
from mind_forge.live_research_adapter_v1 import (
    FakeResearchExecutor,
    RawResearchHit,
    ResearchAdapterKind,
    ResearchPolicy,
    assert_live_research_access,
    execute_research_requests,
)
from mind_forge.logic_engine_v1 import evaluate_logic
from mind_forge.research_evidence_v1 import (
    EvidenceObservation,
    EvidenceObservationOrigin,
    ResearchRequest,
    ResearchRoute,
    ResearchRouterResult,
    build_evidence,
    route_research,
)


def _router():
    topic = TopicInput(topic="تصليح الملابس")
    creative = generate_ideas(topic)
    experts = evaluate_with_expert_minds(creative)
    logic = evaluate_logic(topic, creative, experts)
    critique = critique_survivors(creative, logic)
    return route_research(creative, logic, critique)


def _hit(
    *,
    suffix: str,
    source_type: str = "primary market data",
    stance: EvidenceStance = EvidenceStance.SUPPORTS,
    confidence: float = 0.85,
):
    return RawResearchHit(
        source=f"Source {suffix}",
        source_type=source_type,
        source_ref=f"https://example.test/{suffix}",
        excerpt=f"Sourced observation {suffix}.",
        stance=stance,
        confidence=confidence,
    )


def _single_router(request: ResearchRequest) -> ResearchRouterResult:
    return ResearchRouterResult(
        candidate_idea_ids=[request.idea_id],
        requests=[request],
        external_request_ids=[request.request_id],
        experiment_request_ids=[],
        user_request_ids=[],
        max_requests_per_idea=1,
    )


def test_research_policy_is_disabled_by_default_and_has_separate_budget():
    policy = ResearchPolicy()
    assert policy.enabled is False
    assert policy.max_search_operations == 4
    assert policy.max_operations_per_request == 2
    assert policy.max_estimated_cost_usd == 0.05
    assert policy.estimated_cost_per_search_usd == 0.01


def test_even_fake_research_requires_explicit_policy_opt_in():
    with pytest.raises(RuntimeError, match="policy is disabled"):
        execute_research_requests(
            _router(),
            executor=FakeResearchExecutor(),
        )


def test_live_access_requires_explicit_flag_and_existing_key(monkeypatch):
    policy = ResearchPolicy(enabled=True)
    monkeypatch.delenv("MIND_FORGE_LIVE_RESEARCH_ENABLED", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="MIND_FORGE_LIVE_RESEARCH_ENABLED"):
        assert_live_research_access(policy)

    monkeypatch.setenv("MIND_FORGE_LIVE_RESEARCH_ENABLED", "1")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        assert_live_research_access(policy)


def test_fake_executor_runs_router_external_requests_offline_and_emits_observations_only():
    router = _router()
    external = [
        request for request in router.requests
        if request.request_id in set(router.external_request_ids)
    ]
    hits = {
        request.request_id: [_hit(suffix=str(index))]
        for index, request in enumerate(external, start=1)
    }
    result = execute_research_requests(
        router,
        policy=ResearchPolicy(enabled=True),
        executor=FakeResearchExecutor(hits),
    )

    assert result.live_executor_used is False
    assert result.live_research_enabled is True
    assert len(result.executed_request_ids) == len(external) == 2
    assert result.usage.search_operations == 2
    assert result.usage.search_operations <= 4
    assert result.usage.estimated_cost_usd == 0.02
    assert len(result.observations) == 2
    assert all(item.origin is EvidenceObservationOrigin.LIVE_RESEARCH for item in result.observations)
    assert all(item.classification is None for item in result.observations)
    assert all(item.source and item.source_type and item.source_ref for item in result.observations)


def test_live_research_observation_cannot_assign_verified_fact_directly():
    with pytest.raises(ValidationError, match="cannot assign final evidence classification"):
        EvidenceObservation(
            request_id="research-x",
            origin=EvidenceObservationOrigin.LIVE_RESEARCH,
            source="Source",
            source_type="primary market data",
            source_ref="https://example.test/source",
            observation_text="Observed source text.",
            classification=EvidenceClassification.VERIFIED_FACT,
            stance=EvidenceStance.SUPPORTS,
            confidence=0.9,
        )


def test_evidence_engine_alone_can_upgrade_sourced_live_observation_to_strong_never_verified():
    router = _router()
    request = next(item for item in router.requests if item.route is ResearchRoute.WEB)
    result = execute_research_requests(
        _single_router(request),
        policy=ResearchPolicy(enabled=True, max_search_operations=2),
        executor=FakeResearchExecutor(
            {request.request_id: [_hit(suffix="strong", source_type="primary market data")]}
        ),
    )
    evidence = build_evidence(_single_router(request), result.observations)

    item = evidence.evidence[0]
    assert item.classification is EvidenceClassification.STRONG_EVIDENCE
    assert item.classification is not EvidenceClassification.VERIFIED_FACT
    assert item.source == "Source strong"
    assert item.source_type == "primary market data"
    assert item.source_ref == "https://example.test/strong"
    assert request.request_id in evidence.resolved_request_ids


def test_source_disagreement_remains_conflicting_and_unresolved():
    router = _router()
    request = next(item for item in router.requests if item.route is ResearchRoute.WEB)
    one = _hit(
        suffix="support",
        source_type="primary market data",
        stance=EvidenceStance.SUPPORTS,
    )
    two = _hit(
        suffix="refute",
        source_type="primary market data",
        stance=EvidenceStance.REFUTES,
    )
    research = execute_research_requests(
        _single_router(request),
        policy=ResearchPolicy(enabled=True, max_search_operations=2),
        executor=FakeResearchExecutor({request.request_id: [one, two]}),
    )
    evidence = build_evidence(_single_router(request), research.observations)

    assert request.claim_id in evidence.conflicting_claim_ids
    assert request.request_id in evidence.unresolved_request_ids
    assert all(
        item.classification is EvidenceClassification.CONFLICTING_EVIDENCE
        for item in evidence.evidence
    )
    assert all(item.source and item.source_type and item.source_ref for item in evidence.evidence)


def test_research_budget_gate_stops_before_second_request_when_operation_cap_is_one():
    router = _router()
    external = [
        request for request in router.requests
        if request.request_id in set(router.external_request_ids)
    ]
    hits = {
        request.request_id: [_hit(suffix=str(index))]
        for index, request in enumerate(external, start=1)
    }
    with pytest.raises(RuntimeError, match="search-operation budget"):
        execute_research_requests(
            router,
            policy=ResearchPolicy(
                enabled=True,
                max_search_operations=1,
                max_operations_per_request=1,
                max_estimated_cost_usd=0.05,
            ),
            executor=FakeResearchExecutor(hits),
        )


def test_public_data_route_uses_public_data_adapter():
    request = ResearchRequest(
        request_id="research-public",
        claim_id="claim-public",
        idea_id="idea-public",
        claim_text="Official data may show material local demand.",
        why_material="This public fact changes whether the idea should proceed.",
        route=ResearchRoute.PUBLIC_DATA,
        expected_decision_impact=0.9,
        acceptable_source_types=["official statistics", "primary public dataset"],
    )
    result = execute_research_requests(
        _single_router(request),
        policy=ResearchPolicy(enabled=True, max_search_operations=2),
        executor=FakeResearchExecutor(
            {
                request.request_id: [
                    _hit(
                        suffix="public",
                        source_type="primary public dataset",
                        stance=EvidenceStance.NEUTRAL,
                    )
                ]
            }
        ),
    )
    assert result.adapter_by_request[request.request_id] is ResearchAdapterKind.PUBLIC_DATA


def test_maps_places_specialization_is_available_without_new_router_enum():
    request = ResearchRequest(
        request_id="research-place",
        claim_id="claim-place",
        idea_id="idea-place",
        claim_text="Relevant businesses may exist in the target location.",
        why_material="Local place availability changes the distribution decision.",
        route=ResearchRoute.WEB,
        expected_decision_impact=0.8,
        acceptable_source_types=["maps/place listing", "location listing"],
    )
    result = execute_research_requests(
        _single_router(request),
        policy=ResearchPolicy(enabled=True, max_search_operations=2),
        executor=FakeResearchExecutor(
            {
                request.request_id: [
                    _hit(
                        suffix="place",
                        source_type="maps/place listing",
                        stance=EvidenceStance.NEUTRAL,
                    )
                ]
            }
        ),
    )
    assert result.adapter_by_request[request.request_id] is ResearchAdapterKind.MAPS_PLACES


def test_live_research_workflow_is_manual_only_default_no_and_reuses_existing_secret():
    text = Path(".github/workflows/mind-forge-live-research-v1.yaml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "confirm_paid_live_research:" in text
    assert 'default: "NO"' in text
    assert "if: ${{ inputs.confirm_paid_live_research == 'YES' }}" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "\n  schedule:" not in text
    assert "OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}" in text
    assert "MIND_FORGE_LIVE_RESEARCH_ENABLED: \"1\"" in text
    assert "sk-" not in text
