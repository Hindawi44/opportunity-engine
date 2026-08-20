from __future__ import annotations

import asyncio

from mind_forge.bridge_v110 import build_v110_bridge_snapshot
from mind_forge.contracts_v1 import EvidenceClassification, TopicInput
from mind_forge.orchestrator import run_mock_forge


def test_frozen_v110_mock_can_be_viewed_through_phase1_contracts_without_mutation() -> None:
    legacy = asyncio.run(run_mock_forge("تصليح الملابس"))
    before = legacy.model_dump(mode="json")

    snapshot = build_v110_bridge_snapshot(
        TopicInput(topic="تصليح الملابس"),
        legacy,
    )

    assert legacy.model_dump(mode="json") == before
    assert legacy.engine_version == "0.10.0"
    assert legacy.decision.selected_idea == "Standardized service menu"
    assert legacy.decision.verdict.value == "TEST"

    assert snapshot.run.topic.topic == "تصليح الملابس"
    assert len(snapshot.run.ideas) == 3
    assert len(snapshot.run.expert_outputs) == 10
    assert len({output.mind_id for output in snapshot.run.expert_outputs}) == 10
    assert len({output.lens for output in snapshot.run.expert_outputs}) == 10

    classifications = {item.classification for item in snapshot.run.evidence}
    assert EvidenceClassification.VERIFIED_FACT in classifications
    assert EvidenceClassification.UNKNOWN in classifications

    # Do not invent a Phase 1 decision/experiment/question/memory object where
    # V1.10.1 does not provide the same semantics.
    assert snapshot.run.questions == []
    assert snapshot.run.decision is None
    assert snapshot.run.experiments == []
    assert snapshot.run.memory_records == []

    gap_objects = {gap.contract_object for gap in snapshot.gaps}
    assert "Question" in gap_objects
    assert "Critique" in gap_objects
    assert "Decision" in gap_objects
    assert "Experiment" in gap_objects
    assert "MemoryRecord" in gap_objects

    # V1.10.1 mock evidence contains two HYPOTHESIS items. The current Phase 1
    # evidence enum has no exact HYPOTHESIS value, so they must remain explicit
    # gaps rather than being silently relabeled as facts or assumptions.
    hypothesis_gaps = [
        gap for gap in snapshot.gaps
        if gap.legacy_source == "EvidenceItem.HYPOTHESIS"
    ]
    assert len(hypothesis_gaps) == 2


def test_v110_fact_keeps_explicit_internal_basis() -> None:
    legacy = asyncio.run(run_mock_forge("تصليح الملابس"))
    snapshot = build_v110_bridge_snapshot(TopicInput(topic="تصليح الملابس"), legacy)

    fact = next(
        item for item in snapshot.run.evidence
        if item.classification is EvidenceClassification.VERIFIED_FACT
    )
    assert fact.source_type == "v1.10.1_internal_basis"
    assert fact.source == "problem.known_facts"
    assert fact.source_ref == "problem.known_facts"
