import json
from pathlib import Path


POLICY = Path("config/learning/ai-teaching-gate-v1.json")
GATE = Path("src/opportunity_engine/ai_teaching_gate_v1.py")


def test_ai_teaching_policy_reuses_existing_mind_forge_without_automatic_spend():
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    mind_forge = policy["mind_forge"]

    assert policy["schema_version"] == "ai-teaching-gate-policy-1.0"
    assert policy["allowed_project_domains"] == [
        "CLOTHING_INVENTORY",
        "FABRIC_PROCUREMENT",
    ]
    assert policy["execution_modes"] == [
        "FIXED_RULE",
        "DETERMINISTIC_PROOF",
        "AI_TEACHING",
    ]
    assert mind_forge["reuse_existing_runtime"] is True
    assert mind_forge["reuse_existing_cross_run_learning"] is True
    assert mind_forge["manual_paid_run_required"] is True
    assert mind_forge["existing_budget_gate_authoritative"] is True
    assert mind_forge["duplicate_budget_policy"] is False
    assert mind_forge["automatic_ai_invocation"] is False
    assert policy["automatic_ai_invocation"] is False
    assert policy["production_mutation"] is False


def test_policy_references_the_same_existing_runtime_and_learning_as_the_gate():
    policy = json.loads(POLICY.read_text(encoding="utf-8"))["mind_forge"]
    source = GATE.read_text(encoding="utf-8")

    assert policy["runtime_reference"] in source
    assert policy["learning_reference"] in source
    assert '"manual_paid_run_required": True' in source
    assert '"automatic_ai_invocation": False' in source
    assert '"budget_policy_is_not_duplicated_here": True' in source
