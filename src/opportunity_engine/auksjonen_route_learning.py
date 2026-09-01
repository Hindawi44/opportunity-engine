"""Derive a review-only Norway route candidate from verified Auksjonen item pages.

This module does not change the Auksjonen collector or persist into Search Success
Learning. It only augments the same-run Unified Learning Spine input in memory so
Memory V2 can observe the native source route across independent checkpoint days.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.production_search_outcome_bridge_v1 import (
    augment_unified_learning_spine,
    install_unified_memory_query_outcome_metrics,
    write_production_search_outcome_bridge,
)
from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    classify_project_domain,
)
from opportunity_engine.unified_learning_spine import (
    DAILY_LEARNING_FILENAME,
    MISSED_OPPORTUNITIES_RELATIVE_PATH,
    OUTPUT_FILENAME,
    RIVER_ITEMS_FILENAME,
    SEARCH_SUCCESS_RELATIVE_PATH,
    _attach_summary,
    _read_optional_json,
    _write_json,
    build_unified_learning_spine,
)

AUKSJONEN_EXACT_ITEM_RELATIVE_PATH = Path(
    "no-auksjonen/auksjonen-exact-item-verification.json"
)
AUKSJONEN_EXACT_ITEM_SCHEMA = "auksjonen-exact-item-verification-1.0"
AUKSJONEN_PROVIDER = "direct_public_source"
AUKSJONEN_MARKET = "NO"
AUKSJONEN_PARENT_DOMAIN = "auksjonen.no"
AUKSJONEN_PATHWAY = "PUBLIC_CATEGORY_TO_EXACT_ITEM"
AUKSJONEN_STABLE_QUERY = "Auksjonen clothing inventory category scan"

# Memory V2 is imported later by the established daily CLI hook. Installing the
# additive query-outcome metrics here patches the module globals before the same
# checkpoint calls write_unified_memory_v2(). No search or production mutation
# is introduced.
install_unified_memory_query_outcome_metrics()


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _is_auksjonen_url(value: object) -> bool:
    text = _text(value).lower()
    return text.startswith("https://") and (
        "://www.auksjonen.no/" in text or "://ny.auksjonen.no/" in text
    )


def _verified_clothing_items(
    exact_item_verification: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    payload = _mapping(exact_item_verification)
    if _text(payload.get("schema_version")) != AUKSJONEN_EXACT_ITEM_SCHEMA:
        return []

    verified: list[dict[str, Any]] = []
    for raw in _rows(payload.get("items")):
        if raw.get("exact_item_page_verified") is not True:
            continue
        if _text(raw.get("status")).upper() != "VERIFIED":
            continue
        url = _text(raw.get("final_url") or raw.get("url"))
        if not _is_auksjonen_url(url):
            continue
        domain = classify_project_domain(
            text=" ".join(
                part
                for part in (
                    _text(raw.get("title")),
                    _text(raw.get("description")),
                )
                if part
            )
        )
        if domain != CLOTHING_INVENTORY:
            continue
        verified.append(
            {
                "url": url,
                "title": _text(raw.get("title")) or None,
                "object_id": raw.get("object_id"),
                "quantity": raw.get("quantity"),
                "condition": _text(raw.get("condition")) or None,
            }
        )
    return verified


def build_auksjonen_native_route_candidate(
    exact_item_verification: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Return one stable CANDIDATE route only when exact clothing lots are verified."""
    verified = _verified_clothing_items(exact_item_verification)
    if not verified:
        return None
    urls = sorted({_text(row.get("url")) for row in verified if _text(row.get("url"))})
    if not urls:
        return None
    return {
        "provider": AUKSJONEN_PROVIDER,
        "market_code": AUKSJONEN_MARKET,
        "parent_domain": AUKSJONEN_PARENT_DOMAIN,
        "pathway": AUKSJONEN_PATHWAY,
        "query": AUKSJONEN_STABLE_QUERY,
        "status": "CANDIDATE",
        "independent_run_count": 0,
        "supporting_run_ids": [],
        "verified_exact_lot_url_count": len(urls),
        "verified_exact_lot_urls": urls,
        "automatic_activation": False,
        "production_query_mutation": False,
        "production_mutation": False,
        "source_artifact_schema": AUKSJONEN_EXACT_ITEM_SCHEMA,
    }


def _route_identity(route: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        _text(route.get("provider")).lower(),
        _text(route.get("market_code")).upper(),
        _text(route.get("parent_domain") or route.get("result_domain")).lower(),
        _text(route.get("pathway")).upper(),
    )


def augment_search_success_with_auksjonen_route(
    search_success_memory: Mapping[str, Any] | None,
    exact_item_verification: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Add/replace only the same-run Auksjonen native route in an in-memory copy."""
    success = dict(_mapping(search_success_memory))
    route = build_auksjonen_native_route_candidate(exact_item_verification)
    if route is None:
        return success

    identity = _route_identity(route)
    routes = [
        dict(row)
        for row in _rows(success.get("route_learning"))
        if _route_identity(row) != identity
    ]
    routes.append(route)
    success["route_learning"] = routes
    return success


def write_unified_learning_spine_with_native_routes(
    output_dir: str | Path,
    *,
    input_root: str | Path,
) -> dict[str, Any]:
    """Write the Spine with Auksjonen route + production query outcome evidence."""
    output = Path(output_dir)
    root = Path(input_root)
    output.mkdir(parents=True, exist_ok=True)

    search_success = augment_search_success_with_auksjonen_route(
        _read_optional_json(root / SEARCH_SUCCESS_RELATIVE_PATH),
        _read_optional_json(root / AUKSJONEN_EXACT_ITEM_RELATIVE_PATH),
    )
    bridge = write_production_search_outcome_bridge(
        output,
        input_root=root,
    )
    spine = build_unified_learning_spine(
        unified_intelligence_items=_read_optional_json(output / RIVER_ITEMS_FILENAME),
        search_success_memory=search_success,
        missed_opportunity_memory=_read_optional_json(root / MISSED_OPPORTUNITIES_RELATIVE_PATH),
        daily_learning=_read_optional_json(output / DAILY_LEARNING_FILENAME),
    )
    spine = augment_unified_learning_spine(spine, bridge)
    _write_json(output / OUTPUT_FILENAME, spine)
    _attach_summary(output, spine)
    return spine
