from __future__ import annotations

from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from . import schemas as v110
from .contracts_v1 import (
    Evidence as ContractEvidence,
    EvidenceClassification,
    EvidenceStance,
    ExpertMindOutput,
    Idea as ContractIdea,
    RunContract,
    TopicInput,
)


class BridgeGap(BaseModel):
    """A semantic mismatch that must not be hidden by an invented conversion."""

    model_config = ConfigDict(extra="forbid")

    contract_object: str = Field(min_length=1)
    legacy_source: str = Field(min_length=1)
    severity: Literal["INFO", "PARTIAL", "NEW_COMPONENT_REQUIRED"]
    reason: str = Field(min_length=1)


class V110BridgeSnapshot(BaseModel):
    """Lossless/defensible Phase 1 view over a frozen V1.10.1 ForgeResult.

    Objects that cannot be mapped without changing meaning remain absent from the
    canonical RunContract and are listed in gaps instead.
    """

    model_config = ConfigDict(extra="forbid")

    run: RunContract
    gaps: list[BridgeGap] = Field(default_factory=list)
    legacy_engine_version: str
    legacy_selected_idea: str
    legacy_verdict: str


def _stable_id(prefix: str, *parts: str) -> str:
    material = "\x1f".join(part.strip().casefold() for part in parts)
    digest = sha256(material.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _title_to_id(ideas: list[ContractIdea]) -> dict[str, str]:
    return {idea.title.strip().casefold(): idea.idea_id for idea in ideas}


def legacy_idea_set_to_contracts(idea_set: v110.IdeaSet) -> tuple[list[ContractIdea], list[BridgeGap]]:
    """Map the fields that have the same semantics; report the legacy upside gap."""

    converted: list[ContractIdea] = []
    gaps: list[BridgeGap] = []
    for item in idea_set.ideas:
        converted.append(
            ContractIdea(
                idea_id=_stable_id("idea", item.title),
                title=item.title,
                core_mechanism=item.mechanism,
                business_value=item.thesis,
                risks=[item.main_risk],
            )
        )
        gaps.append(
            BridgeGap(
                contract_object=f"Idea[{item.title}].upside",
                legacy_source="Idea.upside",
                severity="PARTIAL",
                reason=(
                    "The Phase 1 Idea contract has no field with exactly the same semantics as "
                    "V1.10.1 Idea.upside, so the value is not silently moved into a different field."
                ),
            )
        )
    return converted, gaps


def legacy_council_to_contracts(
    council: v110.CouncilReport,
    ideas: list[ContractIdea],
) -> tuple[list[ExpertMindOutput], list[BridgeGap]]:
    """Convert only ACTIVE/MOCK opinions; never fabricate skipped-budget opinions."""

    title_ids = _title_to_id(ideas)
    all_ids = [idea.idea_id for idea in ideas]
    converted: list[ExpertMindOutput] = []
    gaps: list[BridgeGap] = []

    for review in council.reviews:
        if review.opinion is None:
            gaps.append(
                BridgeGap(
                    contract_object=f"ExpertMindOutput[{review.expert_id}]",
                    legacy_source=f"ExpertReview[{review.expert_id}]",
                    severity="PARTIAL",
                    reason=(
                        "V1.10.1 marked this expert SKIPPED_BUDGET and contains no opinion; "
                        "the bridge will not fabricate one."
                    ),
                )
            )
            continue

        preferred_ids: list[str] = []
        unknown_titles: list[str] = []
        for title in review.opinion.preferred_ideas:
            idea_id = title_ids.get(title.strip().casefold())
            if idea_id is None:
                unknown_titles.append(title)
            else:
                preferred_ids.append(idea_id)

        if unknown_titles or not preferred_ids:
            gaps.append(
                BridgeGap(
                    contract_object=f"ExpertMindOutput[{review.expert_id}]",
                    legacy_source=f"ExpertReview[{review.expert_id}].opinion.preferred_ideas",
                    severity="PARTIAL",
                    reason=(
                        "Preferred ideas could not be resolved exactly to canonical idea IDs: "
                        + ", ".join(unknown_titles or review.opinion.preferred_ideas)
                    ),
                )
            )
            continue

        converted.append(
            ExpertMindOutput(
                mind_id=review.expert_id,
                lens=review.lens,
                assessed_idea_ids=all_ids,
                strongest_idea_id=preferred_ids[0],
                independent_reasoning=[review.opinion.recommendation, review.opinion.strongest_point],
                assumptions=list(review.opinion.hidden_assumptions),
                objections=[review.opinion.weakest_point],
                evidence_that_changes_view=list(review.opinion.missing_variables),
                support_scores={},
            )
        )

    return converted, gaps


def legacy_evidence_to_contracts(
    report: v110.EvidenceReport,
) -> tuple[list[ContractEvidence], list[BridgeGap]]:
    """Translate only classifications with a defensible Phase 1 equivalent.

    HYPOTHESIS and basis-free CONTRADICTION are intentionally left as gaps rather
    than being mislabeled as assumptions, estimates, facts, or sourced conflict.
    """

    converted: list[ContractEvidence] = []
    gaps: list[BridgeGap] = []
    report_confidence = report.confidence / 100.0

    for index, item in enumerate(report.items, start=1):
        legacy_class = item.classification
        classification: EvidenceClassification | None = None
        stance = EvidenceStance.NEUTRAL
        source: str | None = None
        source_type: str | None = None
        source_ref: str | None = None
        confidence = report_confidence
        contradiction_notes: list[str] = []

        if legacy_class is v110.EvidenceClass.FACT:
            classification = EvidenceClassification.VERIFIED_FACT
            source_ref = " | ".join(item.basis)
            source = source_ref
            source_type = "v1.10.1_internal_basis"
        elif legacy_class is v110.EvidenceClass.SUPPORTED:
            classification = EvidenceClassification.STRONG_EVIDENCE
            source_ref = " | ".join(item.basis)
            source = source_ref
            source_type = "v1.10.1_internal_basis"
        elif legacy_class is v110.EvidenceClass.ASSUMPTION:
            classification = EvidenceClassification.ASSUMPTION
            confidence = min(confidence, 0.5)
        elif legacy_class is v110.EvidenceClass.UNKNOWN:
            classification = EvidenceClassification.UNKNOWN
            confidence = min(confidence, 0.5)
        elif legacy_class is v110.EvidenceClass.CONTRADICTION and item.basis:
            classification = EvidenceClassification.CONFLICTING_EVIDENCE
            stance = EvidenceStance.MIXED
            source_ref = " | ".join(item.basis)
            source = source_ref
            source_type = "v1.10.1_internal_basis"
            contradiction_notes = [item.claim]
        else:
            gaps.append(
                BridgeGap(
                    contract_object=f"Evidence[{index}]",
                    legacy_source=f"EvidenceItem.{legacy_class.name}",
                    severity="PARTIAL",
                    reason=(
                        "No lossless Phase 1 evidence classification/provenance mapping exists for "
                        f"{legacy_class.value}; the item is preserved as a compatibility gap instead of relabeled."
                    ),
                )
            )
            continue

        converted.append(
            ContractEvidence(
                evidence_id=_stable_id("evidence", str(index), item.claim),
                claim_id=_stable_id("claim", item.claim),
                claim_text=item.claim,
                classification=classification,
                stance=stance,
                source=source,
                source_type=source_type,
                source_ref=source_ref,
                confidence=confidence,
                contradiction_notes=contradiction_notes,
            )
        )

    return converted, gaps


def static_v110_gaps() -> list[BridgeGap]:
    """Known schema gaps discovered by probing the frozen V1.10.1 runtime."""

    return [
        BridgeGap(
            contract_object="Question",
            legacy_source="No V1.10.1 schema",
            severity="NEW_COMPONENT_REQUIRED",
            reason="V1.10.1 starts from a supplied question and has no first-class Question object or adaptive question policy.",
        ),
        BridgeGap(
            contract_object="Critique",
            legacy_source="CrossCritique + DevilsAdvocateReport",
            severity="PARTIAL",
            reason=(
                "V1.10.1 has aggregate cross-critique and failure modes, but not a per-idea critique containing both "
                "a falsification test and a low-cost test."
            ),
        ),
        BridgeGap(
            contract_object="Decision",
            legacy_source="Decision",
            severity="PARTIAL",
            reason=(
                "V1.10.1 selects exactly one idea and uses PROMOTE/TEST/MODIFY/HOLD/REJECT; the Phase 1 contract can "
                "select up to three and has different action semantics. Automatic relabeling would change meaning."
            ),
        ),
        BridgeGap(
            contract_object="Experiment",
            legacy_source="ExperimentPlan",
            severity="PARTIAL",
            reason=(
                "V1.10.1 has duration, sample, string thresholds, pass/stop conditions, but no experiment cost ceiling and "
                "no lossless numeric threshold/direction fields required by the Phase 1 Experiment contract."
            ),
        ),
        BridgeGap(
            contract_object="MemoryRecord",
            legacy_source="LearningSignal",
            severity="NEW_COMPONENT_REQUIRED",
            reason=(
                "V1.10.1 LearningSignal calibrates expert reliability; it is not persistent episodic/semantic memory and "
                "must not be relabeled as MemoryRecord."
            ),
        ),
    ]


def build_v110_bridge_snapshot(topic: TopicInput, result: v110.ForgeResult) -> V110BridgeSnapshot:
    """Build a canonical Phase 1 view without modifying the V1.10.1 result."""

    ideas, idea_gaps = legacy_idea_set_to_contracts(result.ideas)
    expert_outputs, expert_gaps = legacy_council_to_contracts(result.council, ideas)
    evidence, evidence_gaps = legacy_evidence_to_contracts(result.evidence)

    run_id = result.run_id or _stable_id(
        "run",
        topic.topic,
        result.decision.selected_idea,
        result.decision.verdict.value,
    )

    run = RunContract(
        run_id=run_id,
        topic=topic,
        questions=[],
        ideas=ideas,
        expert_outputs=expert_outputs,
        critiques=[],
        evidence=evidence,
        decision=None,
        experiments=[],
        memory_records=[],
    )

    return V110BridgeSnapshot(
        run=run,
        gaps=static_v110_gaps() + idea_gaps + expert_gaps + evidence_gaps,
        legacy_engine_version=result.engine_version,
        legacy_selected_idea=result.decision.selected_idea,
        legacy_verdict=result.decision.verdict.value,
    )
