from __future__ import annotations

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


def _request_labels(router: ResearchRouterResult) -> dict[str, str]:
    labels: dict[str, str] = {}
    for index, request_id in enumerate(router.external_request_ids):
        if index >= len(resilient._MARKET_RESEARCH_TEMPLATES):
            break
        labels[request_id] = resilient._MARKET_RESEARCH_TEMPLATES[index][0]
    return labels


def _source_text(observation: EvidenceObservation) -> str:
    return " ".join(
        value
        for value in (
            observation.source or "",
            observation.source_ref or "",
            observation.observation_text or "",
        )
        if value
    ).casefold()


def _is_geographically_relevant(
    observation: EvidenceObservation,
    *,
    seed: str,
    question_label: str | None,
) -> bool:
    """Fail closed on sources that clearly belong to the wrong jurisdiction.

    The first production profile is the current Namsos/Norway market. Unknown seeds keep
    the resilient V1 behavior unchanged. Reserved .test domains remain allowed for
    deterministic offline regression tests only.
    """

    if observation.origin is not EvidenceObservationOrigin.LIVE_RESEARCH:
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


def _geographic_quality_gate(
    router: ResearchRouterResult,
    observations: Iterable[EvidenceObservation],
    *,
    seed: str,
) -> list[EvidenceObservation]:
    accepted = resilient._source_quality_gate_live_observations(observations)
    labels = _request_labels(router)
    return [
        observation
        for observation in accepted
        if _is_geographically_relevant(
            observation,
            seed=seed,
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
    """Resilient Runner V1 plus fail-closed target-jurisdiction validation."""

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
    accepted_observations = _geographic_quality_gate(
        live_router,
        research.observations,
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
    research = result.research
    executed_count = len(research.executed_request_ids) if research is not None else 0
    skipped_count = len(research.skipped_request_ids) if research is not None else 0
    payload["research_executed_request_count"] = executed_count
    payload["live_external_request_count"] = executed_count + skipped_count

    if research is not None:
        request_metadata = resilient._live_request_metadata(result)
        base_accepted = resilient._source_quality_gate_live_observations(research.observations)
        request_labels = {
            request_id: metadata.get("label", "")
            for request_id, metadata in request_metadata.items()
        }
        accepted = [
            observation
            for observation in base_accepted
            if _is_geographically_relevant(
                observation,
                seed=result.seed,
                question_label=request_labels.get(observation.request_id),
            )
        ]
        unique_sources = resilient._deduplicated_live_sources(accepted, request_metadata)
        coverage = resilient._research_question_coverage(result, accepted, request_metadata)

        payload["live_sources"] = unique_sources
        payload["source_quality_accepted_count"] = len(accepted)
        payload["source_quality_unique_accepted_count"] = len(unique_sources)
        payload["source_quality_rejected_count"] = len(research.observations) - len(accepted)
        payload["geographic_relevance_rejected_count"] = len(base_accepted) - len(accepted)
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
