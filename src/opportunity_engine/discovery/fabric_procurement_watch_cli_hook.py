"""Attach the bounded fabric procurement watch to the established daily bulletin."""
from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable, Mapping

from opportunity_engine.discovery.italy_textile_district_sources import (
    collect_italy_district_expanded_fabric_watch,
)

_INSTALLED = False
Collector = Callable[..., dict[str, Any]]


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _compact_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": candidate.get("candidate_id"),
        "source_name": candidate.get("source_name"),
        "source_country": candidate.get("source_country"),
        "source_kind": candidate.get("source_kind"),
        "location": candidate.get("location"),
        "title": candidate.get("title"),
        "source_url": candidate.get("source_url"),
        "fabric_terms": candidate.get("fabric_terms") or [],
        "bridal_terms": candidate.get("bridal_terms") or [],
        "price": candidate.get("price"),
        "currency": candidate.get("currency"),
        "quantity": candidate.get("quantity"),
        "quantity_unit": candidate.get("quantity_unit"),
        "procurement_relevance_score": candidate.get(
            "procurement_relevance_score", 0
        ),
        "recommended_operator_action": candidate.get(
            "recommended_operator_action"
        ),
    }


def _district_candidates(
    candidates: list[Mapping[str, Any]], source_kind: str
) -> list[Mapping[str, Any]]:
    return [item for item in candidates if item.get("source_kind") == source_kind]


def _summary(report: Mapping[str, Any]) -> dict[str, Any]:
    candidates = [
        item for item in (report.get("candidates") or []) if isinstance(item, Mapping)
    ]
    prato = _district_candidates(candidates, "PRATO_DEADSTOCK")
    como = _district_candidates(candidates, "COMO_SILK_STOCK")
    biella = _district_candidates(candidates, "BIELLA_WOOL_STOCK")
    return {
        "feed_family": report.get("feed_family"),
        "purpose": report.get("purpose"),
        "search_language": report.get("search_language"),
        "freshness": report.get("freshness"),
        "approved_official_domains": report.get("approved_official_domains") or [],
        "status_counts": report.get("status_counts") or {},
        "query_budget_total": report.get("query_budget_total", 0),
        "requests_made": report.get("requests_made", 0),
        "candidate_count": report.get("candidate_count", 0),
        "italy_textile_district_scope": report.get("italy_textile_district_scope")
        or ["Prato", "Como", "Biella"],
        "district_candidate_counts": report.get("district_candidate_counts")
        or {"Prato": len(prato), "Como": len(como), "Biella": len(biella)},
        "prato_candidate_count": len(prato),
        "como_candidate_count": len(como),
        "biella_candidate_count": len(biella),
        "top_procurement_candidates": [
            _compact_candidate(item) for item in candidates[:5]
        ],
        "top_prato_candidates": [_compact_candidate(item) for item in prato[:5]],
        "top_como_candidates": [_compact_candidate(item) for item in como[:5]],
        "top_biella_candidates": [_compact_candidate(item) for item in biella[:5]],
        "seller_or_source_verification_required": True,
        "not_part_of_opportunity_top5": True,
        "promotion_to_opportunity_allowed": False,
        "decision_owner": "HUMAN_OPERATOR",
        "automatic_contact": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _render_text(report: Mapping[str, Any]) -> str:
    candidates = [
        item for item in (report.get("candidates") or []) if isinstance(item, Mapping)
    ]
    regions = (
        ("Prato", "PRATO_DEADSTOCK"),
        ("Como", "COMO_SILK_STOCK"),
        ("Biella", "BIELLA_WOOL_STOCK"),
    )
    grouped = {
        region: _district_candidates(candidates, source_kind)
        for region, source_kind in regions
    }
    lines = [
        "FABRIC PROCUREMENT WATCH",
        f"status_counts: {json.dumps(report.get('status_counts') or {}, sort_keys=True)}",
        f"requests_made: {report.get('requests_made', 0)}",
        f"candidate_count: {report.get('candidate_count', 0)}",
        f"prato_candidate_count: {len(grouped['Prato'])}",
        f"como_candidate_count: {len(grouped['Como'])}",
        f"biella_candidate_count: {len(grouped['Biella'])}",
        "freshness: none (supplier catalog discovery)",
        "purchase_mode: MANUAL_ONLY",
    ]
    for region, _ in regions:
        items = grouped[region]
        for index, item in enumerate(items[:5], start=1):
            lines.append(
                f"{index}. [IT/{region}] {item.get('source_name')} — {item.get('title')} | "
                f"quantity={item.get('quantity')} {item.get('quantity_unit') or ''} | "
                f"price={item.get('price')} {item.get('currency') or ''} | "
                f"score={item.get('procurement_relevance_score', 0)} | {item.get('source_url')}"
            )
        if not items:
            lines.append(
                f"{region.casefold()}_result: No current {region} supplier result passed the gate."
            )
    lines += [
        "human_verification_required: true",
        "top5_eligible: false",
        "automatic_purchase: false",
    ]
    return "\n".join(lines) + "\n"


def write_daily_fabric_procurement_watch(
    output_dir: Path,
    *,
    environment: Mapping[str, str] | None = None,
    collector: Collector = collect_italy_district_expanded_fabric_watch,
) -> dict[str, Any]:
    """Write the supplier watch before the unified river consumes daily artifacts."""
    try:
        report = collector(
            environment=environment if environment is not None else os.environ,
            freshness=None,
        )
    except Exception as exc:
        report = {
            "schema_version": "fabric-procurement-watch-1.0",
            "feed_family": "FABRIC_DEADSTOCK_PROCUREMENT_FEED_V1",
            "purpose": "TAILORING_SHOP_FABRIC_PROCUREMENT_INTELLIGENCE",
            "freshness": None,
            "status_counts": {"FAILED": 1},
            "requests_made": 0,
            "candidate_count": 0,
            "candidates": [],
            "italy_textile_district_scope": ["Prato", "Como", "Biella"],
            "district_candidate_counts": {"Prato": 0, "Como": 0, "Biella": 0},
            "error_type": type(exc).__name__,
            "error": " ".join(str(exc).split())[:500],
            "promotion_to_opportunity_allowed": False,
            "analysis_eligible": False,
            "top5_eligible": False,
            "automatic_contact": False,
            "automatic_reservation": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }

    _write_json(output_dir / "fabric-procurement-watch.json", report)
    (output_dir / "fabric-procurement-watch.txt").write_text(
        _render_text(report), encoding="utf-8"
    )

    brief_path = output_dir / "domain-market-intelligence-brief.json"
    if brief_path.exists():
        try:
            brief = json.loads(brief_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            brief = None
        if isinstance(brief, dict):
            brief["fabric_procurement_watch"] = _summary(report)
            _write_json(brief_path, brief)

    text_path = output_dir / "domain-market-intelligence-brief.txt"
    if text_path.exists():
        base = text_path.read_text(encoding="utf-8").rstrip()
        text_path.write_text(
            base + "\n\n## Fabric procurement watch\n" + _render_text(report),
            encoding="utf-8",
        )
    return report


def install_fabric_procurement_watch_cli_hook() -> None:
    """Register the supplier watch for the existing daily bulletin CLI only.

    This hook is registered after the unified-river hook. Python executes atexit
    callbacks in reverse order, so the fabric artifact is written first and the
    existing unified river then consumes it in the same daily run.
    """
    global _INSTALLED
    if _INSTALLED or Path(sys.argv[0]).name != "build_domain_market_intelligence_feed.py":
        return
    try:
        output_index = sys.argv.index("--output-dir")
        output_dir = Path(sys.argv[output_index + 1])
    except (ValueError, IndexError):
        return

    def _run_before_river() -> None:
        if not (output_dir / "domain-market-intelligence-brief.json").exists():
            return
        report = write_daily_fabric_procurement_watch(output_dir)
        print(
            "daily_fabric_procurement_watch:",
            json.dumps(
                {
                    "status_counts": report.get("status_counts"),
                    "requests_made": report.get("requests_made"),
                    "candidate_count": report.get("candidate_count"),
                    "district_candidate_counts": report.get("district_candidate_counts"),
                    "freshness": report.get("freshness"),
                },
                sort_keys=True,
            ),
        )

    atexit.register(_run_before_river)
    _INSTALLED = True
