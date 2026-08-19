from __future__ import annotations

import json
from pathlib import Path

import pytest

from mind_forge.contracts_v1 import EvidenceClassification, EvidenceStance
from mind_forge.live_research_adapter_v1 import (
    FakeResearchExecutor,
    RawResearchHit,
    ResearchPolicy,
)
from mind_forge.pipeline_v1 import run_phase1_forge
from mind_forge.runner_v1 import (
    _cli_research_policy,
    build_runner_summary,
    main,
    run_mind_forge,
)
from mind_forge.runner_v1_resilient import (
    resilient_build_runner_summary,
    resilient_cli_research_policy,
    resilient_run_mind_forge,
)


def _fake_hits_for_external_requests(seed: str):
    baseline = run_phase1_forge(seed)
    external_ids = set(baseline.research.external_request_ids)
    hits = {}
    for index, request in enumerate(baseline.research.requests, start=1):
        if request.request_id not in external_ids:
            continue
        source_type = request.acceptable_source_types[0]
        hits[request.request_id] = [
            RawResearchHit(
                source=f"Source {index}",
                source_type=source_type,
                source_ref=f"https://example.test/{request.request_id}",
                excerpt=f"Sourced observation for {request.claim_id}.",
                stance=EvidenceStance.SUPPORTS,
                confidence=0.85,
            )
        ]
    return baseline, hits


def _fake_hits_for_all_router_requests(seed: str):
    baseline = run_phase1_forge(seed)
    hits = {}
    for index, request in enumerate(baseline.research.requests, start=1):
        hits[request.request_id] = [
            RawResearchHit(
                source=f"Local source {index}",
                source_type="web/public source",
                source_ref=f"https://example.test/live/{request.request_id}",
                excerpt=f"Directly relevant sourced observation {index}.",
                stance=EvidenceStance.SUPPORTS,
                confidence=0.85,
            )
        ]
    return baseline, hits


def test_runner_starts_from_one_seed_and_is_zero_paid_call_by_default():
    result = run_mind_forge("محل شاي في نامسوس")

    assert result.seed == "محل شاي في نامسوس"
    assert result.live_research_requested is False
    assert result.research is None
    assert result.run_contract == result.baseline.run_contract
    assert len(result.run_contract.ideas) == 14
    assert len(result.run_contract.expert_outputs) == 10


def test_runner_live_research_requires_explicit_enabled_policy():
    with pytest.raises(RuntimeError, match="explicitly enabled ResearchPolicy"):
        run_mind_forge(
            "محل شاي في نامسوس",
            live_research=True,
            research_executor=FakeResearchExecutor(),
        )


def test_runner_rebuilds_evidence_decision_experiment_memory_after_fake_research():
    seed = "محل شاي في نامسوس"
    baseline, hits = _fake_hits_for_external_requests(seed)
    result = run_mind_forge(
        seed,
        live_research=True,
        research_policy=ResearchPolicy(
            enabled=True,
            max_search_operations=4,
            max_estimated_cost_usd=0.05,
        ),
        research_executor=FakeResearchExecutor(hits),
    )

    assert result.research is not None
    assert result.research.live_executor_used is False
    assert set(result.research.executed_request_ids) == set(baseline.research.external_request_ids)
    assert result.research.usage.search_operations == len(baseline.research.external_request_ids)
    assert result.run_contract.evidence == result.evidence_engine.evidence
    assert result.run_contract.decision == result.decision_engine.decision
    assert result.run_contract.experiments == result.experiment_engine.experiments
    assert result.run_contract.memory_records == result.memory_engine.records

    live_refs = {item.source_ref for item in result.research.observations}
    live_evidence = [item for item in result.run_contract.evidence if item.source_ref in live_refs]
    assert live_evidence
    assert all(item.classification is not EvidenceClassification.VERIFIED_FACT for item in live_evidence)
    assert all(item.source and item.source_type and item.source_ref for item in live_evidence)


def test_two_search_budget_is_split_across_two_router_requests():
    seed = "محل شاي في نامسوس"
    baseline, hits = _fake_hits_for_external_requests(seed)
    assert len(baseline.research.external_request_ids) == 2

    policy = _cli_research_policy(
        model="gpt-5.6-luna",
        max_search_operations=2,
        max_research_cost_usd=0.02,
    )
    assert policy.max_operations_per_request == 1

    result = run_mind_forge(
        seed,
        live_research=True,
        research_policy=policy,
        research_executor=FakeResearchExecutor(hits),
    )

    assert result.research is not None
    assert set(result.research.executed_request_ids) == set(baseline.research.external_request_ids)
    assert result.research.usage.search_operations == 2
    assert result.research.usage.estimated_cost_usd == 0.02


def test_resilient_six_search_budget_uses_six_distinct_market_questions_with_one_search_each():
    seed = "محل شاي في نامسوس"
    baseline, hits = _fake_hits_for_all_router_requests(seed)
    assert len(baseline.research.requests) == 6
    assert len(baseline.research.external_request_ids) == 2

    policy = resilient_cli_research_policy(
        model="gpt-5.6-luna",
        max_search_operations=6,
        max_research_cost_usd=0.07,
    )
    assert policy.max_operations_per_request == 1
    assert policy.max_output_tokens == 1600
    assert policy.max_results_per_request == 2

    result = resilient_run_mind_forge(
        seed,
        live_research=True,
        research_policy=policy,
        research_executor=FakeResearchExecutor(hits),
    )

    assert result.research is not None
    assert len(result.research.executed_request_ids) == 6
    assert len(set(result.research.executed_request_ids)) == 6
    assert result.research.skipped_request_ids == []
    assert result.research.usage.search_operations == 6
    assert result.research.usage.estimated_cost_usd == 0.06
    assert result.research.usage.estimated_cost_usd <= 0.07

    summary = resilient_build_runner_summary(result)
    assert summary["research_executed_request_count"] == 6
    assert summary["live_external_request_count"] == 6
    assert summary["research_usage"]["search_operations"] == 6


def test_resilient_source_quality_gate_rejects_neutral_and_generic_market_sources():
    seed = "محل شاي في نامسوس"
    baseline, hits = _fake_hits_for_all_router_requests(seed)
    request_ids = [request.request_id for request in baseline.research.requests]

    bad_neutral_ref = "https://www.booking.com/hotel/no/gullvikvegen-33.ar.html"
    good_ssb_ref = "https://www.ssb.no/kommunefakta/namsos-naavmesjenjaelmie"
    hits[request_ids[0]] = [
        RawResearchHit(
            source="Booking listing",
            source_type="web/public source",
            source_ref=bad_neutral_ref,
            excerpt="A lodging page that does not establish tea-shop demand.",
            stance=EvidenceStance.NEUTRAL,
            confidence=0.90,
        ),
        RawResearchHit(
            source="SSB Namsos",
            source_type="web/public source",
            source_ref=good_ssb_ref,
            excerpt="Official Namsos municipality statistics relevant to the customer base.",
            stance=EvidenceStance.MIXED,
            confidence=0.90,
        ),
    ]

    bad_aggregator_ref = "https://www.toasttab.com/local/order/example-tea"
    good_local_ref = "https://thonsenter.no/namsos/butikker/mat-og-drikke/kafe/"
    hits[request_ids[1]] = [
        RawResearchHit(
            source="Generic ordering page",
            source_type="web/public source",
            source_ref=bad_aggregator_ref,
            excerpt="A tea ordering page outside the target market.",
            stance=EvidenceStance.SUPPORTS,
            confidence=0.90,
        ),
        RawResearchHit(
            source="Thon Senter Namsos cafes",
            source_type="local business listing",
            source_ref=good_local_ref,
            excerpt="Current local cafe alternatives in Namsos.",
            stance=EvidenceStance.SUPPORTS,
            confidence=0.88,
        ),
    ]

    policy = resilient_cli_research_policy(
        model="gpt-5.6-luna",
        max_search_operations=6,
        max_research_cost_usd=0.07,
    )
    result = resilient_run_mind_forge(
        seed,
        live_research=True,
        research_policy=policy,
        research_executor=FakeResearchExecutor(hits),
    )

    summary = resilient_build_runner_summary(result)
    accepted_refs = {item["source_ref"] for item in summary["live_sources"]}
    evidence_refs = {item.source_ref for item in result.run_contract.evidence if item.source_ref}

    assert bad_neutral_ref not in accepted_refs
    assert bad_aggregator_ref not in accepted_refs
    assert bad_neutral_ref not in evidence_refs
    assert bad_aggregator_ref not in evidence_refs
    assert good_ssb_ref in accepted_refs
    assert good_local_ref in accepted_refs
    assert summary["source_quality_rejected_count"] == 2
    assert summary["source_quality_accepted_count"] == len(summary["live_sources"])
    assert result.research is not None
    assert result.research.usage.search_operations == 6
    assert result.research.usage.estimated_cost_usd == 0.06


def test_resilient_cli_four_search_budget_uses_one_operation_per_request():
    policy = resilient_cli_research_policy(
        model="gpt-5.6-luna",
        max_search_operations=4,
        max_research_cost_usd=0.05,
    )
    assert policy.max_operations_per_request == 1
    assert policy.max_output_tokens == 1600
    assert policy.max_results_per_request == 2


def test_runner_summary_exposes_research_budget_sources_and_final_decision():
    seed = "محل شاي في نامسوس"
    _, hits = _fake_hits_for_external_requests(seed)
    result = run_mind_forge(
        seed,
        live_research=True,
        research_policy=ResearchPolicy(
            enabled=True,
            max_search_operations=4,
            max_estimated_cost_usd=0.05,
        ),
        research_executor=FakeResearchExecutor(hits),
    )
    summary = build_runner_summary(result)

    assert summary["status"] == "MIND_FORGE_RUN_COMPLETE"
    assert summary["seed"] == seed
    assert summary["idea_count"] == 14
    assert summary["expert_mind_count"] == 10
    assert summary["live_research_requested"] is True
    assert summary["research_usage"]["search_operations"] > 0
    assert summary["research_usage"]["estimated_cost_usd"] <= 0.05
    assert summary["live_sources"]
    assert summary["decision_verdict"] == result.decision_engine.decision.verdict.value


def test_cli_free_mode_accepts_only_the_seed_and_prints_summary(capsys):
    assert main(["محل شاي في نامسوس"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["seed"] == "محل شاي في نامسوس"
    assert payload["live_research_requested"] is False
    assert payload["research_usage"]["search_operations"] == 0


def test_cli_refuses_paid_live_research_without_explicit_yes(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(SystemExit) as exc:
        main(["محل شاي في نامسوس", "--live-research"])
    assert exc.value.code == 2


def test_manual_live_research_workflow_runs_through_runner_v1_only_after_yes():
    text = Path(".github/workflows/mind-forge-live-research-v1.yaml").read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert 'default: "NO"' in text
    assert "if: ${{ inputs.confirm_paid_live_research == 'YES' }}" in text
    assert "runner_v1.py" in text
    assert "python -m mind_forge.runner_v1" in text
    assert "--live-research" in text
    assert "--confirm-paid-live-research YES" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "\n  schedule:" not in text
