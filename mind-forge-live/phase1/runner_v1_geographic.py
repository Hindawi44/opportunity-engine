from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urlparse

from . import runner_v1 as base
from . import runner_v1_resilient as resilient
from .live_research_adapter_v1 import ResearchPolicy
from .research_evidence_v1 import EvidenceObservation, EvidenceObservationOrigin, ResearchRouterResult


_NORWAY_MARKERS = (
    "namsos",
    "نامسوس",
    "norway",
    "norge",
    "النرويج",
)

_NAMSOS_LOCALITY_MARKERS = (
    "namsos",
    "نامسوس",
    "namdalen",
    "trøndelag",
    "trondelag",
    "norway",
    "norge",
    "النرويج",
)

_LOCALITY_SENSITIVE_LABELS = frozenset(
    {
        "local demand",
        "competition",
        "customer base",
        "pricing and economics",
        "location and customer flow",
    }
)

_SEMANTIC_MARKERS = {
    "local demand": (
        "demand",
        "customer activity",
        "customers",
        "footfall",
        "visitor traffic",
        "visitors",
        "sales",
        "transactions",
        "orders",
        "etterspørsel",
        "kundestrøm",
        "kunder",
        "besøkende",
        "salg",
    ),
    "competition": (
        "competitor",
        "competition",
        "substitute",
        "cafe",
        "café",
        "coffee",
        "tea",
        "restaurant",
        "coffee shop",
        "tea shop",
        "konkurrent",
        "konkurranse",
        "kafe",
        "kafé",
        "kaffe",
        "te",
        "servering",
    ),
    "customer base": (
        "population",
        "resident",
        "residents",
        "visitor",
        "visitors",
        "tourist",
        "tourism",
        "overnight stay",
        "passenger",
        "demographic",
        "befolkning",
        "innbygger",
        "innbyggere",
        "besøkende",
        "turisme",
        "gjestedøgn",
        "passasjer",
    ),
    "regulation": (
        "license",
        "licence",
        "permit",
        "food service",
        "food safety",
        "registration",
        "hygiene",
        "requirement",
        "requirements",
        "servering",
        "skjenking",
        "bevilling",
        "tillatelse",
        "registrering",
        "mattilsynet",
        "regel",
        "regler",
        "krav",
        "godkjenning",
    ),
    "location and customer flow": (
        "footfall",
        "customer flow",
        "visitor traffic",
        "traffic",
        "visitors",
        "shopping centre",
        "shopping center",
        "mall",
        "location",
        "transport",
        "passenger",
        "kundestrøm",
        "besøkende",
        "kjøpesenter",
        "senter",
        "sentrum",
        "lokasjon",
        "passasjer",
    ),
    "observable reality": (
        "evidence",
        "data",
        "measurement",
        "measured",
        "observed",
        "current state",
        "incident",
        "issue",
        "problem",
        "usage",
        "rate",
        "frequency",
        "result",
        "report",
        "record",
        "metric",
        "benchmark",
        "test",
        "error",
        "failure",
        "performance",
    ),
    "alternatives and benchmarks": (
        "alternative",
        "alternatives",
        "benchmark",
        "comparison",
        "comparable",
        "approach",
        "method",
        "solution",
        "option",
        "implementation",
        "competitor",
        "prior",
        "reference",
        "best practice",
    ),
    "people and context": (
        "user",
        "users",
        "customer",
        "customers",
        "stakeholder",
        "stakeholders",
        "affected",
        "population",
        "audience",
        "participant",
        "environment",
        "context",
        "workflow",
        "usage",
        "device",
        "organization",
        "team",
    ),
    "resources and economics": (
        "cost",
        "costs",
        "price",
        "budget",
        "resource",
        "resources",
        "time",
        "capacity",
        "memory",
        "cpu",
        "latency",
        "throughput",
        "energy",
        "power",
        "battery",
        "performance",
        "effort",
        "staff",
        "revenue",
        "margin",
    ),
    "rules risks and dependencies": (
        "risk",
        "risks",
        "dependency",
        "dependencies",
        "requirement",
        "requirements",
        "standard",
        "policy",
        "regulation",
        "safety",
        "security",
        "compatibility",
        "constraint",
        "constraints",
        "limitation",
        "failure mode",
        "vulnerability",
        "permission",
    ),
    "implementation and access": (
        "implementation",
        "implement",
        "setup",
        "install",
        "deploy",
        "deployment",
        "integrate",
        "integration",
        "workflow",
        "access",
        "availability",
        "available",
        "api",
        "configuration",
        "migration",
        "rollout",
        "test",
        "steps",
        "procedure",
        "channel",
        "location",
    ),
}

_PRICING_MARKERS = (
    "price",
    "prices",
    "pricing",
    "price list",
    "menu",
    "cost",
    "costs",
    "margin",
    "gross margin",
    "break-even",
    "break even",
    "revenue",
    "nok",
    "kr",
    "kroner",
    "pris",
    "priser",
    "prisliste",
    "meny",
    "kostnad",
    "kostnader",
    "dekningsbidrag",
    "omsetning",
)

_NUMERIC_SIGNAL = re.compile(r"\d")


def _target_country_code(seed: str) -> str | None:
    text = seed.casefold()
    if any(marker in text for marker in _NORWAY_MARKERS):
        return "no"
    return None


def _hostname(source_ref: str | None) -> str:
    if not source_ref:
        return ""
    try:
        return (urlparse(source_ref).hostname or "").casefold().removeprefix("www.")
    except ValueError:
        return ""


def _country_code_tld(host: str) -> str | None:
    if "." not in host:
        return None
    suffix = host.rsplit(".", 1)[-1]
    if len(suffix) == 2 and suffix.isalpha():
        return suffix
    return None


def _request_labels(router: ResearchRouterResult, *, seed: str) -> dict[str, str]:
    labels: dict[str, str] = {}
    templates = resilient.research_templates_for_seed(seed)
    for index, request_id in enumerate(router.external_request_ids):
        if index >= len(templates):
            break
        labels[request_id] = templates[index][0]
    return labels


def _source_text(observation: EvidenceObservation) -> str:
    return " ".join(
        value
        for value in (
            observation.source or "",
            observation.source_type or "",
            observation.source_ref or "",
            observation.observation_text or "",
        )
        if value
    ).casefold()


def _contains_marker(text: str, marker: str) -> bool:
    marker = marker.casefold()
    if " " in marker or "-" in marker:
        return marker in text
    return re.search(rf"(?<!\w){re.escape(marker)}(?!\w)", text) is not None


def _contains_any_marker(text: str, markers: Iterable[str]) -> bool:
    return any(_contains_marker(text, marker) for marker in markers)


def _is_geographically_relevant(
    observation: EvidenceObservation,
    *,
    seed: str,
    question_label: str | None,
) -> bool:
    """Fail closed on wrong jurisdictions only for local-market research.

    Geography rules are a specialization, not a global MIND FORGE assumption. A technical,
    scientific, personal, administrative, or other GENERAL seed may legitimately use global
    primary evidence even when the seed happens to mention Norway.
    """

    if observation.origin is not EvidenceObservationOrigin.LIVE_RESEARCH:
        return True
    if resilient.research_profile_for_seed(seed) != "LOCAL_MARKET":
        return True

    country_code = _target_country_code(seed)
    if country_code is None:
        return True

    host = _hostname(observation.source_ref)
    if not host:
        return False
    if host.endswith(".test"):
        return True

    source_country = _country_code_tld(host)
    if source_country is not None and source_country != country_code:
        return False

    if country_code == "no":
        if question_label == "regulation":
            return host == "no" or host.endswith(".no")

        if question_label in _LOCALITY_SENSITIVE_LABELS:
            if host == "no" or host.endswith(".no"):
                return True
            text = _source_text(observation)
            return any(marker in text for marker in _NAMSOS_LOCALITY_MARKERS)

    return True


def _is_semantically_relevant(
    observation: EvidenceObservation,
    *,
    question_label: str | None,
) -> bool:
    """Require the source content to bear on the exact selected research lens."""

    if observation.origin is not EvidenceObservationOrigin.LIVE_RESEARCH:
        return True

    host = _hostname(observation.source_ref)
    if host.endswith(".test"):
        return True

    if question_label is None:
        return False

    text = _source_text(observation)
    if question_label == "pricing and economics":
        return _contains_any_marker(text, _PRICING_MARKERS) and bool(_NUMERIC_SIGNAL.search(text))

    markers = _SEMANTIC_MARKERS.get(question_label)
    if markers is None:
        return False
    return _contains_any_marker(text, markers)


def _geographic_quality_gate(
    router: ResearchRouterResult,
    observations: Iterable[EvidenceObservation],
    *,
    seed: str,
) -> list[EvidenceObservation]:
    accepted = resilient._source_quality_gate_live_observations(
        observations,
        seed=seed,
    )
    labels = _request_labels(router, seed=seed)
    return [
        observation
        for observation in accepted
        if _is_geographically_relevant(
            observation,
            seed=seed,
            question_label=labels.get(observation.request_id),
        )
    ]


def _semantic_quality_gate(
    router: ResearchRouterResult,
    observations: Iterable[EvidenceObservation],
    *,
    seed: str,
) -> list[EvidenceObservation]:
    labels = _request_labels(router, seed=seed)
    return [
        observation
        for observation in observations
        if _is_semantically_relevant(
            observation,
            question_label=labels.get(observation.request_id),
        )
    ]


def geographic_run_mind_forge(
    seed: str,
    *,
    live_research: bool = False,
    research_policy: ResearchPolicy | None = None,
    research_executor=None,
    max_selected: int = 3,
):
    """Adaptive Runner V1 plus profile-aware geographic and semantic validation."""

    if not live_research:
        return resilient._ORIGINAL_RUN_MIND_FORGE(
            seed,
            live_research=False,
            research_policy=research_policy,
            research_executor=research_executor,
            max_selected=max_selected,
        )

    baseline = base.run_phase1_forge(seed, max_selected=max_selected)
    if research_policy is None or not research_policy.enabled:
        raise RuntimeError(
            "live research requires an explicitly enabled ResearchPolicy; default remains OFF"
        )

    live_router = resilient.expand_live_research_router(
        baseline.research,
        seed=baseline.run_contract.topic.topic,
        policy=research_policy,
    )
    research = base.execute_research_requests(
        live_router,
        policy=research_policy,
        executor=research_executor,
    )
    geographically_accepted = _geographic_quality_gate(
        live_router,
        research.observations,
        seed=baseline.run_contract.topic.topic,
    )
    accepted_observations = _semantic_quality_gate(
        live_router,
        geographically_accepted,
        seed=baseline.run_contract.topic.topic,
    )
    evidence_engine = base.build_evidence(live_router, accepted_observations)
    decision_engine = base.decide(
        baseline.creative,
        baseline.logic,
        baseline.critique,
        live_router,
        evidence_engine,
        max_selected=max_selected,
    )
    experiment_engine = base.design_experiments(
        baseline.creative,
        baseline.critique,
        decision_engine,
    )
    memory_engine = base.build_planning_memory(
        baseline.run_contract.run_id,
        decision_engine,
        experiment_engine,
    )
    run_contract = base._rebuild_run_contract(
        baseline,
        evidence_engine,
        decision_engine,
        experiment_engine,
        memory_engine,
    )

    return base.MindForgeRunnerResult(
        seed=baseline.run_contract.topic.topic,
        baseline=baseline,
        research=research,
        evidence_engine=evidence_engine,
        decision_engine=decision_engine,
        experiment_engine=experiment_engine,
        memory_engine=memory_engine,
        run_contract=run_contract,
        live_research_requested=True,
    )


def geographic_build_runner_summary(result) -> dict[str, object]:
    payload = resilient._ORIGINAL_BUILD_RUNNER_SUMMARY(result)
    payload["research_profile"] = resilient.research_profile_for_seed(result.seed)
    research = result.research
    executed_count = len(research.executed_request_ids) if research is not None else 0
    skipped_count = len(research.skipped_request_ids) if research is not None else 0
    payload["research_executed_request_count"] = executed_count
    payload["live_external_request_count"] = executed_count + skipped_count

    if research is not None:
        request_metadata = resilient._live_request_metadata(result)
        base_accepted = resilient._source_quality_gate_live_observations(
            research.observations,
            seed=result.seed,
        )
        request_labels = {
            request_id: metadata.get("label", "")
            for request_id, metadata in request_metadata.items()
        }
        geographically_accepted = [
            observation
            for observation in base_accepted
            if _is_geographically_relevant(
                observation,
                seed=result.seed,
                question_label=request_labels.get(observation.request_id),
            )
        ]
        accepted = [
            observation
            for observation in geographically_accepted
            if _is_semantically_relevant(
                observation,
                question_label=request_labels.get(observation.request_id),
            )
        ]
        unique_sources = resilient._deduplicated_live_sources(accepted, request_metadata)
        coverage = resilient._research_question_coverage(result, accepted, request_metadata)

        payload["live_sources"] = unique_sources
        payload["source_quality_accepted_count"] = len(accepted)
        payload["source_quality_unique_accepted_count"] = len(unique_sources)
        payload["source_quality_rejected_count"] = len(research.observations) - len(accepted)
        payload["geographic_relevance_rejected_count"] = len(base_accepted) - len(geographically_accepted)
        payload["semantic_relevance_rejected_count"] = len(geographically_accepted) - len(accepted)
        payload["research_question_coverage"] = coverage
        payload["research_coverage_covered_count"] = sum(
            1 for item in coverage if item["status"] == "COVERED"
        )
        payload["research_coverage_missing_count"] = sum(
            1 for item in coverage if item["status"] == "MISSING"
        )
    else:
        payload["source_quality_accepted_count"] = 0
        payload["source_quality_unique_accepted_count"] = 0
        payload["source_quality_rejected_count"] = 0
        payload["geographic_relevance_rejected_count"] = 0
        payload["semantic_relevance_rejected_count"] = 0
        payload["research_question_coverage"] = []
        payload["research_coverage_covered_count"] = 0
        payload["research_coverage_missing_count"] = 0
    return payload


def install_geographic_runner() -> None:
    resilient.install_resilient_runner()
    base._cli_research_policy = resilient.resilient_cli_research_policy
    base.run_mind_forge = geographic_run_mind_forge
    base.build_runner_summary = geographic_build_runner_summary


def geographic_main() -> int:
    install_geographic_runner()
    return base.main()


if __name__ == "__main__":
    raise SystemExit(geographic_main())
