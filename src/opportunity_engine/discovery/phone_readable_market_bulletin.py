"""Arabic phone-readable presentation for the domain market bulletin.

This module changes presentation only. It does not collect, classify, score,
contact, bid, buy, reserve, pay, or alter the selected human action.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


PRESENTATION_SCHEMA_VERSION = "phone-readable-market-bulletin-1.0"
COUNTRY_LABELS = {
    "NO": "النرويج",
    "SE": "السويد",
    "DE": "ألمانيا",
}
SIGNAL_TYPE_LABELS = {
    "ITEM_LISTING": "إعلان مخزون",
    "AUCTION_EVENT": "حدث مزاد",
    "BUSINESS_CLOSURE": "إغلاق نشاط تجاري",
    "INSOLVENCY_OR_LIQUIDATION": "إفلاس أو تصفية",
    "WAREHOUSE_SURPLUS": "فائض مستودع",
    "REPEATED_SELLER_ACTIVITY": "نشاط متكرر لبائع",
    "RELATED_INVENTORY_ACTIVITY": "نشاط مخزون مرتبط",
}
ACTION_LABELS = {
    "REVIEW_ONE_OPPORTUNITY": "راجع فرصة واحدة",
    "VERIFY_ONE_UNRESOLVED_RECORD": "تحقق من سجل واحد غير محسوم",
    "REVIEW_ONE_SOURCE_FAILURE": "راجع فشل مصدر واحد",
    "INVESTIGATE_RELATED_INVENTORY": "تحقق من وجود مخزون إضافي مرتبط",
    "MONITOR_INVENTORY_RELEASE": "راقب طرح المخزون للبيع",
    "VERIFY_MARKET_SIGNAL": "تحقق من أقوى إشارة سوقية",
    "NO_IMMEDIATE_ACTION": "لا يوجد إجراء فوري",
}
ACTION_REASON_LABELS = {
    "REVIEW_ONE_OPPORTUNITY": "توجد فرصة نشطة موثقة وجاهزة للمراجعة البشرية.",
    "VERIFY_ONE_UNRESOLVED_RECORD": "يوجد سجل يحتاج إلى تحقق من الأدلة قبل اعتباره فرصة.",
    "REVIEW_ONE_SOURCE_FAILURE": "فشل مصدر واحد ويجب التأكد من سبب الفشل قبل الاعتماد على تغطية اليوم.",
    "INVESTIGATE_RELATED_INVENTORY": "تكرار نشاط البائع قد يشير إلى وجود دفعات ملابس إضافية.",
    "MONITOR_INVENTORY_RELEASE": "قد يؤدي الإغلاق أو الإفلاس إلى طرح مخزون ملابس للبيع لاحقًا.",
    "VERIFY_MARKET_SIGNAL": "أقوى إشارة مبكرة تحتاج إلى تحقق قبل أن تصبح فرصة مباشرة.",
    "NO_IMMEDIATE_ACTION": "لا توجد فرصة مباشرة أو إشارة مبكرة موثوقة تتطلب إجراءً اليوم.",
}
WORKFLOW_IMPORTANCE = {
    "REQUIRES_VERIFICATION": "فرصة نشطة تحتاج إلى تحقق بشري قبل التحليل التجاري.",
    "ACTIVE_OPPORTUNITY": "فرصة نشطة موثقة وجاهزة للمراجعة البشرية.",
    "QUALIFIED_OPPORTUNITY": "فرصة مؤهلة وجاهزة للقرار التجاري البشري.",
}


def _compact(value: object) -> str:
    return " ".join(str(value or "").split())


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _first_text(values: Sequence[object]) -> str | None:
    for value in values:
        text = _compact(value)
        if text:
            return text
    return None


def _country_label(code: object) -> str:
    normalized = _compact(code).upper()
    return COUNTRY_LABELS.get(normalized, normalized or "غير معروف")


def _signal_type_label(value: object) -> str:
    normalized = _compact(value).upper()
    return SIGNAL_TYPE_LABELS.get(normalized, normalized or "إشارة سوقية")


def _signal_entity(signal: Mapping[str, Any]) -> str | None:
    return _first_text(
        (
            signal.get("company_name"),
            signal.get("seller_name"),
            signal.get("title"),
        )
    )


def _signal_by_opportunity(
    signal_persistence: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for signal in _mapping_list(signal_persistence.get("current_signals")):
        opportunity_id = _compact(signal.get("related_opportunity_id"))
        if opportunity_id:
            result[opportunity_id] = signal
    return result


def _enrich_direct_opportunities(
    brief: dict[str, Any],
    signal_persistence: Mapping[str, Any],
) -> list[dict[str, Any]]:
    signal_map = _signal_by_opportunity(signal_persistence)
    enriched: list[dict[str, Any]] = []
    for raw in _mapping_list(brief.get("current_direct_opportunities")):
        opportunity = dict(raw)
        identity = _compact(opportunity.get("opportunity_identity"))
        signal = signal_map.get(identity, {})
        metadata = _mapping(signal.get("metadata"))
        source_names = opportunity.get("source_names")
        source_name = _first_text(
            (
                opportunity.get("source_name"),
                source_names[0]
                if isinstance(source_names, Sequence)
                and not isinstance(source_names, (str, bytes))
                and source_names
                else None,
                signal.get("source"),
            )
        )
        source_urls = opportunity.get("source_urls")
        source_url = _first_text(
            (
                opportunity.get("source_url"),
                opportunity.get("canonical_url"),
                source_urls[0]
                if isinstance(source_urls, Sequence)
                and not isinstance(source_urls, (str, bytes))
                and source_urls
                else None,
                signal.get("source_url"),
            )
        )
        opportunity.update(
            {
                "title": _first_text((opportunity.get("title"), signal.get("title"))),
                "market_code": _first_text(
                    (opportunity.get("market_code"), signal.get("source_country"))
                ),
                "source_name": source_name,
                "source_url": source_url,
                "location": _first_text(
                    (opportunity.get("location"), signal.get("location"))
                ),
                "company_name": _first_text(
                    (opportunity.get("company_name"), signal.get("company_name"))
                ),
                "seller_name": _first_text(
                    (opportunity.get("seller_name"), signal.get("seller_name"))
                ),
                "quantity": opportunity.get("quantity")
                if opportunity.get("quantity") is not None
                else metadata.get("quantity"),
                "inventory_type": _first_text(
                    (opportunity.get("inventory_type"), metadata.get("inventory_type"))
                ),
                "related_signal_id": signal.get("signal_id"),
            }
        )
        enriched.append(opportunity)
    brief["current_direct_opportunities"] = enriched
    return enriched


def _top_early_signals(brief: Mapping[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for signal in _mapping_list(brief.get("early_signals_to_watch"))[:limit]:
        items.append(
            {
                "signal_id": signal.get("signal_id"),
                "signal_type": signal.get("signal_type"),
                "signal_type_ar": _signal_type_label(signal.get("signal_type")),
                "title": _first_text((signal.get("title"), signal.get("value"))),
                "entity": _signal_entity(signal),
                "location": _compact(signal.get("location")) or None,
                "market_code": _compact(signal.get("source_country")).upper() or None,
                "market_ar": _country_label(signal.get("source_country")),
                "source_name": _compact(signal.get("source")) or None,
                "source_url": _compact(signal.get("source_url")) or None,
                "confidence": signal.get("confidence"),
            }
        )
    return items


def _selected_opportunity(
    brief: Mapping[str, Any], direct: Sequence[Mapping[str, Any]]
) -> dict[str, Any] | None:
    action = _mapping(brief.get("selected_human_action"))
    selected_id = _compact(action.get("opportunity_identity"))
    if selected_id:
        for item in direct:
            if _compact(item.get("opportunity_identity")) == selected_id:
                return dict(item)
    return dict(direct[0]) if direct else None


def enrich_phone_readable_market_bulletin(
    brief: Mapping[str, Any],
    signal_persistence: Mapping[str, Any],
) -> dict[str, Any]:
    """Add presentation details without changing discovery or action selection."""
    enriched = deepcopy(dict(brief))
    direct = _enrich_direct_opportunities(enriched, signal_persistence)
    action = _mapping(enriched.get("selected_human_action"))
    action_code = _compact(action.get("action")).upper() or "NO_IMMEDIATE_ACTION"
    selected = _selected_opportunity(enriched, direct)
    if selected is not None:
        workflow = _compact(selected.get("workflow_status")).upper()
        selected["market_ar"] = _country_label(selected.get("market_code"))
        selected["why_important_ar"] = WORKFLOW_IMPORTANCE.get(
            workflow,
            "هذه أفضل فرصة مباشرة متاحة في تقرير اليوم للمراجعة البشرية.",
        )
    enriched["presentation_schema_version"] = PRESENTATION_SCHEMA_VERSION
    enriched["phone_readable_summary"] = {
        "top_early_signals": _top_early_signals(enriched),
        "selected_opportunity": selected,
        "selected_action_code": action_code,
        "selected_action_ar": ACTION_LABELS.get(action_code, action_code),
        "selected_reason_ar": ACTION_REASON_LABELS.get(
            action_code,
            "يتطلب التقرير إجراءً بشريًا واحدًا موضحًا في البيانات.",
        ),
    }
    return enriched


def _append_optional(lines: list[str], label: str, value: object) -> None:
    text = _compact(value)
    if text:
        lines.append(f"{label}: {text}")


def render_phone_readable_market_bulletin(brief: Mapping[str, Any]) -> str:
    """Render actual market news and the selected opportunity for a phone screen."""
    counts = _mapping(brief.get("counts"))
    summary = _mapping(brief.get("phone_readable_summary"))
    early = _mapping_list(summary.get("top_early_signals"))
    selected = summary.get("selected_opportunity")
    selected_opportunity = dict(selected) if isinstance(selected, Mapping) else None

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
        details = " | ".join(
            value
            for value in (
                f"الجهة: {_compact(signal.get('entity'))}"
                if _compact(signal.get("entity"))
                else "",
                f"المكان: {_compact(signal.get('location'))}"
                if _compact(signal.get("location"))
                else "",
                f"السوق: {_compact(signal.get('market_ar'))}"
                if _compact(signal.get("market_ar"))
                else "",
            )
            if value
        )
        if details:
            lines.append(f"   {details}")
        _append_optional(lines, "   المصدر", signal.get("source_name"))
        _append_optional(lines, "   الرابط", signal.get("source_url"))

    lines.extend(["", "أفضل فرصة مباشرة اليوم:"])
    if selected_opportunity is None:
        lines.append("لا توجد فرصة مباشرة صالحة للعرض اليوم.")
    else:
        _append_optional(lines, "الاسم", selected_opportunity.get("title"))
        _append_optional(lines, "السوق", selected_opportunity.get("market_ar"))
        _append_optional(lines, "المصدر", selected_opportunity.get("source_name"))
        _append_optional(
            lines,
            "الجهة",
            _first_text(
                (
                    selected_opportunity.get("company_name"),
                    selected_opportunity.get("seller_name"),
                )
            ),
        )
        _append_optional(lines, "الموقع", selected_opportunity.get("location"))
        if selected_opportunity.get("quantity") is not None:
            lines.append(f"الكمية المعروفة: {selected_opportunity.get('quantity')}")
        _append_optional(lines, "نوع المخزون", selected_opportunity.get("inventory_type"))
        _append_optional(
            lines,
            "لماذا مهمة الآن",
            selected_opportunity.get("why_important_ar"),
        )
        _append_optional(lines, "الرابط", selected_opportunity.get("source_url"))

    lines.extend(
        [
            "",
            f"الإجراء البشري الوحيد: {summary.get('selected_action_ar', 'لا يوجد إجراء فوري')}",
            f"السبب: {summary.get('selected_reason_ar', '')}",
            "لا شراء، لا مزايدة، لا اتصال، ولا دفع تلقائي.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_phone_readable_market_bulletin_artifacts(
    brief: Mapping[str, Any],
    signal_persistence: Mapping[str, Any],
    *,
    json_path: str | Path,
    text_path: str | Path,
) -> dict[str, Any]:
    """Write enriched JSON and the Arabic phone-readable bulletin."""
    enriched = enrich_phone_readable_market_bulletin(brief, signal_persistence)
    Path(json_path).write_text(
        json.dumps(enriched, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    Path(text_path).write_text(
        render_phone_readable_market_bulletin(enriched),
        encoding="utf-8",
    )
    return enriched
