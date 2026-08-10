"""Bounded Como and Biella source expansion for the unified fabric watch."""
from __future__ import annotations

from typing import Any

import opportunity_engine.discovery.fabric_procurement_watch as fabric_watch
from opportunity_engine.discovery.fabric_procurement_watch import FabricSource


ITALY_TEXTILE_DISTRICT_SOURCES: tuple[FabricSource, ...] = (
    FabricSource(
        source_id="silk-lab-como",
        name="Silk Lab Italy",
        domain="silklabitaly.com",
        country="IT",
        query=(
            'site:silklabitaly.com (stock OR "stock service" OR "pronta consegna" OR '
            '"al metro") (seta OR silk OR satin OR raso OR georgette OR "crepe de chine" '
            'OR velluto OR viscosa OR tessuti OR fabrics)'
        ),
        source_kind="COMO_SILK_STOCK",
        location="Como, IT",
    ),
    FabricSource(
        source_id="texit-biella",
        name="Texit Italian Quality Textiles",
        domain="texitbiella.com",
        country="IT",
        query=(
            'site:texitbiella.com (stock OR "tessuti a stock" OR magazzino OR '
            '"pronta consegna" OR "minimo ordine") (lana OR wool OR cashmere OR seta '
            'OR silk OR lino OR tessuti OR fabrics)'
        ),
        source_kind="BIELLA_WOOL_STOCK",
        location="Biella, IT",
    ),
)


def collect_italy_district_expanded_fabric_watch(**kwargs: Any) -> dict[str, Any]:
    """Run the established fabric collector with Como and Biella added temporarily.

    The base collector and its standalone five-source contract remain unchanged.
    The unified daily path gets a single combined report with the same feed family,
    safety gates, identity rules, and downstream unified-river adapter.
    """
    original_sources = fabric_watch.SOURCES
    existing_ids = {source.source_id for source in original_sources}
    additions = tuple(
        source
        for source in ITALY_TEXTILE_DISTRICT_SOURCES
        if source.source_id not in existing_ids
    )
    fabric_watch.SOURCES = tuple(original_sources) + additions
    try:
        report = fabric_watch.collect_fabric_procurement_watch(**kwargs)
    finally:
        fabric_watch.SOURCES = original_sources

    candidates = [
        item for item in (report.get("candidates") or []) if isinstance(item, dict)
    ]
    report["italy_textile_district_scope"] = ["Prato", "Como", "Biella"]
    report["district_candidate_counts"] = {
        "Prato": sum(item.get("source_kind") == "PRATO_DEADSTOCK" for item in candidates),
        "Como": sum(item.get("source_kind") == "COMO_SILK_STOCK" for item in candidates),
        "Biella": sum(item.get("source_kind") == "BIELLA_WOOL_STOCK" for item in candidates),
    }
    return report
