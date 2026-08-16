"""Preserve one canonical opportunity decision across downstream projections.

The checkpoint owns opportunity identity and lifecycle truth. The unified river may
add case-level classification and ranking, but it must not erase that canonical
identity/status. Central Intelligence must also honour the checkpoint-selected
opportunity when that same opportunity is present in the actionable river lane.

This module follows the existing discovery hook pattern: it is deterministic,
read-only, performs no collection, and adds no commercial automation.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from opportunity_engine.discovery import central_intelligence_orchestrator as central
from opportunity_engine.discovery import unified_market_intelligence_river as river


_INSTALLED = False
_ORIGINAL_RIVER_BUILD = None
_ORIGINAL_CENTRAL_BUILD = None
_CANONICAL_KIND = "CANONICAL_OPPORTUNITY"
_COMMERCIAL_CASE_TYPES = {"DIRECT_OPPORTUNITY", "B2B_INVENTORY", "AUCTION_INVENTORY"}


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [item for item in value if isinstance(item, dict)]


def _canonical_truth(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Return singular canonical truth only when the case is unambiguous."""
    by_identity: dict[str, set[str]] = {}
    for item in items:
        if _compact(item.get("record_kind")).upper() != _CANONICAL_KIND:
            continue
        details = item.get("details") if isinstance(item.get("details"), Mapping) else {}
        identity = _compact(details.get("opportunity_identity"))
        if not identity:
            stable = _compact(item.get("stable_identity"))
            if stable.startswith("opportunity:"):
                identity = stable.removeprefix("opportunity:")
        if not identity:
            continue
        workflow = _compact(item.get("commercial_state")).upper()
        by_identity.setdefault(identity, set())
        if workflow:
            by_identity[identity].add(workflow)

    identities = sorted(by_identity)
    if not identities:
        return {}
    result: dict[str, Any] = {"canonical_opportunity_identities": identities}
    if len(identities) != 1:
        return result
    identity = identities[0]
    workflows = sorted(by_identity[identity])
    result["opportunity_identity"] = identity
    result["workflow_status"] = workflows[0] if len(workflows) == 1 else None
    return result


def _hydrate_river_result(result: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    items_report = result.get("items") if isinstance(result.get("items"), dict) else {}
    cases_report = result.get("cases") if isinstance(result.get("cases"), dict) else {}
    brief = result.get("brief") if isinstance(result.get("brief"), dict) else {}

    item_by_id = {
        _compact(item.get("intelligence_id")): item
        for item in _rows(items_report.get("items"))
        if _compact(item.get("intelligence_id"))
    }
    truth_by_case: dict[str, dict[str, Any]] = {}
    for case in _rows(cases_report.get("cases")):
        case_items = [
            item_by_id[item_id]
            for raw_id in case.get("item_ids") or []
            if (item_id := _compact(raw_id)) in item_by_id
        ]
        truth = _canonical_truth(case_items)
        if not truth:
            continue
        case.update(truth)
        case_id = _compact(case.get("case_id"))
        if case_id:
            truth_by_case[case_id] = truth

    card_lists = (
        "decision_cards",
        "actionable_now",
        "verification_required",
        "study_required",
        "market_watch",
        "review_queue",
        "historical_evidence",
    )
    for key in card_lists:
        for card in _rows(brief.get(key)):
            truth = truth_by_case.get(_compact(card.get("case_id")))
            if truth:
                card.update(truth)

    for key in (
        "top_actionable_card",
        "top_verification_required_card",
        "top_study_required_card",
        "top_market_watch_card",
        "top_decision_card",
    ):
        card = brief.get(key)
        if not isinstance(card, dict):
            continue
        truth = truth_by_case.get(_compact(card.get("case_id")))
        if truth:
            card.update(truth)

    result["items"] = items_report
    result["cases"] = cases_report
    result["brief"] = brief
    return result


def _consistent_river_build(*args: Any, **kwargs: Any) -> dict[str, dict[str, Any]]:
    assert _ORIGINAL_RIVER_BUILD is not None
    return _hydrate_river_result(_ORIGINAL_RIVER_BUILD(*args, **kwargs))


def _project_card(card: Mapping[str, Any] | None) -> dict[str, Any] | None:
    projected = central._card_projection(card)
    if projected is None or not isinstance(card, Mapping):
        return projected
    projected["opportunity_identity"] = card.get("opportunity_identity")
    projected["workflow_status"] = card.get("workflow_status")
    projected["canonical_opportunity_identities"] = list(
        card.get("canonical_opportunity_identities") or []
    )
    return projected


def _preferred_opportunity_identity(domain: Mapping[str, Any]) -> str:
    action = domain.get("selected_human_action")
    if not isinstance(action, Mapping):
        return ""
    return _compact(action.get("opportunity_identity"))


def _matching_actionable_card(
    unified: Mapping[str, Any], preferred_identity: str
) -> dict[str, Any] | None:
    if not preferred_identity:
        return None
    for card in _rows(unified.get("actionable_now")):
        if _compact(card.get("case_type")).upper() not in _COMMERCIAL_CASE_TYPES:
            continue
        if _compact(card.get("opportunity_identity")) == preferred_identity:
            return card
    return None


def _hydrate_central_projection(
    projection: Mapping[str, Any] | None,
    unified: Mapping[str, Any],
) -> dict[str, Any] | None:
    if not isinstance(projection, Mapping):
        return None
    case_id = _compact(projection.get("case_id"))
    if not case_id:
        return dict(projection)
    for key in (
        "actionable_now",
        "verification_required",
        "study_required",
        "market_watch",
        "historical_evidence",
    ):
        for card in _rows(unified.get(key)):
            if _compact(card.get("case_id")) == case_id:
                return _project_card(card)
    return dict(projection)


def _consistent_central_build(
    domain_brief: Mapping[str, Any] | None,
    unified_brief: Mapping[str, Any] | None,
    **kwargs: Any,
) -> dict[str, Any]:
    assert _ORIGINAL_CENTRAL_BUILD is not None
    domain = domain_brief if isinstance(domain_brief, Mapping) else {}
    unified = unified_brief if isinstance(unified_brief, Mapping) else {}
    brief = _ORIGINAL_CENTRAL_BUILD(domain_brief, unified_brief, **kwargs)

    opportunity = _hydrate_central_projection(brief.get("top_actionable_opportunity"), unified)
    preferred = _preferred_opportunity_identity(domain)
    preferred_card = _matching_actionable_card(unified, preferred)
    if preferred_card is not None:
        opportunity = _project_card(preferred_card)
    brief["top_actionable_opportunity"] = opportunity

    if isinstance(opportunity, Mapping):
        action = central._primary_action(
            opportunity,
            brief.get("top_verification_required_opportunity"),
            brief.get("top_study_required_opportunity"),
            brief.get("top_fabric_supplier"),
            brief.get("top_market_signal"),
        )
        action["opportunity_identity"] = opportunity.get("opportunity_identity")
        action["workflow_status"] = opportunity.get("workflow_status")
        brief["primary_human_action"] = action

    brief["canonical_decision_truth_preserved"] = True
    brief["checkpoint_preferred_opportunity_identity"] = preferred or None
    return brief


def install_one_decision_consistency() -> None:
    """Install canonical truth propagation after unified decision priority."""
    global _INSTALLED, _ORIGINAL_RIVER_BUILD, _ORIGINAL_CENTRAL_BUILD
    if _INSTALLED:
        return
    _ORIGINAL_RIVER_BUILD = river.build_unified_market_intelligence_river
    _ORIGINAL_CENTRAL_BUILD = central.build_central_intelligence_brief
    river.build_unified_market_intelligence_river = _consistent_river_build
    central.build_central_intelligence_brief = _consistent_central_build
    _INSTALLED = True
