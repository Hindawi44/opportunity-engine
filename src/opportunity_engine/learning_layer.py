"""Unified read-only review plane over the project's learning subsystems."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "learning-layer-review-1.1"
OUTPUT_JSON = "learning-layer-review.json"
OUTPUT_TEXT = "learning-layer-review.txt"
_PRIORITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _provider_comparison_status(memory: Mapping[str, Any]) -> str:
    observations = _rows(memory.get("observations"))
    if observations:
        value = _text(observations[-1].get("provider_preference_status")).upper()
        if value:
            return value
    return "PROVIDER_COMPARISON_NOT_EVALUATED"


def _replicated_route_items(memory: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    worked: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    for route in _rows(memory.get("route_learning")):
        if _text(route.get("status")).upper() != "REPLICATED_FOR_REVIEW":
            continue
        provider = _text(route.get("provider")).lower()
        market = _text(route.get("market_code")).upper()
        domain = _text(route.get("parent_domain") or route.get("result_domain"))
        count = _int(route.get("independent_run_count"))
        verified_urls = route.get("verified_exact_lot_urls") or route.get("exact_lot_urls") or []
        exact_count = _int(route.get("verified_exact_lot_url_count")) or len(verified_urls)
        evidence = {
            "kind": "REPLICATED_SEARCH_ROUTE", "provider": provider, "market_code": market,
            "parent_domain": domain, "pathway": _text(route.get("pathway")),
            "independent_run_count": count,
            "supporting_run_ids": [_text(item) for item in (route.get("supporting_run_ids") or []) if _text(item)],
            "exact_lot_count": exact_count, "status": "REPLICATED_FOR_REVIEW",
        }
        worked.append(dict(evidence))
        reviews.append({**evidence, "priority": "HIGH", "review_action": "REVIEW_REPLICATED_ROUTE", "automatic_activation": False})
    return worked, reviews


def _root_cause_items(feedback: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    failed: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    for route in _rows(feedback.get("routes")):
        if _text(route.get("route_status")).upper() != "ACTIVE":
            continue
        item = {
            "kind": "MISSED_OPPORTUNITY_ROOT_CAUSE", "case_id": _text(route.get("case_id")),
            "market_code": _text(route.get("market_code")).upper(),
            "root_cause": _text(route.get("root_cause")).upper(),
            "mechanism": _text(route.get("mechanism")).upper(),
            "priority": _text(route.get("priority")).upper() or "MEDIUM",
            "repeat_miss": route.get("repeat_miss") is True,
            "learning_status": _text(route.get("learning_status")).upper(),
            "review_action": _text(route.get("action")).upper() or "REVIEW_PIPELINE_GAP",
            "automatic_adaptation_available": route.get("automatic_adaptation_available") is True,
        }
        failed.append(dict(item)); reviews.append(dict(item))
    return failed, reviews


def _search_experiment_rejection_items(unified_memory: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Expose persisted Search Experiment verifier failures to Learning Layer."""
    failed: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    for row in _rows(unified_memory.get("evidence_memory")):
        if _text(row.get("result_type")).upper() != "SEARCH_RESULT_REJECTION":
            continue
        if _text(row.get("latest_outcome")).upper() != "REJECTED":
            continue
        reason = _text(row.get("latest_miss_reason")).upper() or "UNDIAGNOSED"
        item = {
            "kind": "SEARCH_EXPERIMENT_REJECTION",
            "case_id": _text(row.get("learning_evidence_id")),
            "market_code": _text(row.get("market_code")).upper(),
            "project_domain": _text(row.get("project_domain")).upper(),
            "provider": _text(row.get("provider")).lower(),
            "query": _text(row.get("query")),
            "url": _text(row.get("url")) or None,
            "root_cause": reason,
            "priority": "MEDIUM",
            "review_action": "REVIEW_SEARCH_REJECTION_REASON",
            "automatic_adaptation_available": False,
        }
        failed.append(dict(item)); reviews.append(dict(item))
    return failed, reviews


def _daily_learning_items(daily: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    worked: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    proven_this_run = _int(daily.get("proven_term_count_this_run"))
    shadow_count = _int(daily.get("shadow_proven_term_count"))
    eligible = _int(daily.get("safe_learning_promotion_eligible_count"))
    if proven_this_run > 0 or shadow_count > 0:
        worked.append({"kind": "SHADOW_KEYWORD_LEARNING", "proven_term_count_this_run": proven_this_run, "shadow_proven_term_count": shadow_count, "search_status": _text(daily.get("search_status")).upper(), "promotion_gate_enforced": daily.get("promotion_gate_enforced") is True})
    if eligible > 0:
        reviews.append({"kind": "SHADOW_KEYWORD_PROMOTION_REVIEW", "priority": "MEDIUM", "promotion_eligible_count": eligible, "review_action": "REVIEW_SHADOW_KEYWORD_EVIDENCE", "automatic_activation": False})
    return worked, reviews


def _sort_review_queue(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: (_PRIORITY_ORDER.get(_text(item.get("priority")).upper(), 9), _text(item.get("kind")), _text(item.get("market_code")), _text(item.get("case_id")), _text(item.get("parent_domain"))))


def build_learning_layer_review(*, search_success_memory: Mapping[str, Any] | None, root_cause_feedback: Mapping[str, Any] | None, daily_learning: Mapping[str, Any] | None, unified_memory: Mapping[str, Any] | None = None) -> dict[str, Any]:
    memory = _mapping(search_success_memory)
    feedback = _mapping(root_cause_feedback)
    daily = _mapping(daily_learning)
    unified = _mapping(unified_memory)

    route_worked, route_reviews = _replicated_route_items(memory)
    miss_failed, miss_reviews = _root_cause_items(feedback)
    search_failed, search_reviews = _search_experiment_rejection_items(unified)
    keyword_worked, keyword_reviews = _daily_learning_items(daily)

    worked = [*route_worked, *keyword_worked]
    failed = [*miss_failed, *search_failed]
    queue = _sort_review_queue([*route_reviews, *miss_reviews, *search_reviews, *keyword_reviews])
    status = "REVIEW_REQUIRED" if queue else ("MONITOR_ONLY" if worked or failed else "VALID_ZERO_NO_REVIEW_ITEMS")

    return {
        "schema_version": SCHEMA_VERSION, "status": status, "generated_at": daily.get("generated_at"),
        "input_presence": {"search_success_memory": bool(memory), "root_cause_feedback": bool(feedback), "daily_learning": bool(daily), "unified_memory": bool(unified)},
        "search_success_run_count": _int(memory.get("run_count")),
        "replicated_search_route_count": len(route_reviews),
        "active_root_cause_route_count": len(miss_reviews),
        "search_experiment_rejection_count": len(search_reviews),
        "shadow_keyword_promotion_review_count": len(keyword_reviews),
        "what_worked_count": len(worked), "what_failed_count": len(failed), "review_item_count": len(queue),
        "what_worked": worked, "what_failed": failed, "review_queue": queue,
        "provider_comparison_status": _provider_comparison_status(memory),
        "learning_contract": "Observe -> diagnose -> shadow learn -> replicate -> review. Search Experiment rejections are visible but never auto-adapt production.",
        "automatic_query_activation": False, "automatic_provider_activation": False,
        "automatic_source_promotion": False, "automatic_code_change": False,
        "production_query_mutation": False, "production_mutation": False,
        "automatic_contact": False, "automatic_bid": False, "automatic_reservation": False,
        "automatic_purchase": False, "automatic_payment": False,
    }


def render_learning_layer_review(review: Mapping[str, Any]) -> str:
    lines = [
        "LEARNING LAYER:", f"status: {_text(review.get('status'))}",
        f"what worked: {_int(review.get('what_worked_count'))}",
        f"what failed: {_int(review.get('what_failed_count'))}",
        f"search rejections: {_int(review.get('search_experiment_rejection_count'))}",
        f"review items: {_int(review.get('review_item_count'))}",
    ]
    queue = _rows(review.get("review_queue"))
    if queue:
        top = queue[0]
        lines.append("top review: " + " / ".join(part for part in (_text(top.get("priority")), _text(top.get("kind")), _text(top.get("market_code")), _text(top.get("review_action"))) if part))
    lines.append("production mutation: disabled")
    return "\n".join(lines) + "\n"


def _attach_to_brief(output_dir: Path, review: Mapping[str, Any]) -> None:
    path = output_dir / "domain-market-intelligence-brief.json"
    brief = _read_json(path)
    if not brief:
        return
    brief["learning_layer"] = {key: review.get(key) for key in (
        "schema_version", "status", "search_success_run_count", "replicated_search_route_count",
        "active_root_cause_route_count", "search_experiment_rejection_count",
        "shadow_keyword_promotion_review_count", "what_worked_count", "what_failed_count",
        "review_item_count", "provider_comparison_status", "automatic_query_activation",
        "automatic_provider_activation", "automatic_source_promotion", "production_mutation",
    )}
    _write_json(path, brief)


def _append_phone_summary(output_dir: Path, text: str) -> None:
    path = output_dir / "multi-market-phone-summary.txt"
    if not path.exists():
        return
    current = path.read_text(encoding="utf-8")
    marker = "LEARNING LAYER:"
    if marker in current:
        current = current.split(marker, 1)[0].rstrip() + "\n"
    path.write_text(current.rstrip() + "\n\n" + text, encoding="utf-8")


def write_learning_layer_review(output_dir: str | Path, *, input_root: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    root = Path(input_root)
    review = build_learning_layer_review(
        search_success_memory=_read_json(root / "learning" / "search-success-memory.json"),
        root_cause_feedback=_read_json(output / "root-cause-feedback-router.json"),
        daily_learning=_read_json(output / "daily-learning-cycle.json"),
        unified_memory=_read_json(root / "learning" / "unified-memory-v2.json"),
    )
    _write_json(output / OUTPUT_JSON, review)
    text = render_learning_layer_review(review)
    (output / OUTPUT_TEXT).write_text(text, encoding="utf-8")
    _attach_to_brief(output, review)
    _append_phone_summary(output, text)
    return review
