"""Correct signal roles, stale events, and the one human action.

This layer is intentionally bounded. It does not collect, score, rank, contact,
bid, buy, reserve, pay, or introduce an opportunity-cluster model. It only fixes
how the existing daily bulletin separates early signals from direct listings and
how it describes the selected human action.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from opportunity_engine.discovery.phone_readable_market_bulletin import (
    enrich_phone_readable_market_bulletin,
)


CORRECTION_SCHEMA_VERSION = "signal-role-freshness-correction-1.0"
EARLY_SIGNAL_TYPES = {
    "AUCTION_EVENT",
    "BUSINESS_CLOSURE",
    "INSOLVENCY_OR_LIQUIDATION",
    "WAREHOUSE_SURPLUS",
    "REPEATED_SELLER_ACTIVITY",
    "RELATED_INVENTORY_ACTIVITY",
}
ACTIVE_SIGNAL_STATES = {"ACTIVE", "WATCH"}
TERMINAL_SIGNAL_STATES = {"CLOSED", "ENDED", "HISTORICAL", "REJECTED"}
TERMINAL_LISTING_STATES = {"ENDED", "CLOSED", "EXPIRED", "SOLD", "UNAVAILABLE", "HISTORICAL"}
TERMINAL_WORKFLOW_STATES = {"CLOSED", "REJECTED", "HISTORICAL_MARKET_EVIDENCE"}
AUCTION_WORDS = ("auction", "auktion", "auksjon", "versteigerung")


def _compact(value: object) -> str:
    return " ".join(str(value or "").split())


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _timestamp(value: object) -> datetime:
    text = _compact(value)
    if not text:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normal(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _compact(value).casefold()).strip()


def _signal_is_terminal(signal: Mapping[str, Any]) -> bool:
    status = _compact(signal.get("status")).upper()
    metadata = _mapping(signal.get("metadata"))
    listing = _compact(metadata.get("listing_status")).upper()
    workflow = _compact(metadata.get("workflow_status")).upper()
    return (
        status in TERMINAL_SIGNAL_STATES
        or listing in TERMINAL_LISTING_STATES
        or workflow in TERMINAL_WORKFLOW_STATES
    )


def _old_auction_year_in_title(signal: Mapping[str, Any], reference: datetime) -> bool:
    if _compact(signal.get("signal_type")).upper() != "AUCTION_EVENT":
        return False
    title = _compact(signal.get("title") or signal.get("value")).casefold()
    if not any(word in title for word in AUCTION_WORDS):
        return False
    years = [int(value) for value in re.findall(r"\b(20\d{2})\b", title)]
    return bool(years) and max(years) <= reference.year - 2


def _event_date_is_stale(signal: Mapping[str, Any], reference: datetime) -> bool:
    text = _compact(signal.get("event_date"))
    if not text:
        return False
    try:
        event_date = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    if event_date.tzinfo is None or event_date.utcoffset() is None:
        event_date = event_date.replace(tzinfo=timezone.utc)
    return (reference - event_date.astimezone(timezone.utc)).days > 548


def _is_credible_early_signal(signal: Mapping[str, Any], reference: datetime) -> bool:
    signal_type = _compact(signal.get("signal_type")).upper()
    status = _compact(signal.get("status")).upper()
    if signal_type not in EARLY_SIGNAL_TYPES or status not in ACTIVE_SIGNAL_STATES:
        return False
    if _compact(signal.get("related_opportunity_id")):
        return False
    if _signal_is_terminal(signal):
        return False
    if _event_date_is_stale(signal, reference):
        return False
    if _old_auction_year_in_title(signal, reference):
        return False
    return True


def _filter_early_signals(brief: dict[str, Any]) -> None:
    reference = _timestamp(brief.get("generated_at"))
    early = [
        signal
        for signal in _mapping_list(brief.get("early_signals_to_watch"))
        if _is_credible_early_signal(signal, reference)
    ]
    brief["early_signals_to_watch"] = early
    counts = dict(_mapping(brief.get("counts")))
    counts["early_signals_to_watch"] = len(early)
    brief["counts"] = counts


def _actual_entity(record: Mapping[str, Any]) -> str:
    return (
        _compact(record.get("company_name"))
        or _compact(record.get("seller_name"))
        or "غير معروفة"
    )


def _selected_opportunity(summary: Mapping[str, Any]) -> dict[str, Any] | None:
    value = summary.get("selected_opportunity")
    return dict(value) if isinstance(value, Mapping) else None


def _verification_message(selected: Mapping[str, Any]) -> tuple[str, str]:
    workflow = _compact(selected.get("workflow_status")).upper()
    verified = selected.get("verified") is True
    if workflow == "REQUIRES_VERIFICATION":
        return (
            "راجع فرصة واحدة تحتاج إلى تحقق",
            "هذه فرصة مباشرة نشطة، لكنها تحتاج إلى تحقق بشري من الأدلة قبل التحليل التجاري.",
        )
    if workflow == "QUALIFIED_OPPORTUNITY":
        return (
            "راجع فرصة مؤهلة",
            "هذه فرصة مؤهلة وجاهزة للقرار التجاري البشري.",
        )
    if verified:
        return (
            "راجع فرصة موثقة",
            "هذه فرصة نشطة موثقة وجاهزة للمراجعة البشرية.",
        )
    return (
        "راجع فرصة مباشرة",
        "هذه فرصة مباشرة نشطة وجاهزة للمراجعة البشرية، دون افتراض أنها موثقة بالكامل.",
    )


def _related_lots(
    selected: Mapping[str, Any], direct: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    source = _normal(selected.get("source_name"))
    location = _normal(selected.get("location"))
    if not source or not location:
        return []
    result = [
        dict(item)
        for item in direct
        if _normal(item.get("source_name")) == source
        and _normal(item.get("location")) == location
    ]
    return result if len(result) >= 2 else []


def _correct_phone_summary(enriched: dict[str, Any]) -> None:
    summary = dict(_mapping(enriched.get("phone_readable_summary")))
    top_early = _mapping_list(summary.get("top_early_signals"))
    for item in top_early:
        raw_match = next(
            (
                signal
                for signal in _mapping_list(enriched.get("early_signals_to_watch"))
                if _compact(signal.get("signal_id")) == _compact(item.get("signal_id"))
            ),
            {},
        )
        item["entity"] = _actual_entity(raw_match)
    summary["top_early_signals"] = top_early

    selected = _selected_opportunity(summary)
    direct = _mapping_list(enriched.get("current_direct_opportunities"))
    if selected is not None:
        selected["display_entity_ar"] = _actual_entity(selected)
        action_label, reason = _verification_message(selected)
        selected["why_important_ar"] = reason
        related = _related_lots(selected, direct)
        if related:
            related_ids = [
                _compact(item.get("opportunity_identity"))
                for item in related
                if _compact(item.get("opportunity_identity"))
            ]
            summary["selected_action_code"] = "REVIEW_RELATED_LOTS"
            summary["selected_action_ar"] = "راجع دفعات المخزون المرتبطة في الموقع نفسه"
            summary["selected_reason_ar"] = (
                "ظهرت عدة دفعات من المصدر والموقع نفسيهما؛ راجعها معًا واسأل البائع "
                "عن بقية مخزون الملابس وإمكانية الاستلام في رحلة واحدة."
            )
            summary["related_lots"] = related
            action = dict(_mapping(enriched.get("selected_human_action")))
            action.update(
                {
                    "action": "REVIEW_RELATED_LOTS",
                    "reason": "Multiple direct lots share the same source and location.",
                    "related_opportunity_ids": related_ids,
                    "automatic_contact": False,
                }
            )
            enriched["selected_human_action"] = action
        else:
            summary["selected_action_ar"] = action_label
            summary["selected_reason_ar"] = reason
            summary["related_lots"] = []
        summary["selected_opportunity"] = selected

    enriched["phone_readable_summary"] = summary


def correct_signal_roles_and_freshness(
    brief: Mapping[str, Any],
    signal_persistence: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a corrected bulletin without changing discovery or scoring."""
    corrected = deepcopy(dict(brief))
    _filter_early_signals(corrected)
    enriched = enrich_phone_readable_market_bulletin(corrected, signal_persistence)
    enriched["correction_schema_version"] = CORRECTION_SCHEMA_VERSION
    _correct_phone_summary(enriched)
    counts = dict(_mapping(enriched.get("counts")))
    counts["early_signals_to_watch"] = len(
        _mapping_list(enriched.get("early_signals_to_watch"))
    )
    enriched["counts"] = counts
    return enriched


def _append(lines: list[str], label: str, value: object, *, required: bool = False) -> None:
    text = _compact(value)
    if text or required:
        lines.append(f"{label}: {text or 'غير معروف'}")


def render_corrected_market_bulletin(brief: Mapping[str, Any]) -> str:
    counts = _mapping(brief.get("counts"))
    summary = _mapping(brief.get("phone_readable_summary"))
    early = _mapping_list(summary.get("top_early_signals"))
    selected = _selected_opportunity(summary)
    related = _mapping_list(summary.get("related_lots"))

    lines = [
        "نشرة استخبارات سوق مخزون الملابس",
        f"الوقت: {brief.get('generated_at')}",
        "الأسواق: النرويج | السويد | ألمانيا",
        (
            "الملخص: "
            f"جديدة {counts.get('new_signals_today', 0)} | "
            f"تغيرت {counts.get('changed_signals_since_previous_checkpoint', 0)} | "
            f"مبكرة {counts.get('early_signals_to_watch', 0)} | "
            f"فرص مباشرة {counts.get('current_direct_opportunities', 0)} | "
            f"مصادر فاشلة {counts.get('unavailable_or_failed_sources', 0)}"
        ),
        "",
        "أهم الإشارات المبكرة اليوم:",
    ]
    if not early:
        lines.append("لا توجد إشارات مبكرة نشطة للمراقبة اليوم.")
    for index, signal in enumerate(early, start=1):
        title = _compact(signal.get("title")) or "دون عنوان"
        lines.append(f"{index}) [{signal.get('signal_type_ar', 'إشارة سوقية')}] {title}")
        lines.append(
            "   "
            + " | ".join(
                (
                    f"الجهة: {_compact(signal.get('entity')) or 'غير معروفة'}",
                    f"المكان: {_compact(signal.get('location')) or 'غير معروف'}",
                    f"السوق: {_compact(signal.get('market_ar')) or 'غير معروف'}",
                )
            )
        )
        _append(lines, "   المصدر", signal.get("source_name"))
        _append(lines, "   الرابط", signal.get("source_url"))

    lines.extend(["", "أفضل فرصة مباشرة اليوم:"])
    if selected is None:
        lines.append("لا توجد فرصة مباشرة صالحة للعرض اليوم.")
    else:
        _append(lines, "الاسم", selected.get("title"), required=True)
        _append(lines, "السوق", selected.get("market_ar"), required=True)
        _append(lines, "المصدر", selected.get("source_name"), required=True)
        _append(lines, "الجهة", selected.get("display_entity_ar"), required=True)
        _append(lines, "الموقع", selected.get("location"), required=True)
        if selected.get("quantity") is not None:
            lines.append(f"الكمية المعروفة: {selected.get('quantity')}")
        _append(lines, "نوع المخزون", selected.get("inventory_type"))
        _append(lines, "لماذا مهمة الآن", selected.get("why_important_ar"), required=True)
        _append(lines, "الرابط", selected.get("source_url"), required=True)

    if related:
        lines.extend(["", "دفعات مرتبطة في المصدر والموقع نفسيهما:"])
        for index, item in enumerate(related, start=1):
            title = _compact(item.get("title")) or "دفعة دون عنوان"
            lines.append(f"{index}) {title}")
            _append(lines, "   الرابط", item.get("source_url"))

    lines.extend(
        [
            "",
            f"الإجراء البشري الوحيد: {summary.get('selected_action_ar', 'لا يوجد إجراء فوري')}",
            f"السبب: {summary.get('selected_reason_ar', '')}",
            "لا شراء، لا مزايدة، لا اتصال، ولا دفع تلقائي.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_corrected_market_bulletin_artifacts(
    brief: Mapping[str, Any],
    signal_persistence: Mapping[str, Any],
    *,
    json_path: str | Path,
    text_path: str | Path,
) -> dict[str, Any]:
    corrected = correct_signal_roles_and_freshness(brief, signal_persistence)
    Path(json_path).write_text(
        json.dumps(corrected, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    Path(text_path).write_text(
        render_corrected_market_bulletin(corrected),
        encoding="utf-8",
    )
    return corrected
