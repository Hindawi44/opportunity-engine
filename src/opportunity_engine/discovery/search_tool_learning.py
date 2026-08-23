"""Conservative Tool Learning scorecard for Exa-vs-Brave shadow evidence.

The scorecard learns only from symmetrically page-verified provider-unique URLs.
Raw search-hit counts are diagnostic and never count as provider quality. A
provider lead may be declared only after at least one page passes the strict
Tool Learning commercial-usefulness gate.
"""
from __future__ import annotations

from typing import Any, Mapping

from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY

SCHEMA_VERSION = "search-tool-learning-scorecard-1.1"
_SUPPORTED_PROVIDERS = frozenset({"exa", "brave"})


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _metrics(report: Mapping[str, Any]) -> dict[str, Any]:
    successful = max(0, int(report.get("page_fetches_succeeded") or 0))
    attempted = max(0, int(report.get("page_fetches_attempted") or 0))
    useful = max(0, int(report.get("useful_clothing_signal_count") or 0))
    out_of_domain = max(0, int(report.get("out_of_domain_count") or 0))
    filtered_active = max(0, int(report.get("non_specific_active_filtered_count") or 0))
    unique_urls = max(0, int(report.get("provider_unique_url_count") or 0))
    useful_yield = useful / successful if successful else 0.0
    out_of_domain_rate = out_of_domain / successful if successful else 0.0
    fetch_success_rate = successful / attempted if attempted else 0.0
    quality_index = useful_yield - out_of_domain_rate
    return {
        "provider_unique_url_count": unique_urls,
        "page_fetches_attempted": attempted,
        "page_fetches_succeeded": successful,
        "fetch_success_rate": round(fetch_success_rate, 4),
        "useful_clothing_signal_count": useful,
        "useful_clothing_yield": round(useful_yield, 4),
        "non_specific_active_filtered_count": filtered_active,
        "out_of_domain_count": out_of_domain,
        "out_of_domain_rate": round(out_of_domain_rate, 4),
        "quality_index": round(quality_index, 4),
    }


def build_search_tool_learning_scorecard(
    exa_verification: Mapping[str, Any],
    brave_verification: Mapping[str, Any],
    *,
    min_successful_pages_per_provider: int = 5,
    minimum_quality_margin: float = 0.05,
) -> dict[str, Any]:
    """Compare Exa and Brave using only symmetric exact-page evidence."""
    if min_successful_pages_per_provider < 1:
        raise ValueError("min_successful_pages_per_provider must be >= 1")
    if not 0.0 <= minimum_quality_margin <= 1.0:
        raise ValueError("minimum_quality_margin must be between 0 and 1")

    reports = {
        _compact(exa_verification.get("provider")).casefold(): exa_verification,
        _compact(brave_verification.get("provider")).casefold(): brave_verification,
    }
    if set(reports) != _SUPPORTED_PROVIDERS:
        raise ValueError("one exa verification and one brave verification are required")

    blocking_reasons: list[str] = []
    for provider in ("exa", "brave"):
        report = reports[provider]
        if report.get("status") != "SUCCESS":
            blocking_reasons.append(f"{provider.upper()}_VERIFICATION_NOT_SUCCESSFUL")
        if report.get("shadow_only") is not True:
            blocking_reasons.append(f"{provider.upper()}_NOT_SHADOW_ONLY")
        if report.get("symmetric_provider_verification") is not True:
            blocking_reasons.append(f"{provider.upper()}_NOT_SYMMETRICALLY_VERIFIED")
        if report.get("commercial_specificity_gate_enforced") is not True:
            blocking_reasons.append(f"{provider.upper()}_COMMERCIAL_SPECIFICITY_GATE_NOT_ENFORCED")
        if report.get("project_domain_gate_enforced") is not True:
            blocking_reasons.append(f"{provider.upper()}_DOMAIN_GATE_NOT_ENFORCED")
        if _compact(report.get("required_project_domain")) != CLOTHING_INVENTORY:
            blocking_reasons.append(f"{provider.upper()}_WRONG_PROJECT_DOMAIN")
        if int(report.get("page_fetches_succeeded") or 0) < min_successful_pages_per_provider:
            blocking_reasons.append(f"{provider.upper()}_VERIFIED_SAMPLE_TOO_SMALL")

    metrics = {
        "exa": _metrics(reports["exa"]),
        "brave": _metrics(reports["brave"]),
    }
    total_useful = sum(int(row["useful_clothing_signal_count"]) for row in metrics.values())
    if total_useful == 0:
        blocking_reasons.append("NO_VERIFIED_USEFUL_COMMERCIAL_PAGES")

    if blocking_reasons:
        decision = "INSUFFICIENT_EVIDENCE"
    else:
        delta = float(metrics["exa"]["quality_index"]) - float(metrics["brave"]["quality_index"])
        if delta > minimum_quality_margin:
            decision = "EXA_LEADS"
        elif delta < -minimum_quality_margin:
            decision = "BRAVE_LEADS"
        else:
            decision = "NO_CLEAR_LEADER"

    return {
        "schema_version": SCHEMA_VERSION,
        "decision": decision,
        "blocking_reasons": list(dict.fromkeys(blocking_reasons)),
        "required_project_domain": CLOTHING_INVENTORY,
        "project_domain_gate_enforced": True,
        "commercial_specificity_gate_enforced": True,
        "comparison_basis": "ITEM_SPECIFIC_VERIFIED_CLOTHING_YIELD_MINUS_OUT_OF_DOMAIN_RATE",
        "min_successful_pages_per_provider": min_successful_pages_per_provider,
        "minimum_quality_margin": minimum_quality_margin,
        "metrics": metrics,
        "interpretation_guard": (
            "A provider cannot lead from raw volume, broad ACTIVE_STOCK_SIGNAL pages, or lower noise alone; at least one item-specific verified commercial clothing page is required."
        ),
        "automatic_provider_activation": False,
        "automatic_provider_disable": False,
        "production_mutation": False,
    }
