"""Run the central intelligence synthesis after existing daily projections."""
from __future__ import annotations

import atexit
import json
from pathlib import Path
import sys
from typing import Any, Mapping

from opportunity_engine.discovery.central_intelligence_orchestrator import (
    TEXT_FILENAME,
    write_central_intelligence_orchestrator,
)
from opportunity_engine.discovery.central_market_decision_quality import (
    apply_market_decision_quality,
)
from opportunity_engine.logistics.official_route_freight import (
    apply_official_route_freight,
)

_INSTALLED = False


def _first_url(item: Mapping[str, Any] | None) -> str | None:
    if not isinstance(item, Mapping):
        return None
    direct = str(item.get("source_url") or "").strip()
    if direct:
        return direct
    urls = item.get("source_urls")
    if isinstance(urls, list):
        for value in urls:
            url = str(value or "").strip()
            if url:
                return url
    return None


def _fabric_title(item: Mapping[str, Any]) -> str:
    source = str(item.get("source_name") or "").strip()
    title = str(item.get("title") or "").strip()
    if source and title and source.casefold() not in title.casefold():
        return f"{source} — {title}"
    return source or title or "NONE"


def _route_freight_lines(opportunity: Mapping[str, Any]) -> list[str]:
    route_freight = opportunity.get("route_freight")
    if not isinstance(route_freight, Mapping):
        return ["  الطريق: NOT_AVAILABLE", "  الشحن الرسمي: NOT_AVAILABLE"]
    route_status = str(route_freight.get("route_status") or "NOT_AVAILABLE")
    distance = route_freight.get("distance_km")
    precision = str(route_freight.get("route_precision") or "NOT_AVAILABLE")
    if distance is not None:
        route_text = f"{distance} km | {precision} | {route_status}"
    else:
        route_text = route_status

    freight_status = str(route_freight.get("freight_status") or "NOT_AVAILABLE")
    provider = str(route_freight.get("freight_provider") or "BRING_SHIPPING_GUIDE")
    quote = route_freight.get("official_quote")
    if isinstance(quote, Mapping):
        amount = quote.get("amount_with_vat")
        currency = quote.get("currency") or ""
        price_type = quote.get("price_type") or ""
        freight_text = f"{provider}: {amount} {currency} | {price_type} | {freight_status}"
    else:
        freight_text = f"{provider}: {freight_status}"
    lines = [f"  الطريق: {route_text}", f"  الشحن الرسمي: {freight_text}"]
    missing = [str(value) for value in route_freight.get("shipping_missing_inputs") or []]
    if missing:
        lines.append("  بيانات الشحن الناقصة: " + ", ".join(missing))
    return lines


def render_daily_central_report(brief: Mapping[str, Any]) -> str:
    """Render the operator report with title, source, market and logistics evidence."""
    visibility = " | ".join(brief.get("market_visibility") or []) or "NONE"
    snapshot = brief.get("today_snapshot") if isinstance(brief.get("today_snapshot"), Mapping) else {}
    opportunity = brief.get("top_actionable_opportunity") if isinstance(brief.get("top_actionable_opportunity"), Mapping) else {}
    watch = brief.get("top_market_signal") if isinstance(brief.get("top_market_signal"), Mapping) else {}
    fabric = brief.get("top_fabric_supplier") if isinstance(brief.get("top_fabric_supplier"), Mapping) else {}
    action = brief.get("primary_human_action") if isinstance(brief.get("primary_human_action"), Mapping) else {}
    benchmark = opportunity.get("market_benchmark") if isinstance(opportunity.get("market_benchmark"), Mapping) else {}

    opportunity_title = str(opportunity.get("headline") or "NONE")
    watch_title = str(watch.get("headline") or "NONE")
    fabric_title = _fabric_title(fabric) if fabric else "NONE"
    opportunity_url = _first_url(opportunity) or "NONE"
    watch_url = _first_url(watch) or "NONE"
    fabric_url = _first_url(fabric) or "NONE"
    benchmark_classification = str(benchmark.get("benchmark_classification") or "NOT_AVAILABLE")
    comparable_count = int(benchmark.get("comparable_count") or 0)

    lines = [
        "CENTRAL INTELLIGENCE ORCHESTRATOR",
        f"status: {brief.get('status')}",
        f"daily_market_visibility: {visibility}",
        f"actionable_now: {snapshot.get('actionable_now_count', 0)}",
        f"market_watch: {snapshot.get('market_watch_count', 0)}",
        f"fabric_candidates: {snapshot.get('fabric_candidate_count', 0)}",
        f"fabric_ai_status: {snapshot.get('fabric_ai_status') or 'NOT_AVAILABLE'}",
        f"market_decision_quality: {snapshot.get('market_decision_quality') or 'UNIFIED_PRIORITY_ONLY'}",
        f"official_route_status: {snapshot.get('official_route_status') or 'NOT_AVAILABLE'}",
        f"official_freight_status: {snapshot.get('official_freight_status') or 'NOT_AVAILABLE'}",
        "",
        "أهم فرصة قابلة للمراجعة الآن:",
        f"- العنوان: {opportunity_title}",
        f"  الرابط: {opportunity_url}",
        f"  مقارنة السوق: {benchmark_classification} | comparables={comparable_count}",
        *_route_freight_lines(opportunity),
        "",
        "أهم إشارة سوق للمراقبة:",
        f"- العنوان: {watch_title}",
        f"  الرابط: {watch_url}",
        "",
        "أفضل مورد أقمشة للمراجعة:",
        f"- العنوان: {fabric_title}",
        f"  الرابط: {fabric_url}",
        (f"  AI: {fabric.get('ai_review_priority')}" if fabric.get("ai_review_priority") else "  AI: NOT_AVAILABLE"),
        "",
        "الإجراء البشري الوحيد:",
        f"- {action.get('action_type')}: {action.get('target') or action.get('recommended_next_action')}",
        f"reason: {action.get('reason')}",
        "decision_owner: HUMAN_OPERATOR",
        "automatic_purchase: false",
    ]
    return "\n".join(lines) + "\n"


def _rewrite_delivery_text(output_dir: Path, brief: Mapping[str, Any]) -> None:
    rendered = render_daily_central_report(brief)
    (output_dir / TEXT_FILENAME).write_text(rendered, encoding="utf-8")

    domain_text = output_dir / "domain-market-intelligence-brief.txt"
    if not domain_text.exists():
        return
    existing = domain_text.read_text(encoding="utf-8")
    marker = "CENTRAL INTELLIGENCE ORCHESTRATOR"
    if marker in existing:
        prefix = existing.split(marker, 1)[0].rstrip()
        domain_text.write_text(prefix + "\n\n" + rendered, encoding="utf-8")


def install_central_intelligence_orchestrator_cli_hook() -> None:
    """Register the final read-only daily synthesis.

    This hook must be registered before the market-comparables and river hooks.
    Python executes atexit callbacks in reverse order, so the established order is:

    fabric watch -> fabric AI -> unified river -> market comparables -> central
    decision quality -> official route/freight -> final report text.
    """
    global _INSTALLED
    if _INSTALLED or Path(sys.argv[0]).name != "build_domain_market_intelligence_feed.py":
        return
    try:
        output_index = sys.argv.index("--output-dir")
        output_dir = Path(sys.argv[output_index + 1])
    except (ValueError, IndexError):
        return

    def _run_last() -> None:
        if not (output_dir / "domain-market-intelligence-brief.json").exists():
            return
        brief = write_central_intelligence_orchestrator(output_dir)
        brief = apply_market_decision_quality(output_dir, brief)
        brief = apply_official_route_freight(output_dir, brief)
        _rewrite_delivery_text(output_dir, brief)
        action = brief.get("primary_human_action") or {}
        print(
            "central_intelligence_orchestrator:",
            json.dumps(
                {
                    "status": brief.get("status"),
                    "market_visibility": brief.get("market_visibility"),
                    "market_decision_quality": (brief.get("today_snapshot") or {}).get("market_decision_quality"),
                    "official_route_status": (brief.get("today_snapshot") or {}).get("official_route_status"),
                    "official_freight_status": (brief.get("today_snapshot") or {}).get("official_freight_status"),
                    "primary_action": action.get("action_type"),
                    "target": action.get("target"),
                    "output_files": brief.get("output_files"),
                },
                sort_keys=True,
            ),
        )

    atexit.register(_run_last)
    _INSTALLED = True
