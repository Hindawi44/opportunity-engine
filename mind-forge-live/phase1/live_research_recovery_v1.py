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
    """Install malformed-output recovery plus a hard one-search prompt."""

    base._research_prompt = _single_search_prompt
    base.OpenAIWebSearchExecutor = ResilientOpenAIWebSearchExecutor