"""Classify a bounded Brave retrieval probe without changing discovery behavior."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class RetrievalProbeResult:
    probe_id: str
    client: str
    query: str
    result_count: int
    error: str | None = None
    sample_results: tuple[dict[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["sample_results"] = list(self.sample_results)
        return payload


def classify_retrieval_probe(
    results: Iterable[RetrievalProbeResult],
) -> dict[str, str]:
    """Identify the smallest next action from four controlled Brave probes."""
    by_id = {result.probe_id: result for result in results}
    required = {
        "current-generic",
        "legacy-generic",
        "legacy-axl-unscoped",
        "legacy-axl-site",
    }
    missing = sorted(required - set(by_id))
    if missing:
        raise ValueError(f"missing retrieval probes: {missing}")

    current = by_id["current-generic"]
    legacy = by_id["legacy-generic"]
    unscoped = by_id["legacy-axl-unscoped"]
    scoped = by_id["legacy-axl-site"]

    if current.error and legacy.error:
        return {
            "diagnosis": "PROVIDER_OR_ACCOUNT_FAILURE",
            "next_action": (
                "Inspect the two generic probe errors and raw transport before changing queries."
            ),
        }
    if current.error:
        return {
            "diagnosis": "CURRENT_CLIENT_PARAMETER_FAILURE",
            "next_action": (
                "Keep the legacy client parameters and fix the current Discovery client transport."
            ),
        }
    if legacy.error:
        return {
            "diagnosis": "LEGACY_CLIENT_PARAMETER_FAILURE",
            "next_action": (
                "Use the current client for the next probe and remove the incompatible legacy parameter."
            ),
        }
    if current.result_count == 0 and legacy.result_count > 0:
        return {
            "diagnosis": "CURRENT_CLIENT_RECALL_REGRESSION",
            "next_action": (
                "Align the current Discovery client with the proven legacy request parameters before retrying source queries."
            ),
        }
    if current.result_count == 0 and legacy.result_count == 0:
        return {
            "diagnosis": "GENERIC_SEARCH_ZERO_RESULTS",
            "next_action": (
                "Inspect the successful HTTP response body and subscription product; do not spend more requests on source targeting."
            ),
        }
    if unscoped.error or scoped.error:
        return {
            "diagnosis": "SOURCE_PROBE_ERROR",
            "next_action": (
                "Inspect the AXL probe error before changing the URL gate or adding Playwright."
            ),
        }
    if unscoped.result_count == 0:
        return {
            "diagnosis": "SOURCE_NOT_RECALLED_BY_BRAVE",
            "next_action": (
                "Treat Brave as unsuitable for this source and move source discovery to direct source collectors or another index."
            ),
        }
    if scoped.result_count == 0:
        return {
            "diagnosis": "SITE_OPERATOR_RECALL_FAILURE",
            "next_action": (
                "Search the source name without site: and enforce the approved host only in the URL gate."
            ),
        }
    return {
        "diagnosis": "SOURCE_QUERY_RECALLS_RESULTS",
        "next_action": (
            "Use the working request shape in source-targeted validation and keep all existing verification gates."
        ),
    }
