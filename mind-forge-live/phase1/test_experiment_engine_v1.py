from __future__ import annotations

from mind_forge.contracts_v1 import DecisionVerdict, RunContract, TopicInput
from mind_forge.creative_engine_v1 import generate_ideas
from mind_forge.critique_engine_v1 import critique_survivors
from mind_forge.decision_engine_v1 import decide
from mind_forge.experiment_engine_v1 import design_experiments
from mind_forge.expert_minds_v1 import evaluate_with_expert_minds
from mind_forge.logic_engine_v1 import evaluate_logic
from mind_forge.question_generator_v1 import generate_questions
from mind_forge.research_evidence_v1 import (
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
    experiments = design_experiments(creative, critique, decision)
    return topic, questions, creative, experts, logic, critique, router, evidence, decision, experiments


def test_test_now_emits_exactly_one_experiment_per_selected_idea() -> None:
    _, _, _, _, _, _, _, _, decision, result = _pipeline()

    assert decision.decision.verdict is DecisionVerdict.TEST_NOW
    assert result.executable_now is True
    assert len(result.experiments) == len(decision.decision.selected_idea_ids) == 3
    assert {item.idea_id for item in result.experiments} == set(decision.decision.selected_idea_ids)


def test_every_experiment_is_bounded_and_falsifiable() -> None:
    _, _, _, _, _, _, _, _, _, result = _pipeline()

    for experiment in result.experiments:
        assert experiment.cost_ceiling >= 0.0
        assert experiment.time_ceiling_hours > 0.0
        assert experiment.success_metrics
        assert experiment.stop_conditions
        assert experiment.data_to_record
        assert "falsification" in experiment.hypothesis.casefold()
        assert experiment.steps


def test_selected_benchmark_experiments_use_structured_family_metrics() -> None:
    _, _, creative, _, _, _, _, _, _, result = _pipeline()
    family_by_id = creative.mechanism_family_by_idea_id
    by_family = {family_by_id[item.idea_id]: item for item in result.experiments}

    assert set(by_family) == {"bottleneck_redesign", "standardization", "data_feedback"}
    assert any(metric.name == "end_to_end_cycle_time_change" for metric in by_family["bottleneck_redesign"].success_metrics)
    assert any(metric.name == "package_fit_rate" for metric in by_family["standardization"].success_metrics)
    assert any(metric.name == "decision_changes_from_data" for metric in by_family["data_feedback"].success_metrics)


def _force_selected_external(router: ResearchRouterResult, selected_idea_id: str) -> ResearchRouterResult:
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


def test_test_after_evidence_gate_emits_no_runnable_experiments() -> None:
    _, _, creative, _, logic, critique, router, _, baseline_decision, _ = _pipeline()
    selected_id = baseline_decision.decision.selected_idea_ids[0]
    forced_router = _force_selected_external(router, selected_id)
    evidence = build_evidence(forced_router)
    blocked_decision = decide(creative, logic, critique, forced_router, evidence)
    result = design_experiments(creative, critique, blocked_decision)

    assert blocked_decision.decision.verdict is DecisionVerdict.TEST_AFTER_EVIDENCE
    assert result.executable_now is False
    assert result.experiments == []


def test_experiments_fit_canonical_run_contract_and_only_test_selected_ideas() -> None:
    topic, questions, creative, experts, _, critique, _, evidence, decision, result = _pipeline()

    contract = RunContract(
        run_id="phase1-experiment-benchmark",
        topic=topic,
        questions=questions,
        ideas=creative.ideas,
        expert_outputs=experts,
        critiques=critique.critiques,
        evidence=evidence.evidence,
        decision=decision.decision,
        experiments=result.experiments,
    )
    assert len(contract.experiments) == 3
    assert {item.idea_id for item in contract.experiments} == set(contract.decision.selected_idea_ids)
