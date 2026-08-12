"""Central operator-facing synthesis over the existing intelligence river.

This layer is intentionally deterministic and read-only. It does not collect new
data, call a model, promote records into opportunities, or perform commercial
actions. It turns already-produced daily artifacts into one concise operator
brief with separate opportunity, market-watch, and fabric-procurement views plus
exactly one recommended human action.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "central-intelligence-orchestrator-1.0"
JSON_FILENAME = "central-intelligence-brief.json"
TEXT_FILENAME = "central-intelligence-brief.txt"
DECISION_OWNER = "HUMAN_OPERATOR"

_COMMERCIAL_CASE_TYPES = {
    "DIRECT_OPPORTUNITY",
    "B2B_INVENTORY",
    "AUCTION_INVENTORY",
}
_FABRIC_PRIORITY = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _now_iso(value: object | None = None) -> str:
    text = _compact(value)
    if text:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat()
        except ValueError:
            pass
    return datetime.now(timezone.utc).isoformat()


def _rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _card_projection(card: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(card, Mapping):
        return None
    return {
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
    }


def _top_commercial_opportunity(unified: Mapping[str, Any]) -> dict[str, Any] | None:
    for card in _rows(unified.get("actionable_now")):
        if _compact(card.get("case_type")).upper() in _COMMERCIAL_CASE_TYPES:
            return _card_projection(card)
    top = unified.get("top_actionable_card")
    if isinstance(top, Mapping) and _compact(top.get("case_type")).upper() in _COMMERCIAL_CASE_TYPES:
        return _card_projection(top)
    return None


def _top_market_watch(unified: Mapping[str, Any]) -> dict[str, Any] | None:
    top = unified.get("top_market_watch_card")
    if isinstance(top, Mapping):
        return _card_projection(top)
    rows = _rows(unified.get("market_watch"))
    return _card_projection(rows[0]) if rows else None


def _advisor_by_candidate(advisor: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(advisor, Mapping):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for assessment in _rows(advisor.get("assessments")):
        candidate_id = _compact(assessment.get("candidate_id"))
        if candidate_id:
            result[candidate_id] = assessment
    return result


def _fabric_rank(candidate: Mapping[str, Any], assessment: Mapping[str, Any] | None) -> tuple[Any, ...]:
    priority = _compact((assessment or {}).get("review_priority")).upper()
    ai_rank = _FABRIC_PRIORITY.get(priority, 3)
    try:
        relevance = float(candidate.get("procurement_relevance_score") or 0)
    except (TypeError, ValueError):
        relevance = 0.0
    return (
        ai_rank,
        -relevance,
        _compact(candidate.get("source_name")).casefold(),
        _compact(candidate.get("candidate_id")),
    )


def _top_fabric_supplier(
    fabric: Mapping[str, Any] | None,
    advisor: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(fabric, Mapping):
        return None
    candidates = _rows(fabric.get("candidates"))
    if not candidates:
        return None
    by_id = _advisor_by_candidate(advisor)
    candidates.sort(
        key=lambda item: _fabric_rank(item, by_id.get(_compact(item.get("candidate_id"))))
    )
    candidate = candidates[0]
    assessment = by_id.get(_compact(candidate.get("candidate_id"))) or {}
    return {
        "candidate_id": candidate.get("candidate_id"),
        "source_name": candidate.get("source_name"),
        "source_country": candidate.get("source_country"),
        "location": candidate.get("location"),
        "title": candidate.get("title"),
        "source_url": candidate.get("source_url"),
        "procurement_relevance_score": candidate.get("procurement_relevance_score", 0),
        "price": candidate.get("price"),
        "currency": candidate.get("currency"),
        "quantity": candidate.get("quantity"),
        "quantity_unit": candidate.get("quantity_unit"),
        "ai_review_priority": assessment.get("review_priority"),
        "ai_material_summary": assessment.get("material_summary"),
        "ai_reason": assessment.get("reason"),
        "missing_information": list(assessment.get("missing_information") or []),
        "operator_questions": list(assessment.get("operator_questions") or []),
        "norway_import_checks": list(assessment.get("norway_import_checks") or []),
        "model_output_is_advisory": bool(assessment),
        "source_evidence_required_for_verification": True,
    }


def _market_visibility(domain: Mapping[str, Any]) -> list[str]:
    daily = domain.get("daily_market_visibility")
    if isinstance(daily, Mapping):
        countries = [_compact(value).upper() for value in (daily.get("countries") or [])]
        countries = [value for value in countries if value]
        if countries:
            return list(dict.fromkeys(countries))
    primary = [_compact(value).upper() for value in (domain.get("market_coverage") or [])]
    primary = [value for value in primary if value]
    return list(dict.fromkeys(primary))


def _priority_counts(unified: Mapping[str, Any]) -> dict[str, int]:
    raw = unified.get("priority_counts")
    if isinstance(raw, Mapping):
        return {
            "ACTIONABLE_NOW": int(raw.get("ACTIONABLE_NOW") or 0),
            "MARKET_WATCH": int(raw.get("MARKET_WATCH") or 0),
            "HISTORICAL_EVIDENCE": int(raw.get("HISTORICAL_EVIDENCE") or 0),
        }
    return {
        "ACTIONABLE_NOW": len(_rows(unified.get("actionable_now"))),
        "MARKET_WATCH": len(_rows(unified.get("market_watch"))),
        "HISTORICAL_EVIDENCE": len(_rows(unified.get("historical_evidence"))),
    }


def _primary_action(
    opportunity: Mapping[str, Any] | None,
    fabric: Mapping[str, Any] | None,
    market_watch: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if isinstance(opportunity, Mapping):
        return {
            "action_type": "REVIEW_TOP_ACTIONABLE_OPPORTUNITY",
            "target_type": opportunity.get("case_type"),
            "target_id": opportunity.get("case_id"),
            "target": opportunity.get("headline"),
            "recommended_next_action": opportunity.get("recommended_next_action"),
            "reason": "A current commercial opportunity or offer is actionable before watch-only signals.",
        }
    if isinstance(fabric, Mapping):
        checks = list(fabric.get("missing_information") or [])
        if not checks:
            checks = list(fabric.get("operator_questions") or [])
        return {
            "action_type": "VERIFY_TOP_FABRIC_SUPPLIER",
            "target_type": "FABRIC_PROCUREMENT",
            "target_id": fabric.get("candidate_id"),
            "target": fabric.get("source_name") or fabric.get("title"),
            "recommended_next_action": "VERIFY_PRICE_MOQ_QUANTITY_COMPOSITION_WIDTH_AND_SHIPPING_TO_NORWAY",
            "reason": (
                f"Highest current fabric review priority: {fabric.get('ai_review_priority')}"
                if fabric.get("ai_review_priority")
                else "Highest current fabric procurement candidate by source-backed relevance."
            ),
            "verification_focus": checks[:8],
        }
    if isinstance(market_watch, Mapping):
        return {
            "action_type": "VERIFY_TOP_MARKET_SIGNAL",
            "target_type": market_watch.get("case_type"),
            "target_id": market_watch.get("case_id"),
            "target": market_watch.get("headline"),
            "recommended_next_action": market_watch.get("recommended_next_action"),
            "reason": "No current commercial opportunity or fabric candidate outranks the top watch signal.",
        }
    return {
        "action_type": "NO_IMMEDIATE_ACTION_CONTINUE_MONITORING",
        "target_type": None,
        "target_id": None,
        "target": None,
        "recommended_next_action": "CONTINUE_DAILY_MONITORING",
        "reason": "No actionable opportunity, fabric candidate, or market-watch signal is available.",
    }


def build_central_intelligence_brief(
    domain_brief: Mapping[str, Any] | None,
    unified_brief: Mapping[str, Any] | None,
    *,
    fabric_report: Mapping[str, Any] | None = None,
    fabric_advisor: Mapping[str, Any] | None = None,
    market_comparables: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one deterministic operator summary from existing daily artifacts."""
    domain = domain_brief if isinstance(domain_brief, Mapping) else {}
    unified = unified_brief if isinstance(unified_brief, Mapping) else {}
    fabric = fabric_report if isinstance(fabric_report, Mapping) else {}
    advisor = fabric_advisor if isinstance(fabric_advisor, Mapping) else {}
    comparables = market_comparables if isinstance(market_comparables, Mapping) else {}

    opportunity = _top_commercial_opportunity(unified)
    watch = _top_market_watch(unified)
    top_fabric = _top_fabric_supplier(fabric, advisor)
    counts = _priority_counts(unified)
    generated_at = _now_iso(unified.get("generated_at") or domain.get("generated_at"))

    unified_status = _compact(unified.get("status")).upper() or "MISSING"
    fabric_candidates = int(fabric.get("candidate_count") or len(_rows(fabric.get("candidates"))))
    if not unified and not domain and not fabric:
        status = "VALID_ZERO"
    elif unified_status in {"FAILED_INPUTS", "PARTIAL_SUCCESS_WITH_INPUT_ERRORS"}:
        status = "PARTIAL_SUCCESS"
    elif not unified:
        status = "PARTIAL_SUCCESS"
    elif (
        unified.get("truthful_zero_result") is True
        and not opportunity
        and not watch
        and fabric_candidates == 0
    ):
        status = "VALID_ZERO"
    else:
        status = "SUCCESS"

    advisor_status = _compact(advisor.get("status")).upper() or "NOT_AVAILABLE"
    comparables_status = _compact(comparables.get("status")).upper() or "NOT_AVAILABLE"

    primary_action = _primary_action(opportunity, top_fabric, watch)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": status,
        "purpose": "ONE_OPERATOR_VIEW_OVER_EXISTING_DAILY_INTELLIGENCE",
        "market_visibility": _market_visibility(domain),
        "primary_opportunity_markets": list(domain.get("market_coverage") or []),
        "today_snapshot": {
            "river_status": unified_status,
            "actionable_now_count": counts["ACTIONABLE_NOW"],
            "market_watch_count": counts["MARKET_WATCH"],
            "historical_evidence_count": counts["HISTORICAL_EVIDENCE"],
            "fabric_candidate_count": fabric_candidates,
            "fabric_ai_status": advisor_status,
            "market_comparables_status": comparables_status,
        },
        "top_actionable_opportunity": opportunity,
        "top_market_signal": watch,
        "top_fabric_supplier": top_fabric,
        "primary_human_action": primary_action,
        "single_human_action_enforced": True,
        "model_output_is_advisory": True,
        "source_evidence_remains_authoritative": True,
        "promotion_to_opportunity_allowed": False,
        "decision_owner": DECISION_OWNER,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
        "output_files": [JSON_FILENAME, TEXT_FILENAME],
    }


def render_central_intelligence_text(brief: Mapping[str, Any]) -> str:
    visibility = " | ".join(brief.get("market_visibility") or []) or "NONE"
    snapshot = brief.get("today_snapshot") if isinstance(brief.get("today_snapshot"), Mapping) else {}
    opportunity = brief.get("top_actionable_opportunity") if isinstance(brief.get("top_actionable_opportunity"), Mapping) else {}
    watch = brief.get("top_market_signal") if isinstance(brief.get("top_market_signal"), Mapping) else {}
    fabric = brief.get("top_fabric_supplier") if isinstance(brief.get("top_fabric_supplier"), Mapping) else {}
    action = brief.get("primary_human_action") if isinstance(brief.get("primary_human_action"), Mapping) else {}
    lines = [
        "CENTRAL INTELLIGENCE ORCHESTRATOR",
        f"status: {brief.get('status')}",
        f"daily_market_visibility: {visibility}",
        f"actionable_now: {snapshot.get('actionable_now_count', 0)}",
        f"market_watch: {snapshot.get('market_watch_count', 0)}",
        f"fabric_candidates: {snapshot.get('fabric_candidate_count', 0)}",
        f"fabric_ai_status: {snapshot.get('fabric_ai_status') or 'NOT_AVAILABLE'}",
        "",
        "أهم فرصة قابلة للمراجعة الآن:",
        f"- {opportunity.get('headline') or 'NONE'}",
        "أهم إشارة سوق للمراقبة:",
        f"- {watch.get('headline') or 'NONE'}",
        "أفضل مورد أقمشة للمراجعة:",
        (
            f"- {fabric.get('source_name') or fabric.get('title') or 'NONE'}"
            + (f" | AI={fabric.get('ai_review_priority')}" if fabric.get("ai_review_priority") else "")
        ),
        "",
        "الإجراء البشري الوحيد:",
        f"- {action.get('action_type')}: {action.get('target') or action.get('recommended_next_action')}",
        f"reason: {action.get('reason')}",
        "decision_owner: HUMAN_OPERATOR",
        "automatic_purchase: false",
    ]
    return "\n".join(lines) + "\n"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _attach_to_domain_brief(output_dir: Path, brief: Mapping[str, Any]) -> None:
    path = output_dir / "domain-market-intelligence-brief.json"
    payload = _read_json(path)
    if payload is not None:
        payload["central_intelligence_orchestrator"] = {
            "schema_version": brief.get("schema_version"),
            "status": brief.get("status"),
            "market_visibility": brief.get("market_visibility"),
            "today_snapshot": brief.get("today_snapshot"),
            "top_actionable_opportunity": brief.get("top_actionable_opportunity"),
            "top_market_signal": brief.get("top_market_signal"),
            "top_fabric_supplier": brief.get("top_fabric_supplier"),
            "primary_human_action": brief.get("primary_human_action"),
            "single_human_action_enforced": True,
            "decision_owner": DECISION_OWNER,
            "automatic_purchase": False,
            "output_files": brief.get("output_files"),
        }
        _write_json(path, payload)

    text_path = output_dir / "domain-market-intelligence-brief.txt"
    if text_path.exists():
        text = text_path.read_text(encoding="utf-8")
        marker = "CENTRAL INTELLIGENCE ORCHESTRATOR"
        if marker not in text:
            with text_path.open("a", encoding="utf-8") as handle:
                handle.write("\n" + render_central_intelligence_text(brief))


def write_central_intelligence_orchestrator(output_dir: str | Path) -> dict[str, Any]:
    """Read final daily projections and write one central operator brief."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    domain = _read_json(directory / "domain-market-intelligence-brief.json")
    unified = _read_json(directory / "unified-daily-decision-brief.json")
    fabric = _read_json(directory / "fabric-procurement-watch.json")
    advisor = _read_json(directory / "openai-fabric-procurement-advisor.json")
    comparables = _read_json(directory / "market-comparables-benchmark.json")
    brief = build_central_intelligence_brief(
        domain,
        unified,
        fabric_report=fabric,
        fabric_advisor=advisor,
        market_comparables=comparables,
    )
    _write_json(directory / JSON_FILENAME, brief)
    (directory / TEXT_FILENAME).write_text(
        render_central_intelligence_text(brief),
        encoding="utf-8",
    )
    _attach_to_domain_brief(directory, brief)
    return brief
