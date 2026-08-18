from __future__ import annotations

from mind_forge.contracts_v1 import (
    DecisionVerdict,
    EvidenceClassification,
    EvidenceStance,
    RunContract,
    TopicInput,
)
from mind_forge.creative_engine_v1 import generate_ideas
from mind_forge.critique_engine_v1 import critique_survivors
from mind_forge.decision_engine_v1 import decide
from mind_forge.expert_minds_v1 import evaluate_with_expert_minds
from mind_forge.logic_engine_v1 import evaluate_logic
from mind_forge.question_generator_v1 import generate_questions
from mind_forge.research_evidence_v1 import (
    EvidenceObservation,
    ResearchRequest,
    ResearchRoute,
    ResearchRouterResult,
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
    evidence = build_evidence(router)
    decision = decide(creative, logic, critique, router, evidence)
    return topic, questions, creative, experts, logic, critique, router, evidence, decision


def test_plain_seed_selects_at_most_three_true_survivors_for_test_now() -> None:
    _, _, _, _, logic, critique, _, _, result = _pipeline()

    decision = result.decision
    assert decision.verdict is DecisionVerdict.TEST_NOW
    assert 1 <= len(decision.selected_idea_ids) <= 3
    assert len(decision.selected_idea_ids) == 3
    assert set(decision.selected_idea_ids).issubset(set(logic.survivor_idea_ids))
    assert set(decision.selected_idea_ids).issubset(set(critique.survived_idea_ids))
    assert decision.needs_research is False
    assert result.expert_popularity_can_override_logic is False


def test_rework_needs_evidence_hold_and_reject_cannot_outrank_true_survivors() -> None:
    _, _, _, _, logic, critique, _, _, result = _pipeline()
    selected = set(result.decision.selected_idea_ids)

    assert selected.isdisjoint(set(critique.rework_idea_ids))
    assert selected.isdisjoint(set(critique.needs_evidence_idea_ids))
    assert selected.isdisjoint(set(critique.rejected_idea_ids))
    assert selected.isdisjoint(set(logic.held_idea_ids))
    assert selected.isdisjoint(set(logic.rejected_idea_ids))


def test_max_selected_is_a_hard_bound_not_a_suggestion() -> None:
    _, _, creative, _, logic, critique, router, evidence, _ = _pipeline()
    result = decide(creative, logic, critique, router, evidence, max_selected=1)

    assert result.max_selected == 1
    assert len(result.decision.selected_idea_ids) == 1


def _force_selected_request_external(router: ResearchRouterResult, selected_idea_id: str) -> ResearchRouterResult:
    requests: list[ResearchRequest] = []
    external_ids: list[str] = []
    experiment_ids: list[str] = []
    user_ids: list[str] = []
    for item in router.requests:
        if item.idea_id == selected_idea_id:
            item = ResearchRequest(
                request_id=item.request_id,
                claim_id=item.claim_id,
                idea_id=item.idea_id,
                claim_text=item.claim_text,
                why_material=item.why_material,
                route=ResearchRoute.WEB,
                expected_decision_impact=item.expected_decision_impact,
                acceptable_source_types=["primary market data"],
                status=item.status,
            )
        requests.append(item)
        if item.route in {ResearchRoute.WEB, ResearchRoute.PUBLIC_DATA, ResearchRoute.CALCULATOR}:
            external_ids.append(item.request_id)
        elif item.route is ResearchRoute.EXPERIMENT:
            experiment_ids.append(item.request_id)
        else:
            user_ids.append(item.request_id)
    return ResearchRouterResult(
        candidate_idea_ids=list(router.candidate_idea_ids),
        requests=requests,
        external_request_ids=external_ids,
        experiment_request_ids=experiment_ids,
        user_request_ids=user_ids,
        max_requests_per_idea=router.max_requests_per_idea,
    )


def test_unresolved_material_external_research_blocks_test_now() -> None:
    _, _, creative, _, logic, critique, router, _, baseline = _pipeline()
    selected_id = baseline.decision.selected_idea_ids[0]
    forced_router = _force_selected_request_external(router, selected_id)
    evidence = build_evidence(forced_router)
    result = decide(creative, logic, critique, forced_router, evidence)

    assert result.decision.verdict is DecisionVerdict.TEST_AFTER_EVIDENCE
    assert result.decision.needs_research is True
    assert any(selected_id in item for item in result.decision.unresolved_unknowns)


def test_resolving_external_request_with_sourced_evidence_restores_test_now() -> None:
    _, _, creative, _, logic, critique, router, _, baseline = _pipeline()
    selected_id = baseline.decision.selected_idea_ids[0]
    forced_router = _force_selected_request_external(router, selected_id)
    request = next(item for item in forced_router.requests if item.idea_id == selected_id)
    observation = EvidenceObservation(
        request_id=request.request_id,
        source="Primary market dataset",
        source_type="primary market data",
        classification=EvidenceClassification.STRONG_EVIDENCE,
        stance=EvidenceStance.SUPPORTS,
        confidence=0.88,
    )
    evidence = build_evidence(forced_router, [observation])
    result = decide(creative, logic, critique, forced_router, evidence)

    assert result.decision.verdict is DecisionVerdict.TEST_NOW
    assert result.decision.needs_research is False


def test_decision_and_evidence_fit_the_canonical_run_contract() -> None:
    topic, questions, creative, experts, _, critique, _, evidence, result = _pipeline()

    contract = RunContract(
        run_id="phase1-decision-benchmark",
        topic=topic,
        questions=questions,
        ideas=creative.ideas,
        expert_outputs=experts,
        critiques=critique.critiques,
        evidence=evidence.evidence,
        decision=result.decision,
    )
    assert contract.decision is not None
    assert contract.decision.verdict is DecisionVerdict.TEST_NOW
    assert len(contract.decision.selected_idea_ids) == 3
