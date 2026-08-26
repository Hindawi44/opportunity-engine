"""Read-only 403 diagnostics using Exa highlights already returned by search.

Live checkpoint #350 showed that Norway discovery finds commercially specific
Merkandi/Europages URLs, while the direct verifier loses many of them to HTTP
403. This shadow layer asks a narrow question only: when the exact URL cannot be
fetched, did Exa already return extractive source highlights strong enough to
look like the same strict commercial evidence?

The answer is diagnostic only. The original FETCH_FAILED classification,
fetch_ok flag, Exact-Lot counts, Tool Learning credit, Top5 eligibility and all
commercial decisions remain unchanged. No search request, direct page fetch,
provider, source, runtime, market or automatic action is added here.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Callable

from opportunity_engine.discovery import provider_unique_page_verification as _verification
from opportunity_engine.discovery.exa_shadow_page_verification import (
    EXACT_LOT_CANDIDATE,
    FETCH_FAILED,
    _classify_page,
)


VERSION = "EXA_403_EXTRACTIVE_EVIDENCE_SHADOW_V1"
EXA_HIGHLIGHT_DESCRIPTION_PREFIX = "EXA_SEARCH_HIGHLIGHTS_V1::"
_INSTALLED = False
_UPSTREAM_VERIFY: Callable[..., dict[str, Any]] | None = None


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _exa_descriptions_by_url(benchmark_report: dict[str, Any]) -> dict[str, str]:
    output: dict[str, str] = {}
    for market_row in benchmark_report.get("market_results") or []:
        if not isinstance(market_row, dict):
            continue
        for item in (market_row.get("exa") or {}).get("results") or []:
            if not isinstance(item, dict):
                continue
            url = _compact(item.get("url"))
            description = _compact(item.get("description"))
            if url and description:
                output.setdefault(url, description)
    return output


def _extract_highlight_text(description: str) -> str:
    if not description.startswith(EXA_HIGHLIGHT_DESCRIPTION_PREFIX):
        return ""
    return _compact(description[len(EXA_HIGHLIGHT_DESCRIPTION_PREFIX) :])


def _attach_shadow_assessment(
    row: dict[str, Any], *, description: str
) -> tuple[dict[str, Any], str | None]:
    updated = dict(row)
    updated["provider_extractive_403_shadow_used"] = False
    updated["provider_extractive_403_shadow_source"] = None
    updated["provider_extractive_403_shadow_classification"] = None
    updated["provider_extractive_403_shadow_evidence"] = {}
    updated["provider_extractive_403_shadow_is_qualification_evidence"] = False
    updated["provider_extractive_403_shadow_changes_primary_classification"] = False
    updated["provider_extractive_403_shadow_changes_tool_learning"] = False

    if row.get("classification") != FETCH_FAILED or row.get("status_code") != 403:
        return updated, None

    text = _extract_highlight_text(description)
    if not text:
        return updated, None

    url = _compact(row.get("final_url") or row.get("url"))
    title = _compact(row.get("title"))
    classification, evidence = _classify_page(title=title, text=text, url=url)
    classification, evidence = _verification._qualified_b2b_active_stock(
        classification=classification,
        evidence=evidence,
        title=title,
        text=text,
    )

    updated["provider_extractive_403_shadow_used"] = True
    updated["provider_extractive_403_shadow_source"] = "EXA_SEARCH_HIGHLIGHTS"
    updated["provider_extractive_403_shadow_classification"] = classification
    updated["provider_extractive_403_shadow_evidence"] = evidence
    return updated, classification


def _verify_provider_unique_pages_with_403_shadow(
    benchmark_report: dict[str, Any],
    *,
    provider: str,
    page_fetcher=_verification.fetch_public_page,
    max_page_fetches: int = 18,
) -> dict[str, Any]:
    if _UPSTREAM_VERIFY is None:  # pragma: no cover - installer contract
        raise RuntimeError("Exa 403 extractive shadow is not installed")

    report = _UPSTREAM_VERIFY(
        benchmark_report,
        provider=provider,
        page_fetcher=page_fetcher,
        max_page_fetches=max_page_fetches,
    )
    output = dict(report)
    normalized_provider = _compact(provider).casefold()
    descriptions = _exa_descriptions_by_url(benchmark_report) if normalized_provider == "exa" else {}

    rows: list[dict[str, Any]] = []
    shadow_classifications: list[str] = []
    http_403_count = 0
    highlight_available_count = 0
    for raw in report.get("verified_pages") or []:
        if not isinstance(raw, dict):
            continue
        if raw.get("classification") == FETCH_FAILED and raw.get("status_code") == 403:
            http_403_count += 1
        url = _compact(raw.get("url"))
        updated, shadow_classification = _attach_shadow_assessment(
            raw,
            description=descriptions.get(url, ""),
        )
        if updated.get("provider_extractive_403_shadow_used") is True:
            highlight_available_count += 1
        if shadow_classification:
            shadow_classifications.append(shadow_classification)
        rows.append(updated)

    counts = Counter(shadow_classifications)
    output["verified_pages"] = rows
    output["provider_extractive_403_shadow"] = {
        "version": VERSION,
        "enabled": normalized_provider == "exa",
        "status": "SUCCESS" if highlight_available_count else "VALID_ZERO",
        "http_403_row_count": http_403_count,
        "highlight_evidence_available_count": highlight_available_count,
        "shadow_classification_counts": dict(sorted(counts.items())),
        "shadow_exact_lot_candidate_count": counts[EXACT_LOT_CANDIDATE],
        "search_requests_added": 0,
        "direct_page_fetches_added": 0,
        "primary_classification_changes": 0,
        "exact_lot_decision_changes": 0,
        "tool_learning_decision_changes": 0,
        "qualification_evidence": False,
        "production_mutation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
        "interpretation_guard": (
            "Exa highlights are diagnostic cached/extractive evidence only. HTTP 403 rows remain FETCH_FAILED and cannot become Exact-Lot or Tool Learning credit through this shadow."
        ),
    }
    return output


def install_exa_403_extractive_evidence_shadow_v1() -> None:
    """Wrap the established provider verifier without changing its decisions."""
    global _INSTALLED, _UPSTREAM_VERIFY
    if _INSTALLED:
        return
    _UPSTREAM_VERIFY = _verification.verify_provider_unique_pages
    _verification.verify_provider_unique_pages = _verify_provider_unique_pages_with_403_shadow
    _INSTALLED = True


__all__ = ["VERSION", "install_exa_403_extractive_evidence_shadow_v1"]
