from __future__ import annotations

import pytest
from pydantic import ValidationError

from mind_forge.contracts_v1 import (
    EvidenceClassification,
    EvidenceStance,
    TopicInput,
)
from mind_forge.creative_engine_v1 import generate_ideas
from mind_forge.critique_engine_v1 import critique_survivors
from mind_forge.expert_minds_v1 import evaluate_with_expert_minds
from mind_forge.logic_engine_v1 import evaluate_logic
from mind_forge.question_generator_v1 import generate_questions
from mind_forge.research_evidence_v1 import (
    EvidenceObservation,
    EvidenceObservationOrigin,
    ResearchRoute,
    build_evidence,
    route_research,
)


def _pipeline():
    topic = TopicInput(topic="تصليح الملابس")
    questions = generate_questions(topic)
    creative = generate_ideas(topic, questions)
    experts = evaluate_with_expert_minds(creative)
    logic = evaluate_logic(topic, creative, experts)
    critique = critique_survivors(creative, logic)
    router = route_research(creative, logic, critique)
    return topic, questions, creative, experts, logic, critique, router


def test_router_only_routes_logic_survivors_and_keeps_one_request_budget() -> None:
    _, _, _, _, logic, critique, router = _pipeline()

    assert set(router.candidate_idea_ids) == set(logic.survivor_idea_ids)
    assert set(item.idea_id for item in router.requests).issubset(set(logic.survivor_idea_ids))
    assert len(router.requests) == len(critique.critiqued_idea_ids) == 6
    assert len({item.idea_id for item in router.requests}) == len(router.requests)
    assert router.max_requests_per_idea == 1
    assert all(item.expected_decision_impact >= 0.60 for item in router.requests)


def test_router_prefers_experiment_for_operational_uncertainty_and_web_for_market_claims() -> None:
    _, _, creative, _, _, _, router = _pipeline()
    families = creative.mechanism_family_by_idea_id
    request_by_family = {families[item.idea_id]: item for item in router.requests}

    assert request_by_family["bottleneck_redesign"].route is ResearchRoute.EXPERIMENT
    assert request_by_family["standardization"].route is ResearchRoute.EXPERIMENT
    assert request_by_family["automation_intake"].route is ResearchRoute.EXPERIMENT
    assert request_by_family["data_feedback"].route is ResearchRoute.EXPERIMENT
    assert request_by_family["premium_speed"].route is ResearchRoute.WEB
    assert request_by_family["adjacent_bundle"].route is ResearchRoute.WEB
    assert len(router.external_request_ids) == 2
    assert len(router.experiment_request_ids) == 4
    assert router.user_request_ids == []


def test_no_observation_never_becomes_fact_or_strong_evidence() -> None:
    _, _, _, _, _, _, router = _pipeline()
    result = build_evidence(router)

    assert len(result.evidence) == len(router.requests) == 6
    assert set(result.unresolved_request_ids) == {item.request_id for item in router.requests}
    assert result.resolved_request_ids == []
    classes = {item.classification for item in result.evidence}
    assert classes == {EvidenceClassification.ASSUMPTION, EvidenceClassification.UNKNOWN}
    assert all(item.source is None and item.source_type is None for item in result.evidence)


def test_sourced_strong_evidence_resolves_one_request() -> None:
    _, _, _, _, _, _, router = _pipeline()
    request = next(item for item in router.requests if item.route is ResearchRoute.WEB)
    observation = EvidenceObservation(
        request_id=request.request_id,
        source="Public source example",
        source_type="primary market data",
        source_ref="https://example.invalid/source",
        classification=EvidenceClassification.STRONG_EVIDENCE,
        stance=EvidenceStance.SUPPORTS,
        confidence=0.86,
    )

    result = build_evidence(router, [observation])
    evidence = next(item for item in result.evidence if item.claim_id == request.claim_id)
    assert request.request_id in result.resolved_request_ids
    assert evidence.classification is EvidenceClassification.STRONG_EVIDENCE
    assert evidence.source == "Public source example"
    assert evidence.source_type == "primary market data"


def test_live_neutral_observation_never_becomes_strong_even_with_high_confidence() -> None:
    _, _, _, _, _, _, router = _pipeline()
    request = next(item for item in router.requests if item.route is ResearchRoute.WEB)
    observation = EvidenceObservation(
        request_id=request.request_id,
        origin=EvidenceObservationOrigin.LIVE_RESEARCH,
        source="Irrelevant but well-formed source",
        source_type=request.acceptable_source_types[0],
        source_ref="https://example.invalid/neutral",
        observation_text="The page exists but does not support or refute the exact claim.",
        stance=EvidenceStance.NEUTRAL,
        confidence=0.99,
    )

    result = build_evidence(router, [observation])
    evidence = next(item for item in result.evidence if item.claim_id == request.claim_id)

    assert evidence.classification is EvidenceClassification.UNKNOWN
    assert evidence.stance is EvidenceStance.NEUTRAL
    assert evidence.confidence <= 0.50
    assert request.request_id in result.unresolved_request_ids
    assert request.request_id not in result.resolved_request_ids


def test_live_directional_observation_can_be_strong_only_when_source_fit_is_acceptable() -> None:
    _, _, _, _, _, _, router = _pipeline()
    request = next(item for item in router.requests if item.route is ResearchRoute.WEB)
    observation = EvidenceObservation(
        request_id=request.request_id,
        origin=EvidenceObservationOrigin.LIVE_RESEARCH,
        source="Primary market source",
        source_type=request.acceptable_source_types[0],
        source_ref="https://example.invalid/support",
        observation_text="This source directly supports the material claim.",
        stance=EvidenceStance.SUPPORTS,
        confidence=0.85,
    )

    result = build_evidence(router, [observation])
    evidence = next(item for item in result.evidence if item.claim_id == request.claim_id)

    assert evidence.classification is EvidenceClassification.STRONG_EVIDENCE
    assert request.request_id in result.resolved_request_ids


def test_strong_evidence_without_provenance_is_rejected_fail_closed() -> None:
    _, _, _, _, _, _, router = _pipeline()
    request = next(item for item in router.requests if item.route is ResearchRoute.WEB)
    observation = EvidenceObservation(
        request_id=request.request_id,
        classification=EvidenceClassification.STRONG_EVIDENCE,
        stance=EvidenceStance.SUPPORTS,
        confidence=0.90,
    )

    with pytest.raises(ValidationError):
        build_evidence(router, [observation])


def test_conflicting_evidence_is_tracked_as_conflict_not_silently_averaged() -> None:
    _, _, _, _, _, _, router = _pipeline()
    request = next(item for item in router.requests if item.route is ResearchRoute.WEB)
    observation = EvidenceObservation(
        request_id=request.request_id,
        source="Two-source comparison",
        source_type="mixed primary sources",
        classification=EvidenceClassification.CONFLICTING_EVIDENCE,
        stance=EvidenceStance.MIXED,
        confidence=0.72,
        contradiction_notes=["Source A supports the claim while Source B materially contradicts it."],
    )

    result = build_evidence(router, [observation])
    assert request.claim_id in result.conflicting_claim_ids
    item = next(e for e in result.evidence if e.claim_id == request.claim_id)
    assert item.classification is EvidenceClassification.CONFLICTING_EVIDENCE
    assert item.stance is EvidenceStance.MIXED
    assert item.contradiction_notes


def test_unknown_cannot_carry_false_high_confidence() -> None:
    _, _, _, _, _, _, router = _pipeline()
    request = router.requests[0]
    observation = EvidenceObservation(
        request_id=request.request_id,
        classification=EvidenceClassification.UNKNOWN,
        confidence=0.90,
    )

    with pytest.raises(ValidationError):
        build_evidence(router, [observation])