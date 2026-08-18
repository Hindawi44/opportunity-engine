"""Run the central intelligence synthesis after existing daily projections."""
from __future__ import annotations

import atexit
import json
from pathlib import Path
import sys
from typing import Any, Mapping
from urllib.parse import urlparse

from opportunity_engine.discovery.central_intelligence_orchestrator import (
    TEXT_FILENAME,
    write_central_intelligence_orchestrator,
)
from opportunity_engine.discovery.central_market_decision_quality import (
    apply_market_decision_quality,
)
from opportunity_engine.discovery.source_logistics_hydration import (
    hydrate_selected_source_logistics,
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


def _source_label(opportunity: Mapping[str, Any]) -> str:
    direct = str(
        opportunity.get("source_name")
        or opportunity.get("source_provider")
        or ""
    ).strip()
    if direct:
        return direct
    url = _first_url(opportunity)
    host = (urlparse(url).hostname or "").casefold() if url else ""
    known = {
        "ny.auksjonen.no": "Auksjonen.no",
        "auksjonen.no": "Auksjonen.no",
        "psauction.se": "PS Auction",
        "sen-sen.de": "Sen & Sen",
    }
    for suffix, label in known.items():
        if host == suffix or host.endswith("." + suffix):
            return label
    return host or "غير متوفر"


def _country_location(opportunity: Mapping[str, Any]) -> str:
    country = str(
        opportunity.get("market_code")
        or opportunity.get("source_country")
        or opportunity.get("country")
        or ""
    ).strip().upper()
    location = str(
        opportunity.get("location")
        or opportunity.get("source_city")
        or ""
    ).strip()
    if not country:
        url = _first_url(opportunity)
        host = (urlparse(url).hostname or "").casefold() if url else ""
        for suffix, code in ((".no", "NO"), (".se", "SE"), (".de", "DE"), (".it", "IT")):
            if host.endswith(suffix):
                country = code
                break
    if country and location:
        return f"{country} | {location}"
    return country or location or "غير متوفر"


def _display_number(value: object) -> str | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        text = str(value).strip()
        return text or None
    if number <= 0:
        return None
    if number.is_integer():
        return str(int(number))
    return f"{number:.2f}".rstrip("0").rstrip(".")


def _price_text(opportunity: Mapping[str, Any]) -> str:
    for key, currency in (
        ("price_nok", "NOK"),
        ("bid_price_nok", "NOK"),
        ("price", str(opportunity.get("currency") or "").strip().upper()),
    ):
        value = _display_number(opportunity.get(key))
        if value:
            return f"{value} {currency}".strip()
    return "غير متوفر"


def _quantity_content(opportunity: Mapping[str, Any]) -> str:
    quantity = _display_number(opportunity.get("quantity"))
    if quantity:
        return quantity
    inventory_type = str(opportunity.get("inventory_type") or "").strip()
    if inventory_type:
        return inventory_type
    title = str(opportunity.get("title") or opportunity.get("headline") or "").strip()
    return title or "غير متوفر"


def _why_useful(opportunity: Mapping[str, Any]) -> str:
    direct = str(
        opportunity.get("why_useful")
        or opportunity.get("reason")
        or opportunity.get("recommended_next_action")
        or ""
    ).strip()
    if direct:
        return direct
    if opportunity.get("analysis_eligible") is True:
        return "فرصة مخزون نشطة اجتازت التحقق وأصبحت مؤهلة للتحليل التجاري"
    return "فرصة مخزون تجارية موثقة"


def _useful_rows(brief: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = brief.get("useful_opportunities")
    if isinstance(rows, list):
        return [dict(row) for row in rows if isinstance(row, Mapping)]
    opportunity = brief.get("top_actionable_opportunity")
    if isinstance(opportunity, Mapping) and opportunity:
        return [dict(opportunity)]
    return []


def render_daily_central_report(brief: Mapping[str, Any]) -> str:
    """Render only useful commercial opportunities for the human operator."""
    opportunities = _useful_rows(brief)
    if not opportunities:
        return "0 فرص مفيدة اليوم.\n"

    lines = [f"فرص مفيدة اليوم: {len(opportunities)}"]
    for index, opportunity in enumerate(opportunities, start=1):
        title = str(opportunity.get("title") or opportunity.get("headline") or "غير متوفر").strip()
        url = _first_url(opportunity) or "غير متوفر"
        lines.append(
            f"{index}. العنوان: {title}"
            f" | المصدر: {_source_label(opportunity)}"
            f" | البلد/الموقع: {_country_location(opportunity)}"
            f" | السعر: {_price_text(opportunity)}"
            f" | الكمية/المحتوى: {_quantity_content(opportunity)}"
            f" | لماذا مفيدة: {_why_useful(opportunity)}"
            f" | الرابط: {url}"
        )
    return "\n".join(lines) + "\n"


def _read_json_dict(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _hydrate_delivery_opportunity(
    output_dir: Path,
    opportunity: Mapping[str, Any],
) -> dict[str, Any]:
    hydrated = dict(opportunity)
    source_url = _first_url(hydrated)
    identity = str(hydrated.get("opportunity_identity") or "").strip()
    input_root = output_dir.parent / "multi-market-inputs"
    if not input_root.exists():
        return hydrated

    for report_path in sorted(input_root.glob("*/unified-opportunity-report.json")):
        report = _read_json_dict(report_path)
        records = report.get("records")
        if not isinstance(records, list):
            continue
        for raw in records:
            if not isinstance(raw, Mapping):
                continue
            record = dict(raw)
            record_url = str(record.get("source_url") or "").strip()
            record_id = str(record.get("opportunity_id") or "").strip()
            if source_url and record_url != source_url and record_id != source_url:
                if not identity or record_id != identity:
                    continue
            elif not source_url and identity and record_id != identity:
                continue
            elif not source_url and not identity:
                continue

            for source_key, target_key in (
                ("market_code", "market_code"),
                ("location", "location"),
                ("quantity", "quantity"),
                ("inventory_type", "inventory_type"),
                ("currency", "currency"),
            ):
                if hydrated.get(target_key) in (None, "", [], {}) and record.get(source_key) not in (None, "", [], {}):
                    hydrated[target_key] = record.get(source_key)
            if not hydrated.get("source_name") and record.get("source_provider"):
                hydrated["source_name"] = record.get("source_provider")
            if _display_number(hydrated.get("price")) is None and _display_number(record.get("price")) is not None:
                hydrated["price"] = record.get("price")
            return hydrated
    return hydrated


def _select_useful_delivery_opportunities(
    output_dir: Path,
    central_brief: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Select only verified direct opportunities already cleared for analysis."""
    domain = _read_json_dict(output_dir / "domain-market-intelligence-brief.json")
    raw_rows = domain.get("current_direct_opportunities")
    useful: list[dict[str, Any]] = []
    if isinstance(raw_rows, list):
        for raw in raw_rows:
            if not isinstance(raw, Mapping):
                continue
            row = dict(raw)
            if row.get("analysis_eligible") is not True:
                continue
            if str(row.get("listing_status") or "").strip().upper() != "ACTIVE":
                continue
            if row.get("top5_eligible") is not True:
                continue
            if not _first_url(row) or not str(row.get("title") or "").strip():
                continue
            row.setdefault(
                "why_useful",
                "فرصة مخزون نشطة اجتازت التحقق وأصبحت مؤهلة للتحليل التجاري",
            )
            useful.append(_hydrate_delivery_opportunity(output_dir, row))

    if useful:
        return useful

    fallback = central_brief.get("top_actionable_opportunity")
    if isinstance(fallback, Mapping) and fallback:
        return [_hydrate_delivery_opportunity(output_dir, fallback)]
    return []


def _remove_legacy_human_action(text: str) -> str:
    """Remove the earlier bulletin action block before central decision synthesis.

    The domain bulletin historically emitted its own single action before the central
    orchestrator existed. Once the central layer is present, that legacy action is an
    intermediate recommendation, not the operator's final decision. Drop only that
    paragraph so the final user-facing report contains exactly one human action while
    preserving all source, signal, fabric and market-intelligence sections.
    """
    lines = text.splitlines()
    cleaned: list[str] = []
    index = 0
    while index < len(lines):
        if lines[index].startswith("الإجراء البشري الوحيد:"):
            index += 1
            while index < len(lines) and lines[index].strip():
                index += 1
            while index < len(lines) and not lines[index].strip():
                index += 1
            continue
        cleaned.append(lines[index])
        index += 1
    return "\n".join(cleaned).rstrip()


def _rewrite_delivery_text(output_dir: Path, brief: Mapping[str, Any]) -> None:
    useful = _select_useful_delivery_opportunities(output_dir, brief)
    rendered = render_daily_central_report({"useful_opportunities": useful})
    (output_dir / TEXT_FILENAME).write_text(rendered, encoding="utf-8")

    # The delivery bulletin is intentionally a clean operator projection. Detailed
    # early signals, fabric procurement and diagnostics remain available in JSON
    # artifacts, but are not repeated in the final human-facing text.
    domain_text = output_dir / "domain-market-intelligence-brief.txt"
    domain_text.write_text(rendered, encoding="utf-8")


def install_central_intelligence_orchestrator_cli_hook() -> None:
    """Register the final read-only daily synthesis.

    This hook must be registered before the market-comparables and river hooks.
    Python executes atexit callbacks in reverse order, so the established order is:

    fabric watch -> fabric AI -> unified river -> market comparables -> central
    decision quality -> selected-source logistics hydration -> official route/freight
    -> final report text.
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
        hydration = hydrate_selected_source_logistics(output_dir, brief)
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
                    "source_logistics_hydration_status": hydration.get("status"),
                    "source_logistics_hydrated_fields": hydration.get("hydrated_fields"),
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
