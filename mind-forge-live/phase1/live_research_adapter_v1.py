from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any, Protocol
from urllib.parse import urlparse

from agents import Agent, ModelSettings, Runner, WebSearchTool
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts_v1 import EvidenceStance
from .research_evidence_v1 import (
    EvidenceObservation,
    EvidenceObservationOrigin,
    ResearchRequest,
    ResearchRoute,
    ResearchRouterResult,
)


class ResearchAdapterKind(str, Enum):
    WEB_SEARCH = "WEB_SEARCH"
    PUBLIC_DATA = "PUBLIC_DATA"
    MAPS_PLACES = "MAPS_PLACES"


class ResearchPolicy(BaseModel):
    """Live-research gate, intentionally separate from LiveModelPolicy/LiveBudgetGate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = False
    model: str = "gpt-5.6-luna"
    max_search_operations: int = Field(default=4, ge=1, le=8)
    max_operations_per_request: int = Field(default=2, ge=1, le=2)
    max_results_per_request: int = Field(default=3, ge=1, le=5)
    max_estimated_cost_usd: float = Field(default=0.05, gt=0.0, le=0.25)
    estimated_cost_per_search_usd: float = Field(default=0.01, gt=0.0, le=0.10)
    max_output_tokens: int = Field(default=800, ge=200, le=2_000)
    search_context_size: str = "low"

    @model_validator(mode="after")
    def validate_reviewed_shape(self) -> "ResearchPolicy":
        if self.model not in {"gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"}:
            raise ValueError("live research model is not in the reviewed model allowlist")
        if self.search_context_size not in {"low", "medium", "high"}:
            raise ValueError("search_context_size must be low, medium, or high")
        return self


class ResearchUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    search_operations: int = 0
    results_returned: int = 0
    estimated_cost_usd: float = 0.0


class ResearchBudgetGate:
    """Reserve worst-case search operations before each request, then record actual use."""

    def __init__(self, policy: ResearchPolicy) -> None:
        self.policy = policy
        self.usage = ResearchUsage()
        self._reserved_operations = 0

    def reserve_request(self) -> int:
        reserve = self.policy.max_operations_per_request
        projected_operations = (
            self.usage.search_operations + self._reserved_operations + reserve
        )
        if projected_operations > self.policy.max_search_operations:
            raise RuntimeError("live research search-operation budget would be exceeded")

        projected_cost = (
            self.usage.estimated_cost_usd
            + (self._reserved_operations + reserve)
            * self.policy.estimated_cost_per_search_usd
        )
        if projected_cost > self.policy.max_estimated_cost_usd:
            raise RuntimeError("live research estimated-cost budget would be exceeded")

        self._reserved_operations += reserve
        return reserve

    def record_request(
        self,
        *,
        reserved_operations: int,
        actual_operations: int,
        results_returned: int,
    ) -> None:
        if reserved_operations > self._reserved_operations:
            raise RuntimeError("research budget reservation accounting is inconsistent")
        if actual_operations < 1:
            self._reserved_operations -= reserved_operations
            raise RuntimeError("live research executor made no web search operation")
        if actual_operations > reserved_operations:
            self._reserved_operations -= reserved_operations
            raise RuntimeError("live research executor exceeded per-request search-operation cap")

        self._reserved_operations -= reserved_operations
        self.usage.search_operations += actual_operations
        self.usage.results_returned += results_returned
        self.usage.estimated_cost_usd = round(
            self.usage.estimated_cost_usd
            + actual_operations * self.policy.estimated_cost_per_search_usd,
            8,
        )

        if self.usage.search_operations > self.policy.max_search_operations:
            raise RuntimeError("live research actual search-operation cap exceeded")
        if self.usage.estimated_cost_usd > self.policy.max_estimated_cost_usd:
            raise RuntimeError("live research actual estimated-cost cap exceeded")

    def cancel_reservation(self, reserved_operations: int) -> None:
        self._reserved_operations = max(0, self._reserved_operations - reserved_operations)


class RawResearchHit(BaseModel):
    """Executor-level hit. It is not canonical Evidence."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)
    stance: EvidenceStance = EvidenceStance.NEUTRAL
    confidence: float = Field(default=0.65, ge=0.0, le=0.90)


class ResearchExecution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hits: list[RawResearchHit] = Field(default_factory=list)
    search_operations: int = Field(ge=1, le=2)


class ResearchExecutor(Protocol):
    is_live: bool

    def search(
        self,
        request: ResearchRequest,
        *,
        adapter_kind: ResearchAdapterKind,
        policy: ResearchPolicy,
    ) -> ResearchExecution: ...


class FakeResearchExecutor:
    """Deterministic offline executor used by CI; never calls a network or model."""

    is_live = False

    def __init__(
        self,
        hits_by_request: dict[str, list[RawResearchHit]] | None = None,
        *,
        operations_by_request: dict[str, int] | None = None,
    ) -> None:
        self.hits_by_request = hits_by_request or {}
        self.operations_by_request = operations_by_request or {}

    def search(
        self,
        request: ResearchRequest,
        *,
        adapter_kind: ResearchAdapterKind,
        policy: ResearchPolicy,
    ) -> ResearchExecution:
        hits = list(self.hits_by_request.get(request.request_id, []))
        hits = hits[: policy.max_results_per_request]
        operations = self.operations_by_request.get(request.request_id, 1)
        return ResearchExecution(hits=hits, search_operations=operations)


class _ResearchDraftItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_ref: str = Field(min_length=1)
    excerpt: str = Field(min_length=1, max_length=1_500)
    stance: EvidenceStance = EvidenceStance.NEUTRAL
    confidence: float = Field(default=0.65, ge=0.0, le=0.90)


class _ResearchDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observations: list[_ResearchDraftItem] = Field(default_factory=list, max_length=5)


def _as_jsonish(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _as_jsonish(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_as_jsonish(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _as_jsonish(getattr(value, field.name))
            for field in fields(value)
        }
    if hasattr(value, "model_dump"):
        try:
            return _as_jsonish(value.model_dump(mode="json"))
        except TypeError:
            return _as_jsonish(value.model_dump())
    return value


def _walk(value: Any):
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _count_web_search_calls(payloads: list[Any]) -> int:
    count = 0
    for payload in payloads:
        for row in _walk(payload):
            if row.get("type") == "web_search_call":
                count += 1
    return count


def _extract_sources(payloads: list[Any]) -> dict[str, str]:
    sources: dict[str, str] = {}
    for payload in payloads:
        for row in _walk(payload):
            url = row.get("url")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                continue
            title = row.get("title")
            if not isinstance(title, str) or not title.strip():
                title = urlparse(url).netloc or url
            sources.setdefault(url, title.strip())
    return sources


def _source_type_for_kind(kind: ResearchAdapterKind) -> str:
    if kind is ResearchAdapterKind.PUBLIC_DATA:
        return "public data source"
    if kind is ResearchAdapterKind.MAPS_PLACES:
        return "maps/place listing"
    return "web/public source"


def _research_prompt(request: ResearchRequest, kind: ResearchAdapterKind, max_results: int) -> str:
    if kind is ResearchAdapterKind.PUBLIC_DATA:
        scope = (
            "Search primary official/public data sources first. Prefer official statistics, "
            "registries, government publications, and primary public datasets."
        )
    elif kind is ResearchAdapterKind.MAPS_PLACES:
        scope = (
            "Search public place/business listings and direct business pages relevant to the "
            "claim. Prefer location-specific, current public listings over generic articles."
        )
    else:
        scope = (
            "Search the public web for primary market data, credible industry data, or direct "
            "public offers that materially bear on the claim."
        )

    return (
        "You are a bounded research collector inside MIND FORGE. Use web search, then return "
        "only observations grounded in URLs that actually appeared in the web-search sources. "
        "Do not label anything as a verified fact and do not make a business decision. "
        "For each observation, say whether the cited source SUPPORTS, REFUTES, is NEUTRAL to, "
        "or presents MIXED evidence about the exact claim. Confidence is extraction/source-fit "
        "confidence, not truth probability. Use web search at most once unless a second search "
        "is strictly necessary to obtain a usable source. "
        f"Return at most {max_results} sourced observations.\n\n"
        f"RESEARCH MODE: {kind.value}\n"
        f"CLAIM: {request.claim_text}\n"
        f"WHY MATERIAL: {request.why_material}\n"
        f"ACCEPTABLE SOURCE TYPES: {request.acceptable_source_types!r}\n"
        f"SCOPE RULE: {scope}"
    )


class OpenAIWebSearchExecutor:
    """Live executor backed by the Agents SDK hosted WebSearchTool."""

    is_live = True

    def search(
        self,
        request: ResearchRequest,
        *,
        adapter_kind: ResearchAdapterKind,
        policy: ResearchPolicy,
    ) -> ResearchExecution:
        agent = Agent(
            name=f"MIND FORGE Research — {adapter_kind.value}",
            instructions=(
                "Collect sourced observations only. Never assign canonical evidence classes. "
                "Use the hosted web search tool and preserve exact source URLs."
            ),
            model=policy.model,
            tools=[WebSearchTool(search_context_size=policy.search_context_size)],
            model_settings=ModelSettings(
                tool_choice="required",
                parallel_tool_calls=False,
                max_tokens=policy.max_output_tokens,
                verbosity="low",
                response_include=["web_search_call.action.sources"],
            ),
            output_type=_ResearchDraft,
        )
        result = Runner.run_sync(
            agent,
            _research_prompt(request, adapter_kind, policy.max_results_per_request),
            max_turns=2,
        )

        raw_payloads = [
            _as_jsonish(item) for item in getattr(result, "raw_responses", [])
        ]
        new_item_payloads = [
            _as_jsonish(raw_item)
            for item in getattr(result, "new_items", [])
            if (raw_item := getattr(item, "raw_item", None)) is not None
        ]

        actual_operations = max(
            _count_web_search_calls(raw_payloads),
            _count_web_search_calls(new_item_payloads),
        )
        sources = _extract_sources(raw_payloads)
        if not sources:
            sources = _extract_sources(new_item_payloads)
        if not sources:
            raise RuntimeError("live web research returned no source URLs; fail closed")

        # A returned web-search source proves at least one hosted search occurred even
        # if a future SDK representation omits the call item from one inspection surface.
        actual_operations = max(actual_operations, 1)

        draft = result.final_output
        if not isinstance(draft, _ResearchDraft):
            draft = _ResearchDraft.model_validate(draft)

        source_type = _source_type_for_kind(adapter_kind)
        hits: list[RawResearchHit] = []
        seen: set[str] = set()
        for item in draft.observations:
            if item.source_ref not in sources or item.source_ref in seen:
                continue
            seen.add(item.source_ref)
            hits.append(
                RawResearchHit(
                    source=sources[item.source_ref],
                    source_type=source_type,
                    source_ref=item.source_ref,
                    excerpt=item.excerpt,
                    stance=item.stance,
                    confidence=item.confidence,
                )
            )
            if len(hits) >= policy.max_results_per_request:
                break

        if not hits:
            summary = str(getattr(result, "final_output", "Sourced web result"))
            if len(summary) > 1_200:
                summary = summary[:1_200]
            for url, title in list(sources.items())[: policy.max_results_per_request]:
                hits.append(
                    RawResearchHit(
                        source=title,
                        source_type=source_type,
                        source_ref=url,
                        excerpt=summary or "Sourced web result.",
                        stance=EvidenceStance.NEUTRAL,
                        confidence=0.60,
                    )
                )

        return ResearchExecution(
            hits=hits,
            search_operations=actual_operations,
        )


def assert_live_research_access(policy: ResearchPolicy) -> None:
    if not policy.enabled:
        raise RuntimeError("live research policy is disabled")
    if os.getenv("MIND_FORGE_LIVE_RESEARCH_ENABLED") != "1":
        raise RuntimeError("MIND_FORGE_LIVE_RESEARCH_ENABLED=1 is required for live research")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not available to the live research runtime")


class _ResearchAdapter:
    kind: ResearchAdapterKind
    supported_route: ResearchRoute

    def execute(
        self,
        request: ResearchRequest,
        *,
        executor: ResearchExecutor,
        policy: ResearchPolicy,
        gate: ResearchBudgetGate,
    ) -> list[EvidenceObservation]:
        if request.route is not self.supported_route:
            raise ValueError(
                f"{self.kind.value} adapter cannot execute route {request.route.value}"
            )

        reserved = gate.reserve_request()
        try:
            execution = executor.search(
                request,
                adapter_kind=self.kind,
                policy=policy,
            )
            observations = [
                EvidenceObservation(
                    request_id=request.request_id,
                    origin=EvidenceObservationOrigin.LIVE_RESEARCH,
                    source=hit.source,
                    source_type=hit.source_type,
                    source_ref=hit.source_ref,
                    observation_text=hit.excerpt,
                    classification=None,
                    stance=hit.stance,
                    confidence=hit.confidence,
                )
                for hit in execution.hits
            ]
            gate.record_request(
                reserved_operations=reserved,
                actual_operations=execution.search_operations,
                results_returned=len(observations),
            )
            return observations
        except Exception:
            if gate._reserved_operations >= reserved:
                gate.cancel_reservation(reserved)
            raise


class WebSearchAdapter(_ResearchAdapter):
    kind = ResearchAdapterKind.WEB_SEARCH
    supported_route = ResearchRoute.WEB


class PublicDataAdapter(_ResearchAdapter):
    kind = ResearchAdapterKind.PUBLIC_DATA
    supported_route = ResearchRoute.PUBLIC_DATA


class MapsPlacesAdapter(_ResearchAdapter):
    """Places specialization over hosted web search; no separate maps API key required."""

    kind = ResearchAdapterKind.MAPS_PLACES
    supported_route = ResearchRoute.WEB


class LiveResearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observations: list[EvidenceObservation] = Field(default_factory=list)
    executed_request_ids: list[str] = Field(default_factory=list)
    skipped_request_ids: list[str] = Field(default_factory=list)
    adapter_by_request: dict[str, ResearchAdapterKind] = Field(default_factory=dict)
    usage: ResearchUsage
    live_executor_used: bool
    live_research_enabled: bool

    @model_validator(mode="after")
    def enforce_observation_boundary(self) -> "LiveResearchResult":
        for item in self.observations:
            if item.origin is not EvidenceObservationOrigin.LIVE_RESEARCH:
                raise ValueError("research adapters must emit LIVE_RESEARCH observations")
            if item.classification is not None:
                raise ValueError("research adapters cannot assign final evidence classification")
        if self.live_executor_used and not self.live_research_enabled:
            raise ValueError("a live executor cannot run while live research is disabled")
        return self


def _maps_places_requested(request: ResearchRequest) -> bool:
    text = " ".join(request.acceptable_source_types).casefold()
    return any(token in text for token in ("maps", "place listing", "location listing"))


def _select_adapter(request: ResearchRequest) -> _ResearchAdapter | None:
    if request.route is ResearchRoute.PUBLIC_DATA:
        return PublicDataAdapter()
    if request.route is ResearchRoute.WEB:
        if _maps_places_requested(request):
            return MapsPlacesAdapter()
        return WebSearchAdapter()
    return None


def execute_research_requests(
    router: ResearchRouterResult,
    *,
    policy: ResearchPolicy | None = None,
    executor: ResearchExecutor | None = None,
) -> LiveResearchResult:
    """Execute only Router-approved external requests behind an independent gate.

    CI passes FakeResearchExecutor, which performs no paid/network calls. Production
    defaults to the live Agents SDK executor but requires both explicit policy opt-in
    and MIND_FORGE_LIVE_RESEARCH_ENABLED=1 plus the existing OPENAI_API_KEY.
    """

    active_policy = policy or ResearchPolicy(enabled=False)
    active_executor: ResearchExecutor = executor or OpenAIWebSearchExecutor()

    if active_executor.is_live:
        assert_live_research_access(active_policy)
    elif not active_policy.enabled:
        raise RuntimeError("research policy is disabled")

    gate = ResearchBudgetGate(active_policy)
    external_ids = set(router.external_request_ids)
    observations: list[EvidenceObservation] = []
    executed: list[str] = []
    skipped: list[str] = []
    adapter_by_request: dict[str, ResearchAdapterKind] = {}

    for request in router.requests:
        if request.request_id not in external_ids:
            continue
        adapter = _select_adapter(request)
        if adapter is None:
            skipped.append(request.request_id)
            continue

        request_observations = adapter.execute(
            request,
            executor=active_executor,
            policy=active_policy,
            gate=gate,
        )
        observations.extend(request_observations)
        executed.append(request.request_id)
        adapter_by_request[request.request_id] = adapter.kind

    return LiveResearchResult(
        observations=observations,
        executed_request_ids=executed,
        skipped_request_ids=skipped,
        adapter_by_request=adapter_by_request,
        usage=gate.usage,
        live_executor_used=active_executor.is_live,
        live_research_enabled=active_policy.enabled,
    )