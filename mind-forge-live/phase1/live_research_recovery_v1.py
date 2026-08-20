from __future__ import annotations

from typing import Any

from . import live_research_adapter_v1 as base


_ORIGINAL_RESEARCH_PROMPT = base._research_prompt


def _recover_invalid_final_output(_data: Any) -> base._ResearchDraft:
    """Return an empty valid draft without replaying web search side effects.

    The Agents SDK validates this fallback against the same output_type. The existing
    executor then reads the already-returned web-search sources and uses its fail-closed
    source fallback. No model retry or second hosted search is triggered here.
    """

    return base._ResearchDraft(observations=[])


def _single_search_prompt(
    request: base.ResearchRequest,
    kind: base.ResearchAdapterKind,
    max_results: int,
) -> str:
    prompt = _ORIGINAL_RESEARCH_PROMPT(request, kind, max_results)
    return (
        prompt
        + "\nHARD SEARCH LIMIT: perform exactly one hosted web-search operation for this "
        "research request. Do not perform a second search; use the sources returned by "
        "that single search or fail closed."
        + "\nADAPTIVE DOMAIN RULE: MIND FORGE is domain-general. Do not assume the seed is a "
        "business, shop, or local market. Infer the domain only from the exact claim and seed "
        "text embedded in it. Preserve the seed's concrete nouns, named entities, technical "
        "terms, products, locations, and constraints in the search query. A local venture may "
        "need market evidence; a technical problem may need primary documentation, issue "
        "reports, benchmarks, or specifications; an administrative or regulatory problem may "
        "need official rules; another domain should use its own primary evidence."
        + "\nQUERY PRECISION RULE: before calling web search, form one compact query that combines "
        "the exact subject of the claim with the evidence dimension being tested. Do not broaden "
        "to generic articles merely because they mention one word from the seed. Prefer exact "
        "entities, location names, model names, standards, error terms, prices, measurements, "
        "or other discriminating terms that can directly answer the claim."
        + "\nSOURCE RELEVANCE RULE: use only sources that materially bear on the exact claim "
        "and target context. For local-market questions, the source must be explicitly local "
        "to the target geography or be an authoritative official/regulatory source directly "
        "applicable to that jurisdiction. Do not use generic international booking pages, "
        "translation sites, shipping directories, or third-party ordering pages as evidence "
        "for local demand, competition, pricing, or customer flow. If the available source "
        "does not meet this rule, return no observation for it."
        + "\nJURISDICTION RULE: for licenses, permits, food-service rules, taxation, or other "
        "regulatory claims, never substitute guidance from another country, region, or "
        "municipality. A source is usable only when it directly applies to the target "
        "jurisdiction named in the seed; otherwise return no observation for that source."
        + "\nSEMANTIC EVIDENCE RULE: geographic match alone is never sufficient. The cited "
        "source and extracted observation must directly answer the research question. For "
        "pricing/economics, require observable prices, a menu/price list with numeric values, "
        "cost inputs, margins, revenue, or break-even inputs. For competition, require a "
        "direct competitor/substitute offer or business listing. For customer base, require "
        "population, visitor, tourism, passenger, or demographic evidence. For local demand, "
        "require observable customer activity, footfall, sales, orders, or equivalent demand "
        "signals. For location/customer flow, require traffic, footfall, visitor-flow, shopping-"
        "centre, transport, or channel evidence. For domain-general questions, require evidence "
        "that directly matches the selected lens such as current measurements, alternatives, "
        "affected users/context, measurable resources, rules/risks/dependencies, or a real "
        "implementation/access path. A page that merely shares a place name or generic keyword "
        "does not qualify for an unrelated claim; return no observation."
    )


class ResilientOpenAIWebSearchExecutor(base.OpenAIWebSearchExecutor):
    """V1 compatibility wrapper for malformed structured final output.

    The underlying V1 executor remains authoritative for source extraction, search
    accounting, provenance, and fail-closed behavior. This wrapper only injects the
    SDK's invalid_final_output handler for the duration of one synchronous search.
    """

    is_live = True

    def search(
        self,
        request: base.ResearchRequest,
        *,
        adapter_kind: base.ResearchAdapterKind,
        policy: base.ResearchPolicy,
    ) -> base.ResearchExecution:
        original_run_sync = base.Runner.run_sync

        def run_sync_with_recovery(*args: Any, **kwargs: Any):
            handlers = dict(kwargs.get("error_handlers") or {})
            handlers.setdefault("invalid_final_output", _recover_invalid_final_output)
            kwargs["error_handlers"] = handlers
            return original_run_sync(*args, **kwargs)

        base.Runner.run_sync = run_sync_with_recovery
        try:
            return super().search(
                request,
                adapter_kind=adapter_kind,
                policy=policy,
            )
        finally:
            base.Runner.run_sync = original_run_sync


def install_live_research_recovery() -> None:
    """Install malformed-output recovery plus hard search and relevance constraints."""

    base._research_prompt = _single_search_prompt
    base.OpenAIWebSearchExecutor = ResilientOpenAIWebSearchExecutor
