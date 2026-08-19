from __future__ import annotations

from math import floor
from typing import Iterable

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
        "A real demand floor must be established before operational optimization can justify investment.",
        ["official statistics", "local market data", "web/public source"],
    ),
    (
        "competition",
        "Direct competitors and substitutes serving customers for {seed} leave a meaningful local gap in product, price, convenience, availability, or experience.",
        "The opportunity depends on what customers can already buy locally and where a measurable gap remains.",
        ["direct competitor/public offer", "local business listing", "web/public source"],
    ),
    (
        "customer base",
        "The addressable resident, visitor, and seasonal customer base around {seed} is large and active enough to support repeat demand.",
        "Population, visitor flow, and seasonality determine whether apparent demand can support recurring sales.",
        ["official statistics", "municipal/public data", "tourism or transport public data", "web/public source"],
    ),
    (
        "pricing and economics",
        "Current local prices and realistic gross-margin inputs for {seed} can support a viable break-even customer volume.",
        "Observed prices and cost/margin inputs are required to test whether the concept can reach break-even at plausible volume.",
        ["direct competitor/public offer", "public menu or price list", "local business listing", "web/public source"],
    ),
    (
        "regulation",
        "Current licenses, food-service rules, permits, and local operating requirements for {seed} are feasible for a low-cost pilot and later commercial operation.",
        "Regulatory blockers can invalidate the opportunity even when demand and competition look attractive.",
        ["government publication", "official regulator guidance", "municipality requirements", "web/public source"],
    ),
    (
        "location and customer flow",
        "There are accessible locations or sales channels for {seed} with enough relevant customer flow to test demand without committing to a full permanent shop.",
        "Location and distribution determine whether the target customer can be reached cheaply enough for a meaningful pilot.",
        ["shopping-centre or public footfall data", "local business or place listing", "municipal planning/public data", "web/public source"],
    ),
)


def resilient_cli_research_policy(
    *,
    model: str,
    max_search_operations: int,
    max_research_cost_usd: float,
) -> ResearchPolicy:
    """Build the bounded live policy used by the resilient manual launcher.

    One hosted search is reserved per market question. The structured research answer
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
    """Use available live-search budget on distinct seed-grounded market questions.

    No new Phase 1 request objects or idea ownership are created. Existing request IDs
    are re-routed only for the live execution copy, preserving the frozen structural
    router while allowing the manual live runner to validate more of the real market.
    """

    target_count = min(_live_request_capacity(policy, router), len(_MARKET_RESEARCH_TEMPLATES))
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
        request_id: _MARKET_RESEARCH_TEMPLATES[index]
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


def _quality_gate_live_observations(
    observations: Iterable[EvidenceObservation],
) -> list[EvidenceObservation]:
    """Prevent non-directional live sources from earning evidence strength.

    A NEUTRAL source does not support or refute the exact claim, so confidence in the
    extraction cannot convert it into WEAK/STRONG evidence. Clamping to 0.50 makes the
    existing Evidence Engine classify it UNKNOWN and keep the request unresolved.
    """

    gated: list[EvidenceObservation] = []
    for observation in observations:
        if (
            observation.origin is EvidenceObservationOrigin.LIVE_RESEARCH
            and observation.stance is EvidenceStance.NEUTRAL
        ):
            gated.append(
                observation.model_copy(
                    update={"confidence": min(observation.confidence, 0.50)}
                )
            )
        else:
            gated.append(observation)
    return gated


def build_live_evidence_with_quality_gate(
    router: ResearchRouterResult,
    observations: Iterable[EvidenceObservation],
):
    return base.build_evidence(router, _quality_gate_live_observations(observations))


def resilient_run_mind_forge(
    seed: str,
    *,
    live_research: bool = False,
    research_policy: ResearchPolicy | None = None,
    research_executor=None,
    max_selected: int = 3,
):
    """Production live path with market expansion and evidence-quality guardrail."""

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
    research = result.research
    executed_count = len(research.executed_request_ids) if research is not None else 0
    skipped_count = len(research.skipped_request_ids) if research is not None else 0
    payload["research_executed_request_count"] = executed_count
    payload["live_external_request_count"] = executed_count + skipped_count
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