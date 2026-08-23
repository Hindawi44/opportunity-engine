import inspect
import sys
import types
from pathlib import Path


# Normal repository CI intentionally does not install the paid Agents SDK.
# Stub only the import surface because these tests exercise pure planning/wiring logic.
if "agents" not in sys.modules:
    agents_stub = types.ModuleType("agents")

    class _AgentsStub:
        pass

    agents_stub.Agent = _AgentsStub
    agents_stub.ModelSettings = _AgentsStub
    agents_stub.Runner = _AgentsStub
    agents_stub.WebSearchTool = _AgentsStub
    sys.modules["agents"] = agents_stub

from scripts.mind_forge_v2_live_evidence_runtime import _build_plan, _prompt, run_live_top3_evidence


LIVE_CREATIVE = Path("mind-forge-live/phase1/live_creative_v2_open.py")
LIVE_EVIDENCE = Path("scripts/mind_forge_v2_live_evidence_runtime.py")


def _reasoning():
    return {
        "seed": "raw seed",
        "selected_idea_ids": ["a", "b", "c"],
        "assessments": [
            {"idea_id": "a", "title": "A", "critique": {"key_assumption": "Claim A"}},
            {"idea_id": "b", "title": "B", "critique": {"key_assumption": "Claim B"}},
            {"idea_id": "c", "title": "C", "critique": {"key_assumption": "Claim C"}},
        ],
    }


def _memory():
    return {
        "auto_apply_to_production": False,
        "next_cycle_search_adjustments": [
            {
                "action": "REQUIRE_EXACT_CLAIM_RELEVANCE",
                "search_question": "Can the exact claim be tested with direct evidence instead of generic background data?",
                "required_evidence": "Prefer direct evidence; generic background data is not proof.",
                "origin_memory_id": "v2-fast-generic-evidence-rejected",
                "mode": "SHADOW_HINT",
                "may_auto_reject_ideas": False,
            }
        ],
    }


def test_live_evidence_plan_consumes_shadow_memory_without_changing_top3_or_search_budget():
    plan = _build_plan(_reasoning(), prior_memory=_memory())

    assert len(plan) == 3
    assert [row["idea_id"] for row in plan] == ["a", "b", "c"]
    assert all(len(row["shadow_search_hints"]) == 1 for row in plan)
    prompt = _prompt(plan[0])
    assert "PRIOR CROSS-RUN LEARNING" in prompt
    assert "exact claim" in prompt.lower()
    assert "direct evidence" in prompt.lower()
    assert "search guidance only" in prompt.lower()


def test_live_runtime_accepts_prior_memory_and_writes_current_fast_memory_artifact():
    signature = inspect.signature(run_live_top3_evidence)
    assert "prior_memory" in signature.parameters

    source = LIVE_EVIDENCE.read_text(encoding="utf-8")
    assert "learn_from_run" in source
    assert "fast_learning_memory.json" in source
    assert "GITHUB_RUN_ID" in source


def test_live_creative_hook_can_load_prior_memory_path_and_pass_it_to_evidence_runtime():
    source = LIVE_CREATIVE.read_text(encoding="utf-8")

    assert "MIND_FORGE_PRIOR_MEMORY_PATH" in source
    assert "prior_memory=prior_memory" in source
