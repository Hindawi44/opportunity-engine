import pytest
from pydantic import ValidationError

from mind_forge.contracts_v1 import TopicInput
from mind_forge.creative_engine_v1 import generate_ideas
from mind_forge.live_model_adapter_v1 import (
    LiveBudgetGate,
    LiveCreativePayload,
    LiveExpertDraft,
    LiveIdeaRewrite,
    LiveModelPolicy,
    apply_live_creative_payload,
    apply_live_expert_drafts,
    assert_live_model_access,
)
from mind_forge.live_pipeline_v1 import run_live_model_forge
from mind_forge.question_generator_v1 import generate_questions


def _baseline():
    topic = TopicInput(topic="تصليح الملابس")
    questions = generate_questions(topic)
    return topic, questions, generate_ideas(topic, questions)


def _creative_payload(baseline):
    return LiveCreativePayload(
        ideas=[
            LiveIdeaRewrite(
                idea_id=idea.idea_id,
                title=f"Live {idea.title}",
                core_mechanism=f"Live-specific mechanism for {idea.idea_id}",
                customer_value="More explicit customer value without asserting demand facts.",
                business_value="A testable commercial mechanism rather than an unsupported market claim.",
                required_capabilities=["measurement", "controlled execution"],
                assumptions=["The mechanism creates enough value to justify a small test."],
                risks=["Operational complexity could outweigh the intended benefit."],
                novelty_reason="The live rewrite makes the bounded mechanism more topic-specific.",
            )
            for idea in baseline.ideas
        ]
    )


def _expert_drafts(creative):
    idea_ids = [idea.idea_id for idea in creative.ideas]
    mind_ids = [
        "rockefeller",
        "rothschild",
        "buffett",
        "walton",
        "carnegie",
        "ford",
        "vanderbilt",
        "lauder",
        "kroc",
        "jobs",
    ]
    drafts = {}
    for index, mind_id in enumerate(mind_ids):
        strongest = idea_ids[index % len(idea_ids)]
        drafts[mind_id] = LiveExpertDraft(
            strongest_idea_id=strongest,
            independent_reasoning=[
                f"{mind_id} applies only its bounded lens.",
                "The score is a viewpoint, not a structural survival gate.",
            ],
            assumptions=["The relevant operating premise still needs testing."],
            objections=["The mechanism could fail under real customer or capacity constraints."],
            evidence_that_changes_view=["Observed test results would materially change this view."],
            support_scores={
                idea_id: round(0.35 + ((offset + index) % 10) * 0.05, 2)
                for offset, idea_id in enumerate(idea_ids)
            },
        )
    return drafts


def test_live_access_requires_explicit_opt_in_and_existing_key(monkeypatch):
    policy = LiveModelPolicy(enabled=True)
    monkeypatch.delenv("MIND_FORGE_LIVE_ENABLED", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="MIND_FORGE_LIVE_ENABLED"):
        assert_live_model_access(policy)

    monkeypatch.setenv("MIND_FORGE_LIVE_ENABLED", "1")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        assert_live_model_access(policy)

    monkeypatch.setenv("OPENAI_API_KEY", "present-but-never-inspected")
    assert_live_model_access(policy)


def test_policy_does_not_store_secret_and_rejects_unreviewed_model():
    policy = LiveModelPolicy()
    serialized = policy.model_dump()
    assert "OPENAI_API_KEY" not in serialized
    assert "api_key" not in serialized
    with pytest.raises(ValidationError):
        LiveModelPolicy(creative_model="unreviewed-model")


def test_budget_gate_hard_caps_request_count():
    policy = LiveModelPolicy(
        enabled=True,
        creative_model="gpt-5.6-luna",
        expert_model="gpt-5.6-luna",
        max_estimated_cost_usd=0.25,
    )
    gate = LiveBudgetGate(policy)
    for _ in range(11):
        gate.reserve(model="gpt-5.6-luna", prompt="small prompt", max_output_tokens=300)
    with pytest.raises(RuntimeError, match="request budget exhausted"):
        gate.reserve(model="gpt-5.6-luna", prompt="small prompt", max_output_tokens=300)


def test_live_creative_rewrite_preserves_exact_ids_families_and_provenance():
    _, _, baseline = _baseline()
    live = apply_live_creative_payload(baseline, _creative_payload(baseline))

    assert [idea.idea_id for idea in live.ideas] == [idea.idea_id for idea in baseline.ideas]
    assert live.mechanism_family_by_idea_id == baseline.mechanism_family_by_idea_id
    assert live.mechanism_diversity_ratio == 1.0
    assert [idea.source_question_ids for idea in live.ideas] == [
        idea.source_question_ids for idea in baseline.ideas
    ]
    assert all(idea.title.startswith("Live ") for idea in live.ideas)


def test_live_creative_rewrite_fails_closed_on_changed_idea_universe():
    _, _, baseline = _baseline()
    payload = _creative_payload(baseline)
    foreign = payload.ideas[-1].model_copy(update={"idea_id": "idea-foreign"})
    changed_universe = LiveCreativePayload(ideas=payload.ideas[:-1] + [foreign])
    with pytest.raises(ValueError, match="exact baseline idea universe"):
        apply_live_creative_payload(baseline, changed_universe)


def test_live_expert_drafts_cover_exact_ten_minds_and_full_idea_universe():
    _, _, baseline = _baseline()
    creative = apply_live_creative_payload(baseline, _creative_payload(baseline))
    outputs = apply_live_expert_drafts(creative, _expert_drafts(creative))

    assert len(outputs) == 10
    idea_ids = {idea.idea_id for idea in creative.ideas}
    assert {output.mind_id for output in outputs} == {
        "rockefeller",
        "rothschild",
        "buffett",
        "walton",
        "carnegie",
        "ford",
        "vanderbilt",
        "lauder",
        "kroc",
        "jobs",
    }
    assert all(set(output.assessed_idea_ids) == idea_ids for output in outputs)
    assert all(set(output.support_scores) == idea_ids for output in outputs)


def test_live_expert_drafts_fail_closed_on_missing_score():
    _, _, baseline = _baseline()
    creative = apply_live_creative_payload(baseline, _creative_payload(baseline))
    drafts = _expert_drafts(creative)
    broken = drafts["buffett"]
    first_idea_id = creative.ideas[0].idea_id
    drafts["buffett"] = broken.model_copy(
        update={
            "support_scores": {
                key: value for key, value in broken.support_scores.items() if key != first_idea_id
            }
        }
    )
    with pytest.raises(ValueError, match="complete idea universe"):
        apply_live_expert_drafts(creative, drafts)


def test_live_pipeline_is_disabled_by_default_before_any_paid_call(monkeypatch):
    monkeypatch.delenv("MIND_FORGE_LIVE_ENABLED", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="policy is disabled"):
        run_live_model_forge("تصليح الملابس")
