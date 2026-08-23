import io
import json
from pathlib import Path
import sys
import zipfile

from opportunity_engine.mind_forge_checkpoint_bridge_restore import _extract_fast_memory
from scripts import mind_forge_v2_decision_experiment as decision
from scripts import run_search_experiment_checkpoint_cycle as cycle


def _route_seed():
    return (
        "Improve discovery intelligence for IT / FABRIC_PROCUREMENT / FABRIC_PROCUREMENT. "
        "Current route status: GAP. Generate alternative search/discovery mechanisms."
    )


def _creative_payload():
    return {
        "seed": _route_seed(),
        "ideas": [
            {
                "idea_id": "idea-1",
                "title": "Prato deadstock route",
                "core_mechanism": (
                    'SEARCH_TEST_V1 provider=exa; '
                    'query="Italia tessuti deadstock ingrosso rotoli prezzo EUR"'
                ),
            }
        ],
    }


def _rank():
    return {"ranking": [{"idea_id": "idea-1", "title": "Prato deadstock route"}]}


def test_decision_stage_exports_ready_spec_into_existing_fast_memory(tmp_path):
    root = tmp_path / "run"
    root.mkdir()
    (root / "result.json").write_text(json.dumps(_creative_payload()), encoding="utf-8")
    (root / "final_rank.json").write_text(json.dumps(_rank()), encoding="utf-8")
    (root / "fast_learning_memory.json").write_text(
        json.dumps({"schema_version": "mind-forge-fast-learning-memory-1.0"}),
        encoding="utf-8",
    )

    result = decision._attach_search_experiment_spec(
        result={"status": "MIND_FORGE_V2_DECISION_EXPERIMENT_COMPLETE"},
        final_rank_path=root / "final_rank.json",
    )
    fast = json.loads((root / "fast_learning_memory.json").read_text(encoding="utf-8"))

    assert result["search_experiment_bridge"] == "READY_FOR_NEXT_CHECKPOINT"
    spec = fast["pending_search_experiment_spec"]
    assert spec["status"] == "READY"
    assert spec["market_code"] == "IT"
    assert spec["project_domain"] == "FABRIC_PROCUREMENT"
    assert spec["slot_id"] == "FABRIC_PROCUREMENT"
    assert spec["automatic_query_activation"] is False


def test_mind_forge_artifact_restore_accepts_only_ready_search_spec():
    fast = {
        "schema_version": "mind-forge-fast-learning-memory-1.0",
        "pending_search_experiment_spec": {
            "status": "READY",
            "experiment_fingerprint": "search-experiment:abc",
        },
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("fast_learning_memory.json", json.dumps(fast))
    assert _extract_fast_memory(buffer.getvalue()) == fast

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "fast_learning_memory.json",
            json.dumps({"schema_version": "mind-forge-fast-learning-memory-1.0"}),
        )
    assert _extract_fast_memory(buffer.getvalue()) is None


def test_checkpoint_cycle_executes_new_spec_once_and_uses_existing_memory(monkeypatch):
    spec = {
        "schema_version": "search-experiment-spec-1.0",
        "status": "READY",
        "experiment_fingerprint": "search-experiment:abc",
        "market_code": "IT",
        "project_domain": "FABRIC_PROCUREMENT",
        "slot_id": "FABRIC_PROCUREMENT",
        "provider": "exa",
        "query": "Italia tessuti deadstock ingrosso rotoli prezzo EUR",
        "route": "SEARCH_TO_FABRIC_COMMERCIAL_PAGE",
        "route_source_identity": "search-experiment:fabric_procurement",
        "max_independent_executions": 3,
    }
    fake_result = {
        "schema_version": "search-experiment-execution-bridge-1.0",
        "status": "SUCCESS",
        "origin_experiment_run_id": "run-2",
        "observed_at": "2026-08-25T05:20:00+00:00",
        "experiment_fingerprint": "search-experiment:abc",
        "spec": spec,
        "outcome": "NO_VERIFIED_ROUTE",
        "successful_route": False,
        "search_hit_count": 2,
        "verified_page_count": 2,
        "successful_result_count": 0,
        "verified_result_urls": [],
        "verified_result_domains": [],
        "project_domain_gate_enforced": True,
        "automatic_query_activation": False,
        "automatic_provider_activation": False,
        "automatic_source_promotion": False,
        "automatic_code_change": False,
        "production_query_mutation": False,
        "production_mutation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }

    monkeypatch.setattr(cycle, "execute_search_experiment_spec", lambda *a, **k: fake_result)
    report = cycle.run_checkpoint_cycle(
        fast_memory={"pending_search_experiment_spec": spec},
        existing_memory={},
        run_id="run-2",
        exa_api_key="test",
        rule_registry={},
    )

    assert report["status"] == "EXECUTED_AND_LEARNED"
    assert report["selection_reason"] == "NEW_MIND_FORGE_SPEC"
    assert report["network_search_executed"] is True
    assert report["execution_count_after"] == 1
    assert report["memory"]["query_memory_count"] == 1


def test_route_teaching_prompt_requires_machine_readable_search_contract():
    mind_forge_root = Path(__file__).resolve().parents[1] / "mind-forge-live"
    sys.path.insert(0, mind_forge_root.as_posix())
    try:
        from phase1.contracts_v1 import Question, QuestionKind, TopicInput
        from phase1.creative_engine_v2_open import open_creative_prompt

        topic = TopicInput(topic=_route_seed())
        questions = [
            Question(
                question_id="q-1",
                text="Which search route reaches original textile stock pages?",
                kind=QuestionKind.INTERNAL,
                purpose="Find a route.",
            )
        ]
        prompt = open_creative_prompt(topic, questions)
    finally:
        sys.path.remove(mind_forge_root.as_posix())

    assert "EXECUTABLE SEARCH CONTRACT" in prompt
    assert 'SEARCH_TEST_V1 provider=exa; query="<one public-web search query>"' in prompt
    assert "FABRIC_PROCUREMENT" in prompt
