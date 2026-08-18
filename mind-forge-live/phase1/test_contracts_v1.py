from __future__ import annotations

import pytest
from pydantic import ValidationError

from mind_forge.contracts_v1 import (
    Critique,
    CritiqueDisposition,
    Decision,
    DecisionVerdict,
    Evidence,
    EvidenceClassification,
    Experiment,
    ExpertMindOutput,
    Idea,
    MemoryRecord,
    MemoryTruthStatus,
    MemoryType,
    MetricDirection,
    MetricSpec,
    Question,
    QuestionKind,
    RunContract,
    TopicInput,
)


def test_topic_only_seed_is_valid() -> None:
    seed = TopicInput(topic="تصليح الملابس")
    assert seed.topic == "تصليح الملابس"
    assert seed.constraints == []
    assert seed.goals == []


def test_low_value_user_question_cannot_be_blocking() -> None:
    with pytest.raises(ValidationError):
        Question(
            question_id="q-low",
            text="كم لونًا تفضّل؟",
            kind=QuestionKind.USER,
            purpose="non-material preference",
            expected_information_gain=0.1,
            interruption_cost=0.4,
            materiality=0.2,
            blocking=True,
        )


def test_verified_fact_requires_provenance() -> None:
    with pytest.raises(ValidationError):
        Evidence(
            evidence_id="e-1",
            claim_id="claim-1",
            claim_text="There are three local competitors.",
            classification=EvidenceClassification.VERIFIED_FACT,
            confidence=0.9,
        )


def test_assumption_can_exist_without_becoming_fact() -> None:
    item = Evidence(
        evidence_id="e-assumption",
        claim_id="claim-assumption",
        claim_text="Customers may pay for pickup and return.",
        classification=EvidenceClassification.ASSUMPTION,
        confidence=0.35,
    )
    assert item.source is None
    assert item.classification is EvidenceClassification.ASSUMPTION


def test_decision_cannot_select_more_than_three_ideas() -> None:
    with pytest.raises(ValidationError):
        Decision(
            decision_id="d-1",
            finalist_idea_ids=["i1", "i2", "i3", "i4"],
            selected_idea_ids=["i1", "i2", "i3", "i4"],
            verdict=DecisionVerdict.TEST_NOW,
            confidence=0.5,
            rationale=["Too many selected candidates."],
        )


def test_verified_memory_requires_grounding() -> None:
    with pytest.raises(ValidationError):
        MemoryRecord(
            memory_id="m-1",
            run_id="r-1",
            memory_type=MemoryType.DOMAIN_HEURISTIC,
            statement="Pickup service always works.",
            truth_status=MemoryTruthStatus.VERIFIED,
            confidence=0.9,
        )


def test_clothing_alterations_acceptance_shape_supports_ten_distinct_minds() -> None:
    topic = TopicInput(topic="تصليح الملابس")

    questions = [
        Question(
            question_id="q-internal",
            text="Where does value leak in the current service flow?",
            kind=QuestionKind.INTERNAL,
            purpose="Find bottlenecks without interrupting the user.",
            materiality=0.8,
        ),
        Question(
            question_id="q-user",
            text="What capital ceiling may the first experiment use?",
            kind=QuestionKind.USER,
            purpose="Bound experiment downside.",
            decision_variable="experiment_budget",
            expected_information_gain=0.9,
            interruption_cost=0.2,
            materiality=0.9,
            blocking=True,
        ),
    ]

    ideas = [
        Idea(
            idea_id="idea-pickup",
            title="Pickup and return route",
            core_mechanism="Bundle alteration orders into bounded pickup windows.",
            assumptions=["Enough nearby demand exists to fill a route."],
            risks=["Travel time can destroy unit economics."],
            source_question_ids=["q-internal"],
        ),
        Idea(
            idea_id="idea-standard",
            title="Standard alteration menu",
            core_mechanism="Standardize common jobs, intake, price bands, and lead times.",
            assumptions=["A meaningful share of jobs are repeatable."],
            risks=["Complex jobs still need expert handling."],
            source_question_ids=["q-internal"],
        ),
    ]

    lenses = [
        "Systems & Control",
        "Information & Network",
        "Capital Efficiency",
        "Scale & Throughput",
        "Productivity",
        "Standardization",
        "Distribution & Flow",
        "Customer Experience",
        "Replication",
        "Differentiation",
    ]
    expert_outputs = [
        ExpertMindOutput(
            mind_id=f"mind-{index:02d}",
            lens=lens,
            assessed_idea_ids=["idea-pickup", "idea-standard"],
            strongest_idea_id=(
                "idea-standard"
                if lens in {"Systems & Control", "Productivity", "Standardization", "Replication"}
                else "idea-pickup"
            ),
            independent_reasoning=[f"Independent assessment through {lens}."],
            objections=[f"{lens} objection."],
            evidence_that_changes_view=[f"{lens} evidence request."],
            support_scores={"idea-pickup": 0.6, "idea-standard": 0.7},
        )
        for index, lens in enumerate(lenses, start=1)
    ]

    critique = Critique(
        critique_id="crit-pickup",
        idea_id="idea-pickup",
        failure_modes=["Travel cost may exceed contribution margin."],
        hidden_assumptions=["Customer density is sufficient."],
        falsification_test="A two-week route fails to reach the minimum paid-order density.",
        low_cost_test="Offer two fixed pickup windows before buying any vehicle or hiring.",
        severity=0.75,
        disposition=CritiqueDisposition.NEEDS_EVIDENCE,
    )

    assumption = Evidence(
        evidence_id="e-assumption-density",
        claim_id="claim-density",
        claim_text="Local demand density may support two pickup windows.",
        idea_id="idea-pickup",
        classification=EvidenceClassification.ASSUMPTION,
        confidence=0.35,
    )

    decision = Decision(
        decision_id="decision-1",
        finalist_idea_ids=["idea-pickup", "idea-standard"],
        selected_idea_ids=["idea-standard"],
        rejected_idea_ids=[],
        verdict=DecisionVerdict.TEST_NOW,
        score_by_idea={"idea-pickup": 0.63, "idea-standard": 0.79},
        confidence=0.62,
        evidence_ids=["e-assumption-density"],
        unresolved_unknowns=["Actual share of jobs that fit a standard menu."],
        rationale=["Standardization is cheap and reversible to test."],
    )

    metric = MetricSpec(
        name="standard_menu_share",
        direction=MetricDirection.AT_LEAST,
        threshold=0.60,
        unit="share_of_orders",
    )
    experiment = Experiment(
        experiment_id="experiment-standard-menu",
        idea_id="idea-standard",
        hypothesis="A standard menu can cover at least 60% of incoming jobs without reducing quality.",
        steps=[
            "Tag every incoming job for two weeks.",
            "Measure whether it fits one of the predefined service recipes.",
        ],
        cost_ceiling=500.0,
        time_ceiling_hours=10.0,
        success_metrics=[metric],
        stop_conditions=["Quality complaints increase materially."],
        data_to_record=["job type", "minutes worked", "price", "rework"],
        next_decision_if_passed="Pilot standardized intake and pricing.",
        next_decision_if_failed="Rework the service taxonomy.",
    )

    run = RunContract(
        run_id="benchmark-clothing-alterations",
        topic=topic,
        questions=questions,
        ideas=ideas,
        expert_outputs=expert_outputs,
        critiques=[critique],
        evidence=[assumption],
        decision=decision,
        experiments=[experiment],
    )

    assert len(run.expert_outputs) == 10
    assert len({mind.mind_id for mind in run.expert_outputs}) == 10
    assert len({mind.lens for mind in run.expert_outputs}) == 10
    assert run.decision is not None
    assert len(run.decision.selected_idea_ids) <= 3
    assert run.experiments[0].idea_id in run.decision.selected_idea_ids
