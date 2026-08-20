from __future__ import annotations

from math import floor
from typing import Iterable
from urllib.parse import urlparse

from . import runner_v1 as base
from .contracts_v1 import EvidenceStance
from .live_research_adapter_v1 import ResearchPolicy
from .live_research_recovery_v1 import install_live_research_recovery
from .research_evidence_v1 import (
    EvidenceObservation,
    EvidenceObservationOrigin,
    ResearchRoute,
    ResearchRouterResult,
)


_ORIGINAL_RUN_MIND_FORGE = base.run_mind_forge
_ORIGINAL_BUILD_RUNNER_SUMMARY = base.build_runner_summary
_ORIGINAL_CLI_RESEARCH_POLICY = base._cli_research_policy


_MARKET_RESEARCH_TEMPLATES = (
    (
        "local demand",
        "The target market for {seed} has enough current observable local demand and customer activity to justify a low-cost paid pilot before larger capital is committed.",
        "A real demand floor must be established before operational optimization can justify investment. Search for direct local demand signals rather than generic market commentary.",
        ["official statistics", "local footfall or sales data", "local market data", "web/public source"],
    ),
    (
        "competition",
        "Direct competitors and substitutes serving customers for {seed} leave a meaningful local gap in product, price, convenience, availability, or experience.",
        "The opportunity depends on what customers can already buy locally and where a measurable gap remains. Search direct local competitor offers or current business listings.",
        ["direct competitor/public offer", "local business listing", "direct business page", "web/public source"],
    ),
    (
        "customer base",
        "The addressable resident, visitor, and seasonal customer base around {seed} is large and active enough to support repeat demand.",
        "Population, visitor flow, and seasonality determine whether apparent demand can support recurring sales. Prefer official population, tourism, passenger, or visitor data.",
        ["official statistics", "municipal/public data", "tourism or transport public data", "web/public source"],
    ),
    (
        "pricing and economics",
        "Current local prices and realistic gross-margin inputs for {seed} can support a viable break-even customer volume.",
        "Observed prices and cost/margin inputs are required to test whether the concept can reach break-even at plausible volume. Search direct menus, price lists, or measurable cost inputs.",
        ["direct competitor/public offer", "public menu or price list", "local business listing", "web/public source"],
    ),
    (
        "regulation",
        "Current licenses, food-service rules, permits, and local operating requirements for {seed} are feasible for a low-cost pilot and later commercial operation.",
        "Regulatory blockers can invalidate the opportunity even when demand and competition look attractive. Prefer the exact regulator or municipality that governs the target location.",
        ["government publication", "official regulator guidance", "municipality requirements", "web/public source"],
    ),
    (
        "location and customer flow",
        "There are accessible locations or sales channels for {seed} with enough relevant customer flow to test demand without committing to a full permanent shop.",
        "Location and distribution determine whether the target customer can be reached cheaply enough for a meaningful pilot. Search measurable footfall, transport, shopping-centre, or channel evidence.",
        ["shopping-centre or public footfall data", "local business or place listing", "municipal planning/public data", "web/public source"],
    ),
)


_UNIVERSAL_RESEARCH_TEMPLATES = (
    (
        "observable reality",
        "Current observable evidence materially establishes the real-world state, problem, need, or opportunity described by {seed}, rather than relying on assumption alone.",
        "MIND FORGE must verify what is actually happening now before choosing a solution. Search direct measurements, primary records, current data, or authoritative descriptions of the exact issue.",
        ["primary source", "official/public data", "direct measurement", "credible web/public source"],
    ),
    (
        "alternatives and benchmarks",
        "Existing alternatives, comparable approaches, prior solutions, or benchmarks relevant to {seed} show what already works, fails, or remains unresolved.",
        "A decision is stronger when it is compared with real alternatives and measurable reference points rather than evaluated in isolation.",
        ["primary documentation", "direct alternative or comparable source", "benchmark data", "credible web/public source"],
    ),
    (
        "people and context",
        "The users, stakeholders, affected groups, operating environment, and contextual conditions relevant to {seed} are understood well enough to judge the problem or opportunity correctly.",
        "Who is affected and under what conditions can materially change both the reasoning and the best solution.",
        ["official/public data", "primary user or stakeholder source", "credible survey or study", "credible web/public source"],
    ),
    (
        "resources and economics",
        "The measurable resources, costs, time, capacity, performance, or economic constraints around {seed} are known well enough to compare feasible options.",
        "A promising idea can fail when its resource, cost, time, capacity, or performance requirements are unrealistic.",
        ["primary specification or price", "benchmark or performance data", "official/public data", "credible web/public source"],
    ),
    (
        "rules risks and dependencies",
        "The material rules, risks, dependencies, standards, safety constraints, compatibility limits, or failure modes affecting {seed} are identified and supported by evidence.",
        "Hidden constraints or dependencies can invalidate an otherwise attractive solution, so they must be verified before commitment.",
        ["official rule or standard", "primary documentation", "security/safety guidance", "credible web/public source"],
    ),
    (
        "implementation and access",
        "There is a practical implementation, access, integration, workflow, delivery, or testing path for {seed} that can be executed without assuming unavailable capabilities.",
        "A decision is not actionable unless the required implementation path, access conditions, dependencies, and test route are real.",
        ["primary implementation documentation", "official availability/source", "direct operational evidence", "credible web/public source"],
    ),
)


_LOCAL_MARKET_SEED_MARKERS = (
    "محل",
    "متجر",
    "مقهى",
    "كافيه",
    "مطعم",
    "صالون",
    "سوبرماركت",
    "مشروع تجاري",
    "shop",
    "store",
    "cafe",
    "café",
    "restaurant",
    "retail",
    "salon",
    "butikk",
    "kafe",
    "kafé",
    "restaurant",
    "butikkdrift",
)


_LOW_RELEVANCE_LOCAL_MARKET_DOMAINS = frozenset(
    {
        "areq.net",
        "booking.com",
        "reverso.net",
        "searates.com",
        "toasttab.com",
    }
)


def research_profile_for_seed(seed: str) -> str:
    """Select a bounded research profile without making MIND FORGE domain-specific.

    LOCAL_MARKET is a specialization for obvious physical/local ventures. Everything else
    falls back to GENERAL, whose six lenses are deliberately domain-neutral. Future profiles
    can be added without changing the Phase 1 contract or the six-search budget model.
    """

    text = seed.casefold()
    if any(marker.casefold() in text for marker in _LOCAL_MARKET_SEED_MARKERS):
        return "LOCAL_MARKET"
    return "GENERAL"


def research_templates_for_seed(seed: str):
    if research_profile_for_seed(seed) == "LOCAL_MARKET":
        return _MARKET_RESEARCH_TEMPLATES
    return _UNIVERSAL_RESEARCH_TEMPLATES


def resilient_cli_research_policy(
    *,
    model: str,
    max_search_operations: int,
    max_research_cost_usd: float,
) -> ResearchPolicy:
    """Build the bounded live policy used by the resilient manual launcher.

    One hosted search is reserved per research question. The structured research answer
    gets a larger output ceiling so it can finish cleanly, while each request is kept
    to at most two sourced observations to avoid unnecessary output growth.
    """

    return ResearchPolicy(
        enabled=True,
        model=model,
        max_search_operations=max_search_operations,
        max_operations_per_request=1,
        max_results_per_request=2,
        max_estimated_cost_usd=max_research_cost_usd,
        max_output_tokens=1600,
    )


def _live_request_capacity(policy: ResearchPolicy, router: ResearchRouterResult) -> int:
    operation_capacity = policy.max_search_operations // policy.max_operations_per_request
    reserved_cost_per_request = (
        policy.max_operations_per_request * policy.estimated_cost_per_search_usd
    )
    cost_capacity = floor(
        (policy.max_estimated_cost_usd + 1e-12) / reserved_cost_per_request
    )
    return max(1, min(len(router.requests), operation_capacity, cost_capacity))


def expand_live_research_router(
    router: ResearchRouterResult,
    *,
    seed: str,
    policy: ResearchPolicy,
) -> ResearchRouterResult:
    """Use available live-search budget on distinct seed-grounded research lenses.

    No new Phase 1 request objects or idea ownership are created. Existing request IDs
    are re-routed only for the live execution copy, preserving the frozen structural
    router while selecting either a local-market specialization or domain-general lenses.
    """

    templates = research_templates_for_seed(seed)
    target_count = min(_live_request_capacity(policy, router), len(templates))
    requests_by_id = {item.request_id: item for item in router.requests}

    selected_ids: list[str] = []
    for request_id in router.external_request_ids:
        if request_id in requests_by_id and request_id not in selected_ids:
            selected_ids.append(request_id)
            if len(selected_ids) >= target_count:
                break

    if len(selected_ids) < target_count:
        for request in router.requests:
            if request.request_id in selected_ids:
                continue
            if request.request_id in set(router.user_request_ids):
                continue
            selected_ids.append(request.request_id)
            if len(selected_ids) >= target_count:
                break

    selected_set = set(selected_ids)
    template_by_id = {
        request_id: templates[index]
        for index, request_id in enumerate(selected_ids)
    }

    live_requests = []
    for request in router.requests:
        if request.request_id not in selected_set:
            live_requests.append(request)
            continue

        _label, claim_template, why_material, source_types = template_by_id[request.request_id]
        live_requests.append(
            request.model_copy(
                update={
                    "claim_text": claim_template.format(seed=seed),
                    "why_material": why_material,
                    "route": ResearchRoute.WEB,
                    "acceptable_source_types": list(source_types),
                }
            )
        )

    experiment_ids = [
        request.request_id
        for request in live_requests
        if request.request_id not in selected_set and request.route is ResearchRoute.EXPERIMENT
    ]
    user_ids = [
        request.request_id
        for request in live_requests
        if request.request_id not in selected_set and request.route is ResearchRoute.USER
    ]

    return router.model_copy(
        update={
            "requests": live_requests,
            "external_request_ids": selected_ids,
            "experiment_request_ids": experiment_ids,
            "user_request_ids": user_ids,
        }
    )


def _source_hostname(source_ref: str | None) -> str:
    if not source_ref:
        return ""
    try:
        return (urlparse(source_ref).hostname or "").casefold().removeprefix("www.")
    except ValueError:
        return ""


def _is_low_relevance_local_market_domain(source_ref: str | None) -> bool:
    host = _source_hostname(source_ref)
    if not host:
        return False
    return any(
        host == blocked or host.endswith(f".{blocked}")
        for blocked in _LOW_RELEVANCE_LOCAL_MARKET_DOMAINS
    )


def _source_quality_gate_live_observations(
    observations: Iterable[EvidenceObservation],
    *,
    seed: str | None = None,
) -> list[EvidenceObservation]:
    """Keep only observations that can materially bear on the selected research claim.

    NEUTRAL observations are context, not evidence, so they are excluded from the live
    evidence path. The historical local-market denylist is applied only to LOCAL_MARKET
    runs (or legacy callers that do not provide a seed), so a general topic is not forced
    through assumptions created for the Namsos market experiment.
    """

    apply_local_market_denylist = seed is None or research_profile_for_seed(seed) == "LOCAL_MARKET"
    accepted: list[EvidenceObservation] = []
    for observation in observations:
        if observation.origin is not EvidenceObservationOrigin.LIVE_RESEARCH:
            accepted.append(observation)
            continue
        if observation.stance is EvidenceStance.NEUTRAL:
            continue
        if apply_local_market_denylist and _is_low_relevance_local_market_domain(observation.source_ref):
            continue
        accepted.append(observation)
    return accepted


def _quality_gate_live_observations(
    observations: Iterable[EvidenceObservation],
    *,
    seed: str | None = None,
) -> list[EvidenceObservation]:
    """Apply source relevance before allowing live observations into Evidence."""

    gated = _source_quality_gate_live_observations(observations, seed=seed)
    return [
        observation.model_copy(
            update={"confidence": min(observation.confidence, 0.50)}
        )
        if (
            observation.origin is EvidenceObservationOrigin.LIVE_RESEARCH
            and observation.stance is EvidenceStance.NEUTRAL
        )
        else observation
        for observation in gated
    ]


def build_live_evidence_with_quality_gate(
    router: ResearchRouterResult,
    observations: Iterable[EvidenceObservation],
    *,
    seed: str | None = None,
):
    return base.build_evidence(
        router,
        _quality_gate_live_observations(observations, seed=seed),
    )


def _ordered_live_request_ids(result) -> list[str]:
    research = result.research
    if research is None:
        return []

    target_count = len(research.executed_request_ids) + len(research.skipped_request_ids)
    if target_count == 0:
        return []

    router = result.baseline.research
    requests_by_id = {item.request_id: item for item in router.requests}
    selected_ids: list[str] = []

    for request_id in router.external_request_ids:
        if request_id in requests_by_id and request_id not in selected_ids:
            selected_ids.append(request_id)
            if len(selected_ids) >= target_count:
                return selected_ids

    user_ids = set(router.user_request_ids)
    for request in router.requests:
        if request.request_id in selected_ids or request.request_id in user_ids:
            continue
        selected_ids.append(request.request_id)
        if len(selected_ids) >= target_count:
            break
    return selected_ids


def _live_request_metadata(result) -> dict[str, dict[str, str]]:
    metadata: dict[str, dict[str, str]] = {}
    templates = research_templates_for_seed(result.seed)
    for index, request_id in enumerate(_ordered_live_request_ids(result)):
        if index >= len(templates):
            break
        label, claim_template, why_material, _source_types = templates[index]
        metadata[request_id] = {
            "label": label,
            "claim": claim_template.format(seed=result.seed),
            "why_material": why_material,
        }
    return metadata


def _deduplicated_live_sources(
    accepted: Iterable[EvidenceObservation],
    request_metadata: dict[str, dict[str, str]],
) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    for observation in accepted:
        key = observation.source_ref or f"{observation.source}|{observation.request_id}"
        item = grouped.get(key)
        label = request_metadata.get(observation.request_id, {}).get("label")
        if item is None:
            item = {
                "source": observation.source,
                "source_type": observation.source_type,
                "source_ref": observation.source_ref,
                "stance": observation.stance.value,
                "confidence": observation.confidence,
                "source_types": [],
                "stances": [],
                "request_ids": [],
                "question_labels": [],
            }
            grouped[key] = item

        source_types = item["source_types"]
        stances = item["stances"]
        request_ids = item["request_ids"]
        question_labels = item["question_labels"]
        assert isinstance(source_types, list)
        assert isinstance(stances, list)
        assert isinstance(request_ids, list)
        assert isinstance(question_labels, list)

        if observation.source_type not in source_types:
            source_types.append(observation.source_type)
        if observation.stance.value not in stances:
            stances.append(observation.stance.value)
        if observation.request_id not in request_ids:
            request_ids.append(observation.request_id)
        if label and label not in question_labels:
            question_labels.append(label)
        item["confidence"] = max(float(item["confidence"]), observation.confidence)

    return list(grouped.values())


def _research_question_coverage(
    result,
    accepted: Iterable[EvidenceObservation],
    request_metadata: dict[str, dict[str, str]],
) -> list[dict[str, object]]:
    accepted_by_request: dict[str, set[str]] = {}
    for observation in accepted:
        accepted_by_request.setdefault(observation.request_id, set()).add(
            observation.source_ref or observation.source
        )

    raw_by_request: dict[str, int] = {}
    if result.research is not None:
        for observation in result.research.observations:
            raw_by_request[observation.request_id] = raw_by_request.get(observation.request_id, 0) + 1

    coverage: list[dict[str, object]] = []
    for request_id in _ordered_live_request_ids(result):
        metadata = request_metadata.get(request_id, {})
        refs = sorted(accepted_by_request.get(request_id, set()))
        accepted_count = len(refs)
        raw_count = raw_by_request.get(request_id, 0)
        coverage.append(
            {
                "request_id": request_id,
                "label": metadata.get("label", "unmapped research question"),
                "claim": metadata.get("claim", ""),
                "accepted_source_count": accepted_count,
                "rejected_observation_count": max(0, raw_count - accepted_count),
                "accepted_source_refs": refs,
                "status": "COVERED" if accepted_count > 0 else "MISSING",
            }
        )
    return coverage


def resilient_run_mind_forge(
    seed: str,
    *,
    live_research: bool = False,
    research_policy: ResearchPolicy | None = None,
    research_executor=None,
    max_selected: int = 3,
):
    """Production live path with adaptive research expansion and evidence guardrails."""

    if not live_research:
        return _ORIGINAL_RUN_MIND_FORGE(
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

    live_router = expand_live_research_router(
        baseline.research,
        seed=baseline.run_contract.topic.topic,
        policy=research_policy,
    )
    research = base.execute_research_requests(
        live_router,
        policy=research_policy,
        executor=research_executor,
    )
    evidence_engine = build_live_evidence_with_quality_gate(
        live_router,
        research.observations,
        seed=baseline.run_contract.topic.topic,
    )
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


def resilient_build_runner_summary(result) -> dict[str, object]:
    payload = _ORIGINAL_BUILD_RUNNER_SUMMARY(result)
    payload["research_profile"] = research_profile_for_seed(result.seed)
    research = result.research
    executed_count = len(research.executed_request_ids) if research is not None else 0
    skipped_count = len(research.skipped_request_ids) if research is not None else 0
    payload["research_executed_request_count"] = executed_count
    payload["live_external_request_count"] = executed_count + skipped_count

    if research is not None:
        accepted = _source_quality_gate_live_observations(
            research.observations,
            seed=result.seed,
        )
        request_metadata = _live_request_metadata(result)
        unique_sources = _deduplicated_live_sources(accepted, request_metadata)
        coverage = _research_question_coverage(result, accepted, request_metadata)

        payload["live_sources"] = unique_sources
        payload["source_quality_accepted_count"] = len(accepted)
        payload["source_quality_unique_accepted_count"] = len(unique_sources)
        payload["source_quality_rejected_count"] = len(research.observations) - len(accepted)
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
        payload["research_question_coverage"] = []
        payload["research_coverage_covered_count"] = 0
        payload["research_coverage_missing_count"] = 0
    return payload


def install_resilient_runner() -> None:
    install_live_research_recovery()
    base._cli_research_policy = resilient_cli_research_policy
    base.run_mind_forge = resilient_run_mind_forge
    base.build_runner_summary = resilient_build_runner_summary


def resilient_main() -> int:
    install_resilient_runner()
    return base.main()


if __name__ == "__main__":
    raise SystemExit(resilient_main())
