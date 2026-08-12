"""Use existing market-comparable evidence to improve the central daily choice.

This layer is deterministic and read-only. It does not search, call a model,
change lifecycle state, or perform commercial actions. It only re-ranks current
commercial ACTIONABLE_NOW cards when the already-produced market benchmark
contains useful evidence, then makes the single human action match that evidence.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

CENTRAL_JSON_FILENAME = "central-intelligence-brief.json"
DOMAIN_JSON_FILENAME = "domain-market-intelligence-brief.json"
UNIFIED_JSON_FILENAME = "unified-daily-decision-brief.json"
COMPARABLES_JSON_FILENAME = "market-comparables-benchmark.json"

_COMMERCIAL_CASE_TYPES = {
    "DIRECT_OPPORTUNITY",
    "B2B_INVENTORY",
    "AUCTION_INVENTORY",
}
_MARKET_CLASS_PRIORITY = {
    "CLEARLY_BELOW_MARKET": 0,
    "BELOW_MARKET_REQUIRES_VERIFICATION": 1,
    "NEAR_MARKET": 2,
    "MARKET_RANGE_AVAILABLE_TARGET_PRICE_MISSING": 3,
    "INSUFFICIENT_COMPARABLES": 4,
    "ABOVE_MARKET": 6,
}


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _benchmark_summary(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    return {
        "benchmark_classification": value.get("benchmark_classification"),
        "confidence": value.get("confidence"),
        "comparable_count": int(value.get("comparable_count") or 0),
        "target_price": deepcopy(value.get("target_price")),
        "wholesale_range": deepcopy(value.get("wholesale_range")),
        "retail_range": deepcopy(value.get("retail_range")),
        "reference_lane": value.get("reference_lane"),
        "target_to_reference_median_ratio": value.get("target_to_reference_median_ratio"),
        "recommended_next_action": value.get("recommended_next_action"),
        "asking_prices_not_completed_sales": True,
        "shipping_included": False,
    }


def _benchmark_by_case(report: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in _rows(report.get("target_benchmarks")):
        case_id = _compact(row.get("case_id"))
        if case_id and case_id not in result:
            result[case_id] = row
    return result


def _card_projection(
    card: Mapping[str, Any], benchmark: Mapping[str, Any] | None
) -> dict[str, Any]:
    projected = {
        "case_id": card.get("case_id"),
        "headline": card.get("headline"),
        "case_type": card.get("case_type"),
        "case_status": card.get("case_status"),
        "decision_lane": card.get("decision_lane"),
        "actionability_tier": card.get("actionability_tier"),
        "actionability_score": card.get("actionability_score"),
        "source_strength": card.get("source_strength", card.get("commercial_strength")),
        "recommended_next_action": card.get("recommended_next_action"),
        "missing_information": list(card.get("missing_information") or []),
        "risk_flags": list(card.get("risk_flags") or []),
        "source_urls": list(card.get("source_urls") or [])[:5],
        "market_benchmark": _benchmark_summary(benchmark),
        "selection_basis": (
            "MARKET_COMPARABLES_THEN_EXISTING_ACTIONABILITY_ORDER"
            if benchmark
            else "EXISTING_ACTIONABILITY_ORDER"
        ),
    }
    return projected


def _market_rank(benchmark: Mapping[str, Any] | None) -> int:
    if not isinstance(benchmark, Mapping):
        return 4
    classification = _compact(benchmark.get("benchmark_classification")).upper()
    return _MARKET_CLASS_PRIORITY.get(classification, 4)


def select_market_aware_opportunity(
    unified: Mapping[str, Any], comparables: Mapping[str, Any]
) -> dict[str, Any] | None:
    """Select among current commercial cards using benchmark evidence when present."""
    cards = [
        card
        for card in _rows(unified.get("actionable_now"))
        if _compact(card.get("case_type")).upper() in _COMMERCIAL_CASE_TYPES
    ]
    if not cards:
        return None

    by_case = _benchmark_by_case(comparables)
    indexed = list(enumerate(cards))
    indexed.sort(
        key=lambda pair: (
            _market_rank(by_case.get(_compact(pair[1].get("case_id")))),
            pair[0],
        )
    )
    _, selected = indexed[0]
    benchmark = by_case.get(_compact(selected.get("case_id")))
    return _card_projection(selected, benchmark)


def _market_action(opportunity: Mapping[str, Any]) -> dict[str, Any]:
    benchmark = opportunity.get("market_benchmark")
    benchmark = benchmark if isinstance(benchmark, Mapping) else {}
    classification = _compact(benchmark.get("benchmark_classification")).upper()
    base = {
        "target_type": opportunity.get("case_type"),
        "target_id": opportunity.get("case_id"),
        "target": opportunity.get("headline"),
        "market_benchmark_classification": classification or None,
        "decision_basis": (
            "MARKET_COMPARABLES_PLUS_EXISTING_ACTIONABILITY"
            if classification
            else "EXISTING_ACTIONABILITY_ONLY"
        ),
    }

    if classification in {"CLEARLY_BELOW_MARKET", "BELOW_MARKET_REQUIRES_VERIFICATION"}:
        return {
            **base,
            "action_type": "VERIFY_LANDED_COST_FOR_BELOW_MARKET_OPPORTUNITY",
            "recommended_next_action": "VERIFY_FINAL_PRICE_SHIPPING_FEES_CONDITION_TAX_AND_LANDED_COST",
            "reason": (
                "Public asking-price comparables place this candidate below the reference market range; "
                "verify the final purchase price and full landed cost before any purchase decision."
            ),
        }
    if classification == "NEAR_MARKET":
        return {
            **base,
            "action_type": "REVIEW_MARGIN_FOR_NEAR_MARKET_OPPORTUNITY",
            "recommended_next_action": "VERIFY_MARGIN_FINAL_PRICE_AND_LANDED_COST_BEFORE_ADVANCING",
            "reason": (
                "The candidate is near the public asking-price reference; margin must be proven before "
                "spending more effort on the deal."
            ),
        }
    if classification == "ABOVE_MARKET":
        return {
            **base,
            "action_type": "DEPRIORITIZE_OR_NEGOTIATE_ABOVE_MARKET_OPPORTUNITY",
            "recommended_next_action": "DO_NOT_ADVANCE_WITHOUT_BETTER_PRICE_OR_STRONGER_EVIDENCE",
            "reason": (
                "The visible target price is above the compatible public asking-price reference before "
                "shipping and other costs, so it should not be advanced without a better price or stronger evidence."
            ),
        }
    if classification == "MARKET_RANGE_AVAILABLE_TARGET_PRICE_MISSING":
        return {
            **base,
            "action_type": "VERIFY_TARGET_PRICE_BEFORE_MARKET_COMPARISON",
            "recommended_next_action": "VERIFY_TARGET_PRICE_AND_UNIT_BASIS",
            "reason": "A market range exists, but the target price is missing, so a commercial comparison cannot yet be completed.",
        }
    if classification == "INSUFFICIENT_COMPARABLES":
        return {
            **base,
            "action_type": "VERIFY_MORE_COMPARABLES_BEFORE_COST_ANALYSIS",
            "recommended_next_action": "GATHER_MORE_COMPATIBLE_COMPARABLES_OR_VERIFY_PRICE_DIRECTLY",
            "reason": "The current benchmark does not contain enough compatible public comparables for a reliable market-position classification.",
        }
    return {
        **base,
        "action_type": "REVIEW_TOP_ACTIONABLE_OPPORTUNITY",
        "recommended_next_action": opportunity.get("recommended_next_action"),
        "reason": "No usable market-position classification is available, so the existing actionability order remains authoritative.",
    }


def apply_market_benchmark_to_brief(
    brief: Mapping[str, Any],
    unified: Mapping[str, Any],
    comparables: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a central brief whose commercial choice uses existing benchmark evidence."""
    result = deepcopy(dict(brief))
    selected = select_market_aware_opportunity(unified, comparables)
    snapshot = result.get("today_snapshot")
    if not isinstance(snapshot, dict):
        snapshot = {}
        result["today_snapshot"] = snapshot

    if selected is None:
        snapshot["market_decision_quality"] = "NO_COMMERCIAL_ACTIONABLE"
        result["decision_quality_policy"] = "MARKET_COMPARABLES_WHEN_AVAILABLE"
        return result

    result["top_actionable_opportunity"] = selected
    result["primary_human_action"] = _market_action(selected)
    benchmark = selected.get("market_benchmark")
    classification = (
        _compact(benchmark.get("benchmark_classification")).upper()
        if isinstance(benchmark, Mapping)
        else ""
    )
    snapshot["market_decision_quality"] = (
        "BENCHMARK_APPLIED" if classification else "UNIFIED_PRIORITY_ONLY"
    )
    snapshot["top_market_benchmark_classification"] = classification or None
    result["decision_quality_policy"] = "MARKET_COMPARABLES_THEN_EXISTING_ACTIONABILITY_ORDER"
    result["market_comparables_are_asking_prices_not_completed_sales"] = True
    result["shipping_still_requires_verification"] = True
    return result


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def apply_market_decision_quality(
    output_dir: str | Path, brief: Mapping[str, Any]
) -> dict[str, Any]:
    """Apply decision quality to final daily artifacts without adding any retrieval."""
    directory = Path(output_dir)
    unified = _read_json(directory / UNIFIED_JSON_FILENAME)
    comparables = _read_json(directory / COMPARABLES_JSON_FILENAME)
    result = apply_market_benchmark_to_brief(brief, unified, comparables)

    _write_json(directory / CENTRAL_JSON_FILENAME, result)

    domain_path = directory / DOMAIN_JSON_FILENAME
    domain = _read_json(domain_path)
    if domain:
        central = domain.get("central_intelligence_orchestrator")
        if not isinstance(central, dict):
            central = {}
            domain["central_intelligence_orchestrator"] = central
        for key in (
            "today_snapshot",
            "top_actionable_opportunity",
            "primary_human_action",
            "decision_quality_policy",
            "market_comparables_are_asking_prices_not_completed_sales",
            "shipping_still_requires_verification",
        ):
            central[key] = deepcopy(result.get(key))
        _write_json(domain_path, domain)
    return result
