from pathlib import Path

from mind_forge.contracts_v1 import EvidenceStance
from mind_forge.live_research_adapter_v1 import FakeResearchExecutor, RawResearchHit
from mind_forge.pipeline_v1 import run_phase1_forge
from mind_forge.runner_v1_geographic import (
    geographic_build_runner_summary,
    geographic_run_mind_forge,
)
from mind_forge.runner_v1_resilient import resilient_cli_research_policy


WORKFLOW = Path(".github/workflows/mind-forge-live-model-v1.yaml")


def _expanded_request_order(baseline):
    selected_ids = list(baseline.research.external_request_ids)
    user_ids = set(baseline.research.user_request_ids)
    for request in baseline.research.requests:
        if request.request_id in selected_ids or request.request_id in user_ids:
            continue
        selected_ids.append(request.request_id)
    return selected_ids


def _all_request_hits(seed: str):
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


def test_live_model_workflow_is_manual_only_and_explicitly_authorized():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "confirm_paid_live_run:" in text
    assert "if: ${{ inputs.confirm_paid_live_run == 'YES' }}" in text
    assert "default: \"NO\"" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "\n  schedule:" not in text


def test_live_model_workflow_reuses_existing_secret_without_exposing_value():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}" in text
    assert "value not displayed" in text
    assert "MIND_FORGE_LIVE_ENABLED: \"1\"" in text
    assert "sk-" not in text


def test_live_model_workflow_has_budget_and_model_gates():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "max_estimated_cost_usd:" in text
    assert 'default: "0.10"' in text
    assert "if int(usage[\"requests\"]) > 11:" in text
    assert "gpt-5.6-terra" in text
    assert "gpt-5.6-luna" in text
    assert "live_research_enabled\"] is not False" in text


def test_geographic_gate_rejects_foreign_regulation_for_namsos_and_keeps_norway():
    seed = "محل شاي في نامسوس"
    baseline, hits = _all_request_hits(seed)
    regulation_id = _expanded_request_order(baseline)[4]

    foreign_ref = "https://www.wallonie.be/en/demarches/horeca-certificate"
    mattilsynet_ref = "https://www.mattilsynet.no/mat-og-drikke/matservering"
    hits[regulation_id] = [
        RawResearchHit(
            source="Wallonia HORECA rules",
            source_type="government publication",
            source_ref=foreign_ref,
            excerpt="Belgian regional HORECA requirements.",
            stance=EvidenceStance.MIXED,
            confidence=0.90,
        ),
        RawResearchHit(
            source="Mattilsynet food service guidance",
            source_type="official regulator guidance",
            source_ref=mattilsynet_ref,
            excerpt="Norwegian food-service requirements applicable to a Namsos pilot.",
            stance=EvidenceStance.SUPPORTS,
            confidence=0.90,
        ),
    ]

    policy = resilient_cli_research_policy(
        model="gpt-5.6-luna",
        max_search_operations=6,
        max_research_cost_usd=0.07,
    )
    result = geographic_run_mind_forge(
        seed,
        live_research=True,
        research_policy=policy,
        research_executor=FakeResearchExecutor(hits),
    )
    summary = geographic_build_runner_summary(result)

    accepted_refs = {item["source_ref"] for item in summary["live_sources"]}
    evidence_refs = {item.source_ref for item in result.run_contract.evidence if item.source_ref}
    coverage = {item["label"]: item for item in summary["research_question_coverage"]}

    assert foreign_ref not in accepted_refs
    assert foreign_ref not in evidence_refs
    assert mattilsynet_ref in accepted_refs
    assert mattilsynet_ref in evidence_refs
    assert coverage["regulation"]["status"] == "COVERED"
    assert coverage["regulation"]["accepted_source_count"] == 1
    assert coverage["regulation"]["rejected_observation_count"] == 1
    assert summary["geographic_relevance_rejected_count"] == 1


def test_semantic_gate_rejects_local_but_irrelevant_pricing_page_and_keeps_menu_price_evidence():
    seed = "محل شاي في نامسوس"
    baseline, hits = _all_request_hits(seed)
    pricing_id = _expanded_request_order(baseline)[3]

    irrelevant_ref = (
        "https://namsos.kommune.no/kultur-idrett-og-fritid/"
        "lokta-og-melkrampa/melkrampa/2025/mai/frivilligsentralen/"
    )
    menu_ref = "https://kruscoffee.no/meny"
    hits[pricing_id] = [
        RawResearchHit(
            source="Namsos Frivilligsentralen",
            source_type="web/public source",
            source_ref=irrelevant_ref,
            excerpt="Community volunteer-center activities and local events in Namsos.",
            stance=EvidenceStance.SUPPORTS,
            confidence=0.90,
        ),
        RawResearchHit(
            source="Krus Coffee menu",
            source_type="public menu or price list",
            source_ref=menu_ref,
            excerpt="The current menu lists tea at 49 NOK and coffee at 45 NOK.",
            stance=EvidenceStance.SUPPORTS,
            confidence=0.90,
        ),
    ]

    policy = resilient_cli_research_policy(
        model="gpt-5.6-luna",
        max_search_operations=6,
        max_research_cost_usd=0.07,
    )
    result = geographic_run_mind_forge(
        seed,
        live_research=True,
        research_policy=policy,
        research_executor=FakeResearchExecutor(hits),
    )
    summary = geographic_build_runner_summary(result)

    accepted_refs = {item["source_ref"] for item in summary["live_sources"]}
    evidence_refs = {item.source_ref for item in result.run_contract.evidence if item.source_ref}
    coverage = {item["label"]: item for item in summary["research_question_coverage"]}

    assert irrelevant_ref not in accepted_refs
    assert irrelevant_ref not in evidence_refs
    assert menu_ref in accepted_refs
    assert menu_ref in evidence_refs
    assert coverage["pricing and economics"]["status"] == "COVERED"
    assert coverage["pricing and economics"]["accepted_source_count"] == 1
    assert coverage["pricing and economics"]["rejected_observation_count"] == 1
    assert summary["semantic_relevance_rejected_count"] == 1
