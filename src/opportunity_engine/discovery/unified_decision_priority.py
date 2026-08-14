"""Prioritise unified river cases by verified commercial actionability.

Every commercial case is routed through the source-agnostic universal verification
gate. Known opportunity profiles must satisfy their minimum evidence contract.
Credible commercial cases that do not fit a known profile are preserved in a
STUDY_REQUIRED lane instead of being rejected or forced through the wrong matrix.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from opportunity_engine.discovery import unified_market_intelligence_river as river
from opportunity_engine.discovery.universal_opportunity_verification_gate import (
    ACTIONABLE_NOW,
    HISTORICAL_EVIDENCE,
    MARKET_WATCH,
    STUDY_REQUIRED,
    VERIFICATION_REQUIRED,
    classify_opportunity_verification,
)

PRIORITY_SCHEMA_VERSION = "unified-decision-priority-1.2"

_ORIGINAL_BUILD = river.build_unified_market_intelligence_river
_ORIGINAL_ATTACH = river._attach_to_existing_brief
_INSTALLED = False


def _compact(value: object) -> str:
    return " ".join(str(value or "").split())


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _snapshot(card: Mapping[str, Any]) -> Mapping[str, Any]:
    value = card.get("commercial_snapshot")
    return value if isinstance(value, Mapping) else {}


def _has_values(card: Mapping[str, Any], key: str) -> bool:
    value = _snapshot(card).get(key)
    return isinstance(value, list) and bool(value)


def _priority_tier(card: Mapping[str, Any], lane: str) -> tuple[int, str]:
    case_type = _compact(card.get("case_type")).upper()
    case_status = _compact(card.get("case_status")).upper()
    direct_count = int(card.get("direct_opportunity_count") or 0)
    offer_count = int(card.get("offer_count") or 0)
    has_price = _has_values(card, "prices")
    has_quantity = _has_values(card, "quantities")

    if lane == HISTORICAL_EVIDENCE:
        return 90, "HISTORICAL_REFERENCE_ONLY"
    if lane == STUDY_REQUIRED:
        return 16, "NONSTANDARD_COMMERCIAL_CASE_STUDY"
    if lane == VERIFICATION_REQUIRED:
        if direct_count > 0 or case_type == "DIRECT_OPPORTUNITY":
            return 12, "DIRECT_OPPORTUNITY_VERIFICATION_REQUIRED"
        if case_type == "B2B_INVENTORY":
            return 13, "B2B_STANDARD_VERIFICATION_REQUIRED"
        if case_type == "AUCTION_INVENTORY":
            return 14, "AUCTION_STANDARD_VERIFICATION_REQUIRED"
        return 15, "COMMERCIAL_VERIFICATION_REQUIRED"
    if lane == ACTIONABLE_NOW:
        if direct_count > 0 or case_type == "DIRECT_OPPORTUNITY":
            if case_status == "QUALIFIED_OPPORTUNITY":
                return 1, "QUALIFIED_DIRECT_OPPORTUNITY"
            return 2, "VERIFIED_DIRECT_OPPORTUNITY"
        if case_type == "B2B_INVENTORY" or (
            offer_count > 0 and case_type not in {"AUCTION_INVENTORY", "FABRIC_PROCUREMENT"}
        ):
            if has_price and has_quantity:
                return 4, "B2B_OFFER_WITH_PRICE_AND_QUANTITY"
            return 5, "B2B_OFFER_REQUIRES_REVIEW"
        if case_type == "AUCTION_INVENTORY":
            return 6, "VERIFIED_AUCTION_REVIEW"
        if case_type == "FABRIC_PROCUREMENT":
            return 7, "FABRIC_PROCUREMENT_REVIEW"
        return 8, "LINKED_COMMERCIAL_CASE_REQUIRES_REVIEW"
    if case_type == "BRIDAL_LIQUIDATION":
        return 20, "BRIDAL_MARKET_WATCH"
    if case_type == "COMPANY_LIQUIDATION":
        return 21, "INVENTORY_RELEASE_WATCH"
    if case_type == "MARKET_SIGNAL_WATCH":
        return 22, "EARLY_MARKET_SIGNAL_WATCH"
    return 23, "MARKET_WATCH_REQUIRES_VERIFICATION"


def _actionability_score(card: Mapping[str, Any], lane: str, tier: int) -> float:
    base_by_tier = {
        1: 98.0,
        2: 94.0,
        4: 86.0,
        5: 80.0,
        6: 76.0,
        7: 68.0,
        8: 64.0,
        12: 58.0,
        13: 55.0,
        14: 53.0,
        15: 50.0,
        16: 48.0,
        20: 44.0,
        21: 40.0,
        22: 32.0,
        23: 28.0,
        90: 0.0,
    }
    score = base_by_tier.get(tier, 25.0)
    case_status = _compact(card.get("case_status")).upper()
    if case_status == "QUALIFIED_OPPORTUNITY":
        score += 2.0
    elif case_status == "ACTIVE_REQUIRES_VERIFICATION":
        score += 1.0

    if _has_values(card, "prices"):
        score += 2.5
    if _has_values(card, "quantities"):
        score += 2.5
    if _has_values(card, "brands"):
        score += 1.0

    source_strength = _number(card.get("commercial_strength")) or 0.0
    score += min(3.0, source_strength / 35.0)
    score -= min(5.0, len(card.get("risk_flags") or []) * 0.75)
    score -= min(5.0, len(card.get("missing_information") or []) * 0.35)
    if lane == HISTORICAL_EVIDENCE:
        score = 0.0
    return round(max(0.0, min(100.0, score)), 2)


def _priority_reasons(
    card: Mapping[str, Any],
    lane: str,
    priority_class: str,
    gate: Mapping[str, Any],
) -> list[str]:
    reasons = [
        f"LANE_{lane}",
        priority_class,
        f"GATE_{_compact(gate.get('reason_code')).upper()}",
    ]
    if int(card.get("direct_opportunity_count") or 0) > 0:
        reasons.append("DIRECT_OPPORTUNITY_PRESENT")
    if int(card.get("offer_count") or 0) > 0:
        reasons.append("COMMERCIAL_OFFER_PRESENT")
    if _has_values(card, "prices"):
        reasons.append("PRICE_VISIBLE")
    if _has_values(card, "quantities"):
        reasons.append("QUANTITY_VISIBLE")
    if _has_values(card, "brands"):
        reasons.append("BRAND_INFORMATION_VISIBLE")
    if gate.get("study_required") is True:
        reasons.append("CUSTOM_STUDY_PROFILE_REQUIRED")
    if not card.get("risk_flags"):
        reasons.append("NO_EXPLICIT_RISK_FLAG")
    return reasons


def _decorate(card: Mapping[str, Any]) -> dict[str, Any]:
    decorated = dict(card)
    gate = classify_opportunity_verification(card)
    lane = str(gate["route"])
    tier, priority_class = _priority_tier(card, lane)
    decorated.update(
        {
            "decision_lane": lane,
            "actionability_tier": tier,
            "priority_class": priority_class,
            "actionability_score": _actionability_score(card, lane, tier),
            "source_strength": card.get("commercial_strength"),
            "verification_gate": gate,
            "priority_reasons": _priority_reasons(card, lane, priority_class, gate),
        }
    )
    return decorated


def _sort_key(card: Mapping[str, Any]) -> tuple[Any, ...]:
    lane_order = {
        ACTIONABLE_NOW: 0,
        VERIFICATION_REQUIRED: 1,
        STUDY_REQUIRED: 2,
        MARKET_WATCH: 3,
        HISTORICAL_EVIDENCE: 4,
    }
    return (
        lane_order.get(_compact(card.get("decision_lane")).upper(), 5),
        int(card.get("actionability_tier") or 999),
        -float(card.get("actionability_score") or 0.0),
        -float(card.get("source_strength") or 0.0),
        _compact(card.get("headline")).casefold(),
        _compact(card.get("case_id")),
    )


def prioritise_decision_cards(
    cards: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Return all cards, actionable cards, review queue, and historical cards.

    The review queue preserves API arity for existing callers and contains the
    VERIFICATION_REQUIRED, STUDY_REQUIRED, and MARKET_WATCH lanes in priority order.
    """
    decorated = sorted((_decorate(card) for card in cards), key=_sort_key)
    actionable = [card for card in decorated if card["decision_lane"] == ACTIONABLE_NOW]
    review = [
        card
        for card in decorated
        if card["decision_lane"] in {VERIFICATION_REQUIRED, STUDY_REQUIRED, MARKET_WATCH}
    ]
    historical = [card for card in decorated if card["decision_lane"] == HISTORICAL_EVIDENCE]
    return decorated, actionable, review, historical


def _apply_priority(result: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    brief = result.get("brief") if isinstance(result.get("brief"), dict) else {}
    cards = brief.get("decision_cards") if isinstance(brief.get("decision_cards"), list) else []
    all_cards, actionable, review, historical = prioritise_decision_cards(
        [card for card in cards if isinstance(card, Mapping)]
    )
    verification = [card for card in review if card["decision_lane"] == VERIFICATION_REQUIRED]
    study = [card for card in review if card["decision_lane"] == STUDY_REQUIRED]
    watch = [card for card in review if card["decision_lane"] == MARKET_WATCH]
    priority_counts = {
        ACTIONABLE_NOW: len(actionable),
        VERIFICATION_REQUIRED: len(verification),
        STUDY_REQUIRED: len(study),
        MARKET_WATCH: len(watch),
        HISTORICAL_EVIDENCE: len(historical),
    }
    top_decision = (
        actionable[0]
        if actionable
        else verification[0]
        if verification
        else study[0]
        if study
        else watch[0]
        if watch
        else historical[0]
        if historical
        else None
    )
    brief.update(
        {
            "priority_schema_version": PRIORITY_SCHEMA_VERSION,
            "decision_cards": all_cards,
            "actionable_now": actionable,
            "verification_required": verification,
            "study_required": study,
            "market_watch": watch,
            "review_queue": review,
            "historical_evidence": historical,
            "priority_counts": priority_counts,
            "top_actionable_card": actionable[0] if actionable else None,
            "top_verification_required_card": verification[0] if verification else None,
            "top_study_required_card": study[0] if study else None,
            "top_market_watch_card": watch[0] if watch else None,
            "top_decision_card": top_decision,
            "priority_rule": "VERIFIED_ACTIONABILITY_THEN_VERIFICATION_THEN_STUDY_THEN_WATCH",
            "universal_verification_gate_enabled": True,
        }
    )

    cases_report = result.get("cases") if isinstance(result.get("cases"), dict) else {}
    cases = cases_report.get("cases") if isinstance(cases_report.get("cases"), list) else []
    card_by_id = {_compact(card.get("case_id")): card for card in all_cards}
    enriched_cases: list[dict[str, Any]] = []
    for raw in cases:
        if not isinstance(raw, Mapping):
            continue
        case = dict(raw)
        card = card_by_id.get(_compact(case.get("case_id")))
        if card:
            for key in (
                "decision_lane",
                "actionability_tier",
                "priority_class",
                "actionability_score",
                "source_strength",
                "priority_reasons",
                "verification_gate",
            ):
                case[key] = card.get(key)
        enriched_cases.append(case)
    enriched_cases.sort(
        key=lambda case: _sort_key(
            {
                **case,
                "headline": case.get("case_title"),
                "source_strength": case.get("source_strength", case.get("commercial_strength")),
            }
        )
    )
    cases_report.update(
        {
            "priority_schema_version": PRIORITY_SCHEMA_VERSION,
            "priority_counts": priority_counts,
            "universal_verification_gate_enabled": True,
            "cases": enriched_cases,
        }
    )
    result["brief"] = brief
    result["cases"] = cases_report
    return result


def _prioritised_build(*args: Any, **kwargs: Any) -> dict[str, dict[str, Any]]:
    return _apply_priority(_ORIGINAL_BUILD(*args, **kwargs))


def _attach_priority_to_existing_brief(output_dir: Path, brief: Mapping[str, Any]) -> None:
    _ORIGINAL_ATTACH(output_dir, brief)
    path = output_dir / "domain-market-intelligence-brief.json"
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict):
            river_summary = payload.get("unified_market_intelligence_river")
            if isinstance(river_summary, dict):
                river_summary.update(
                    {
                        "priority_schema_version": brief.get("priority_schema_version"),
                        "priority_rule": brief.get("priority_rule"),
                        "priority_counts": brief.get("priority_counts"),
                        "top_actionable_card": brief.get("top_actionable_card"),
                        "top_verification_required_card": brief.get("top_verification_required_card"),
                        "top_study_required_card": brief.get("top_study_required_card"),
                        "top_market_watch_card": brief.get("top_market_watch_card"),
                        "top_decision_card": brief.get("top_decision_card"),
                        "universal_verification_gate_enabled": True,
                    }
                )
                path.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )

    text_path = output_dir / "domain-market-intelligence-brief.txt"
    if not text_path.exists():
        return
    text = text_path.read_text(encoding="utf-8")
    marker = "UNIFIED DECISION PRIORITY"
    if marker in text:
        return
    counts = brief.get("priority_counts") if isinstance(brief.get("priority_counts"), Mapping) else {}
    actionable = brief.get("top_actionable_card") if isinstance(brief.get("top_actionable_card"), Mapping) else {}
    verification = brief.get("top_verification_required_card") if isinstance(brief.get("top_verification_required_card"), Mapping) else {}
    study = brief.get("top_study_required_card") if isinstance(brief.get("top_study_required_card"), Mapping) else {}
    watch = brief.get("top_market_watch_card") if isinstance(brief.get("top_market_watch_card"), Mapping) else {}
    with text_path.open("a", encoding="utf-8") as handle:
        handle.write(
            f"\n{marker}\n"
            f"actionable_now: {counts.get(ACTIONABLE_NOW, 0)}\n"
            f"verification_required: {counts.get(VERIFICATION_REQUIRED, 0)}\n"
            f"study_required: {counts.get(STUDY_REQUIRED, 0)}\n"
            f"market_watch: {counts.get(MARKET_WATCH, 0)}\n"
            f"historical_evidence: {counts.get(HISTORICAL_EVIDENCE, 0)}\n"
            f"top_actionable: {actionable.get('headline') or 'NONE'}\n"
            f"top_verification_required: {verification.get('headline') or 'NONE'}\n"
            f"top_study_required: {study.get('headline') or 'NONE'}\n"
            f"top_market_watch: {watch.get('headline') or 'NONE'}\n"
            "priority_rule: VERIFIED_ACTIONABILITY_THEN_VERIFICATION_THEN_STUDY_THEN_WATCH\n"
            "decision_owner: HUMAN_OPERATOR\n"
        )


def install_unified_decision_priority() -> None:
    """Install the bounded priority projection on the unified river module."""
    global _INSTALLED
    if _INSTALLED:
        return
    river.build_unified_market_intelligence_river = _prioritised_build
    river._attach_to_existing_brief = _attach_priority_to_existing_brief
    _INSTALLED = True
