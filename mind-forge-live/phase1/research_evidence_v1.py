from __future__ import annotations

from enum import Enum
from hashlib import sha256
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts_v1 import (
    CritiqueDisposition,
    Evidence,
    EvidenceClassification,
    EvidenceStance,
)
from .creative_engine_v1 import CreativeEngineResult
from .critique_engine_v1 import CritiqueEngineResult
from .logic_engine_v1 import LogicEngineResult


class ResearchRoute(str, Enum):
    WEB = "WEB"
    PUBLIC_DATA = "PUBLIC_DATA"
    CALCULATOR = "CALCULATOR"
    USER = "USER"
    EXPERIMENT = "EXPERIMENT"


class ResearchStatus(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    DEFERRED = "DEFERRED"


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    idea_id: str = Field(min_length=1)
    claim_text: str = Field(min_length=1)
    why_material: str = Field(min_length=1)
    route: ResearchRoute
    expected_decision_impact: float = Field(ge=0.0, le=1.0)
    acceptable_source_types: list[str] = Field(default_factory=list)
    status: ResearchStatus = ResearchStatus.OPEN

    @model_validator(mode="after")
    def validate_route_contract(self) -> "ResearchRequest":
        if self.route in {ResearchRoute.WEB, ResearchRoute.PUBLIC_DATA} and not self.acceptable_source_types:
            raise ValueError("external research routes require acceptable_source_types")
        if self.expected_decision_impact < 0.5:
            raise ValueError("Research Router may only open material requests with decision impact >= 0.5")
        return self


class ResearchRouterResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_idea_ids: list[str] = Field(min_length=1)
    requests: list[ResearchRequest] = Field(default_factory=list)
    external_request_ids: list[str] = Field(default_factory=list)
    experiment_request_ids: list[str] = Field(default_factory=list)
    user_request_ids: list[str] = Field(default_factory=list)
    max_requests_per_idea: int = Field(default=1, ge=1, le=3)

    @model_validator(mode="after")
    def validate_partition(self) -> "ResearchRouterResult":
        ids = [item.request_id for item in self.requests]
        if len(ids) != len(set(ids)):
            raise ValueError("research request IDs must be unique")
        known = set(ids)
        external = set(self.external_request_ids)
        experiment = set(self.experiment_request_ids)
        user = set(self.user_request_ids)
        if external & experiment or external & user or experiment & user:
            raise ValueError("research route partitions must be disjoint")
        if external | experiment | user != known:
            raise ValueError("research route partitions must cover every request")
        by_idea: dict[str, int] = {}
        for item in self.requests:
            by_idea[item.idea_id] = by_idea.get(item.idea_id, 0) + 1
            if by_idea[item.idea_id] > self.max_requests_per_idea:
                raise ValueError("research request budget exceeded for an idea")
        if not set(by_idea).issubset(set(self.candidate_idea_ids)):
            raise ValueError("research request references an idea outside candidate_idea_ids")
        return self


class EvidenceObservation(BaseModel):
    """Normalized observation returned by a future tool/research adapter.

    The Evidence Engine does not fetch in Phase 1 CI. It validates whatever a future
    web/public-data/calculator adapter returns and refuses to upgrade unsupported
    claims into sourced evidence.
    """

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1)
    source: str | None = None
    source_type: str | None = None
    source_ref: str | None = None
    classification: EvidenceClassification
    stance: EvidenceStance = EvidenceStance.NEUTRAL
    confidence: float = Field(ge=0.0, le=1.0)
    contradiction_notes: list[str] = Field(default_factory=list)


class EvidenceEngineResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence: list[Evidence] = Field(default_factory=list)
    resolved_request_ids: list[str] = Field(default_factory=list)
    unresolved_request_ids: list[str] = Field(default_factory=list)
    conflicting_claim_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_resolution(self) -> "EvidenceEngineResult":
        resolved = set(self.resolved_request_ids)
        unresolved = set(self.unresolved_request_ids)
        if resolved & unresolved:
            raise ValueError("a research request cannot be both resolved and unresolved")
        evidence_request_ids = {
            item.source_ref.removeprefix("research-request:")
            for item in self.evidence
            if item.source_ref and item.source_ref.startswith("research-request:")
        }
        if not evidence_request_ids.issubset(resolved | unresolved):
            raise ValueError("evidence references a research request absent from resolution partitions")
        return self


def _stable_request_id(idea_id: str, claim_text: str) -> str:
    digest = sha256(f"{idea_id}\x1f{claim_text}".encode("utf-8")).hexdigest()[:14]
    return f"research-{digest}"


def _route_for_family(family: str, disposition: CritiqueDisposition) -> tuple[ResearchRoute, list[str]]:
    # Prefer real-world experiments when the uncertainty is operational and can be
    # exposed cheaply. Use external research only where market/channel facts are more
    # decision-relevant than an internal pilot.
    if family in {"bottleneck_redesign", "standardization", "automation_intake", "data_feedback"}:
        return ResearchRoute.EXPERIMENT, []
    if family in {"premium_speed", "adjacent_bundle"}:
        return ResearchRoute.WEB, ["primary market data", "credible industry data", "direct competitor/public offer"]
    if disposition is CritiqueDisposition.NEEDS_EVIDENCE:
        return ResearchRoute.PUBLIC_DATA, ["official statistics", "primary public dataset"]
    return ResearchRoute.EXPERIMENT, []


def _impact(disposition: CritiqueDisposition, evidence_debt: float) -> float:
    base = {
        CritiqueDisposition.REJECT: 1.00,
        CritiqueDisposition.REWORK: 0.86,
        CritiqueDisposition.NEEDS_EVIDENCE: 0.92,
        CritiqueDisposition.SURVIVES: 0.58,
    }[disposition]
    return round(min(1.0, base + 0.08 * evidence_debt), 4)


def route_research(
    creative: CreativeEngineResult,
    logic: LogicEngineResult,
    critique: CritiqueEngineResult,
    *,
    max_requests_per_idea: int = 1,
) -> ResearchRouterResult:
    """Route only decision-material unresolved claims from Logic survivors.

    One bounded request per idea is the Phase 1 default. The router deliberately
    prefers EXPERIMENT for cheap operational uncertainties and WEB/PUBLIC_DATA only
    when external evidence can change the decision more efficiently.
    """

    if max_requests_per_idea < 1 or max_requests_per_idea > 3:
        raise ValueError("max_requests_per_idea must be between 1 and 3")

    ideas_by_id = {idea.idea_id: idea for idea in creative.ideas}
    logic_by_id = {item.idea_id: item for item in logic.assessments}
    critique_by_id = {item.idea_id: item for item in critique.critiques}
    candidate_ids = list(critique.critiqued_idea_ids)

    if not set(candidate_ids).issubset(set(logic.survivor_idea_ids)):
        raise ValueError("Research Router may only receive ideas that survived Logic")

    requests: list[ResearchRequest] = []
    external_ids: list[str] = []
    experiment_ids: list[str] = []
    user_ids: list[str] = []

    for idea_id in candidate_ids:
        idea = ideas_by_id[idea_id]
        logic_item = logic_by_id[idea_id]
        critique_item = critique_by_id[idea_id]

        # SURVIVES items with low evidence debt stay test-first; REWORK and
        # NEEDS_EVIDENCE are always material enough to route.
        impact = _impact(critique_item.disposition, logic_item.evidence_debt)
        if impact < 0.60:
            continue

        claim_text = (
            idea.assumptions[0]
            if idea.assumptions
            else critique_item.failure_modes[0]
        )
        route, source_types = _route_for_family(
            logic_item.mechanism_family,
            critique_item.disposition,
        )
        request_id = _stable_request_id(idea_id, claim_text)
        request = ResearchRequest(
            request_id=request_id,
            claim_id=f"claim-{request_id}",
            idea_id=idea_id,
            claim_text=claim_text,
            why_material=(
                f"Resolving this claim can change the {critique_item.disposition.value} pre-evidence disposition "
                f"for the {logic_item.mechanism_family} mechanism; current evidence debt is {logic_item.evidence_debt:.2f}."
            ),
            route=route,
            expected_decision_impact=impact,
            acceptable_source_types=source_types,
        )
        requests.append(request)
        if route in {ResearchRoute.WEB, ResearchRoute.PUBLIC_DATA, ResearchRoute.CALCULATOR}:
            external_ids.append(request_id)
        elif route is ResearchRoute.EXPERIMENT:
            experiment_ids.append(request_id)
        else:
            user_ids.append(request_id)

    return ResearchRouterResult(
        candidate_idea_ids=candidate_ids,
        requests=requests,
        external_request_ids=external_ids,
        experiment_request_ids=experiment_ids,
        user_request_ids=user_ids,
        max_requests_per_idea=max_requests_per_idea,
    )


def _placeholder_evidence(request: ResearchRequest) -> Evidence:
    classification = (
        EvidenceClassification.ASSUMPTION
        if request.route in {ResearchRoute.EXPERIMENT, ResearchRoute.USER}
        else EvidenceClassification.UNKNOWN
    )
    confidence = 0.35 if classification is EvidenceClassification.ASSUMPTION else 0.20
    return Evidence(
        evidence_id=f"evidence-{request.request_id}-unresolved",
        claim_id=request.claim_id,
        claim_text=request.claim_text,
        idea_id=request.idea_id,
        classification=classification,
        stance=EvidenceStance.NEUTRAL,
        source=None,
        source_type=None,
        source_ref=f"research-request:{request.request_id}",
        confidence=confidence,
        contradiction_notes=[],
    )


def build_evidence(
    router: ResearchRouterResult,
    observations: Iterable[EvidenceObservation] = (),
) -> EvidenceEngineResult:
    """Convert research observations into canonical Evidence, fail-closed.

    Missing observations remain ASSUMPTION/UNKNOWN. Sourced classifications still
    pass through the canonical Evidence provenance validator, so VERIFIED/STRONG/
    WEAK/CONFLICTING cannot be created without source + source_type.
    """

    requests = {item.request_id: item for item in router.requests}
    obs_by_request: dict[str, EvidenceObservation] = {}
    for observation in observations:
        if observation.request_id not in requests:
            raise ValueError(f"observation references unknown research request {observation.request_id}")
        if observation.request_id in obs_by_request:
            raise ValueError(f"duplicate observation for research request {observation.request_id}")
        obs_by_request[observation.request_id] = observation

    evidence: list[Evidence] = []
    resolved: list[str] = []
    unresolved: list[str] = []
    conflicting_claim_ids: list[str] = []

    for request in router.requests:
        observation = obs_by_request.get(request.request_id)
        if observation is None:
            evidence.append(_placeholder_evidence(request))
            unresolved.append(request.request_id)
            continue

        item = Evidence(
            evidence_id=f"evidence-{request.request_id}",
            claim_id=request.claim_id,
            claim_text=request.claim_text,
            idea_id=request.idea_id,
            classification=observation.classification,
            stance=observation.stance,
            source=observation.source,
            source_type=observation.source_type,
            source_ref=f"research-request:{request.request_id}",
            confidence=observation.confidence,
            contradiction_notes=list(observation.contradiction_notes),
        )
        evidence.append(item)
        if item.classification in {EvidenceClassification.UNKNOWN, EvidenceClassification.ASSUMPTION}:
            unresolved.append(request.request_id)
        else:
            resolved.append(request.request_id)
        if item.classification is EvidenceClassification.CONFLICTING_EVIDENCE:
            conflicting_claim_ids.append(item.claim_id)

    return EvidenceEngineResult(
        evidence=evidence,
        resolved_request_ids=resolved,
        unresolved_request_ids=unresolved,
        conflicting_claim_ids=conflicting_claim_ids,
    )
