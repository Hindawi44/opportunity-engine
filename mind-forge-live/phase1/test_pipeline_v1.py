from __future__ import annotations

from mind_forge.contracts_v1 import DecisionVerdict, MemoryTruthStatus, QuestionKind, TopicInput
from mind_forge.pipeline_v1 import run_phase1_forge
from mind_forge.research_evidence_v1 import ResearchRoute


def test_raw_seed_runs_end_to_end_without_user_interruption() -> None:
    result = run_phase1_forge("تصليح الملابس")
    contract = result.run_contract

    assert contract.topic.topic == "تصليح الملابس"
    assert result.user_questions_asked == []
    assert len([q for q in contract.questions if q.kind is QuestionKind.INTERNAL]) >= 8
    assert len(contract.ideas) == 14
    assert len(contract.expert_outputs) == 10
    assert len(result.logic.survivor_idea_ids) == 6
    assert len(contract.critiques) == 6
    assert len(result.critique.survived_idea_ids) == 3
    assert len(result.critique.rework_idea_ids) == 2
    assert len(result.critique.needs_evidence_idea_ids) == 1
    assert len(result.research.requests) == 6
    assert len(result.research.experiment_request_ids) == 4
    assert len(result.research.external_request_ids) == 2
    assert contract.decision is not None
    assert contract.decision.verdict is DecisionVerdict.TEST_NOW
    assert len(contract.decision.selected_idea_ids) == 3
    assert len(contract.experiments) == 3
    assert len(contract.memory_records) == 3
    assert all(item.truth_status is MemoryTruthStatus.INFERRED for item in contract.memory_records)


def test_one_call_preserves_structural_diversity_and_full_expert_universe() -> None:
    result = run_phase1_forge("تصليح الملابس")
    contract = result.run_contract
    idea_ids = {item.idea_id for item in contract.ideas}

    assert result.creative.mechanism_diversity_ratio == 1.0
    assert len(set(result.creative.mechanism_family_by_idea_id.values())) == 14
    assert all(set(output.assessed_idea_ids) == idea_ids for output in contract.expert_outputs)
    assert len({output.mind_id for output in contract.expert_outputs}) == 10


def test_research_state_is_bounded_and_unresolved_claims_are_not_upgraded() -> None:
    result = run_phase1_forge("تصليح الملابس")

    assert all(request.expected_decision_impact >= 0.60 for request in result.research.requests)
    assert all(
        request.route in {ResearchRoute.EXPERIMENT, ResearchRoute.WEB}
        for request in result.research.requests
    )
    assert result.evidence_engine.resolved_request_ids == []
    assert len(result.evidence_engine.unresolved_request_ids) == 6
    assert not any(item.source for item in result.evidence_engine.evidence)


def test_topicinput_constraints_flow_through_same_one_call_pipeline() -> None:
    topic = TopicInput(topic="تصليح الملابس", goals=["Improve the business without a new location"])
    result = run_phase1_forge(topic, max_selected=1)

    assert result.run_contract.topic.goals == topic.goals
    assert result.user_questions_asked == []
    assert result.run_contract.decision is not None
    assert len(result.run_contract.decision.selected_idea_ids) == 1
    assert len(result.run_contract.experiments) == 1
    assert len(result.run_contract.memory_records) == 1


def test_pipeline_run_id_is_deterministic_for_same_seed() -> None:
    first = run_phase1_forge("تصليح الملابس")
    second = run_phase1_forge("  تصليح الملابس  ")

    assert first.run_contract.run_id == second.run_contract.run_id
