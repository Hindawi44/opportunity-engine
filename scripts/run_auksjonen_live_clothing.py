#!/usr/bin/env python3
"""Collect bounded live Auksjonen clothing categories and promote inventory lots."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from opportunity_engine.discovery.auksjonen_exact_item_verification import (
    DEFAULT_ITEM_VERIFICATION_LIMIT,
    verify_auksjonen_inventory_lots,
    write_auksjonen_exact_item_evidence,
)
from opportunity_engine.discovery.auksjonen_multi_category_adapter import (
    AuksjonenMultiCategoryCollector,
    write_multi_category_artifact,
)
from opportunity_engine.discovery.auksjonen_public_api_adapter import (
    DEFAULT_PAGE_SIZE,
    MAX_LISTINGS,
    MAX_PAGES,
    write_live_clothing_artifacts,
)
from opportunity_engine.discovery.auksjonen_unified_lifecycle import (
    write_auksjonen_unified_artifacts,
)
from opportunity_engine.parser_gap_rescue import (
    OVERLAY_FILENAME as PARSER_RESCUE_OVERLAY_FILENAME,
    SUPPORTED_SOURCE as PARSER_RESCUE_SOURCE,
    apply_auksjonen_parser_rescue,
    load_parser_rescue_terms,
)


def _write_fallback_persistence_error(
    output_dir: Path,
    report_path: Path,
    exc: Exception,
) -> Path:
    path = output_dir / "unified-persistence-error.json"
    path.write_text(
        json.dumps(
            {
                "status": "FAILED",
                "pipeline_name": "UNIFIED_DISCOVERY_PERSISTENCE_V1",
                "report_path": str(report_path),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "json_reports_remain_official": True,
                "report_deleted": False,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default="artifacts/auksjonen-live-clothing",
    )
    parser.add_argument("--max-listings", type=int, default=MAX_LISTINGS)
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES)
    parser.add_argument(
        "--item-verification-limit",
        type=int,
        default=DEFAULT_ITEM_VERIFICATION_LIMIT,
        help="Maximum active inventory lots whose exact public item pages are verified.",
    )
    parser.add_argument(
        "--parser-rescue-overlay",
        default=os.environ.get("PARSER_RESCUE_OVERLAY_PATH", ""),
        help="Optional durable parser-rescue overlay learned from verified prior PARSER_GAP cases.",
    )
    parser.add_argument("--persist-unified", action="store_true")
    parser.add_argument(
        "--database-url",
        default=os.environ.get(
            "OPPORTUNITY_DATABASE_URL",
            "sqlite:///data/opportunity_engine.db",
        ),
    )
    parser.add_argument("--alembic-config", default="alembic.ini")
    args = parser.parse_args()

    if args.persist_unified and not str(args.database_url).strip():
        raise SystemExit("--database-url must not be empty with --persist-unified")
    if args.item_verification_limit < 0:
        raise SystemExit("--item-verification-limit must be non-negative")

    output_dir = Path(args.output_dir)
    result = AuksjonenMultiCategoryCollector(
        max_listings=args.max_listings,
        page_size=args.page_size,
        max_pages=args.max_pages,
    ).collect()
    base_collection = result.combined

    overlay_path_text = str(args.parser_rescue_overlay or "").strip()
    if not overlay_path_text:
        input_root_text = str(os.environ.get("INPUT_ROOT") or "").strip()
        if input_root_text:
            overlay_path_text = (
                Path(input_root_text) / "learning" / PARSER_RESCUE_OVERLAY_FILENAME
            ).as_posix()

    learned_terms: tuple[str, ...] = ()
    if overlay_path_text:
        overlay_path = Path(overlay_path_text)
        if overlay_path.exists():
            learned_terms = load_parser_rescue_terms(
                overlay_path,
                PARSER_RESCUE_SOURCE,
            )
    collection = apply_auksjonen_parser_rescue(base_collection, learned_terms)
    rescued_count = (
        len(collection.inventory_opportunities)
        - len(base_collection.inventory_opportunities)
    )

    exact_item_evidence = verify_auksjonen_inventory_lots(
        collection.inventory_opportunities,
        limit=args.item_verification_limit,
    )

    paths = write_live_clothing_artifacts(collection, output_dir)
    paths["category_scans"] = write_multi_category_artifact(result, output_dir)
    paths["exact_item_verification"] = write_auksjonen_exact_item_evidence(
        exact_item_evidence,
        output_dir,
    )
    paths.update(
        write_auksjonen_unified_artifacts(
            collection,
            output_dir,
            exact_item_evidence=exact_item_evidence,
        )
    )

    persistence_failure: Exception | None = None
    if args.persist_unified:
        try:
            from opportunity_engine.persistence.live_unified_persistence import (
                persist_unified_report_with_artifacts,
            )

            _, persistence_summary_path = persist_unified_report_with_artifacts(
                paths["unified_opportunity_report"],
                output_dir,
                database_url=args.database_url,
                config_path=args.alembic_config,
            )
            paths["unified_persistence_summary"] = persistence_summary_path
        except Exception as exc:
            persistence_failure = exc
            error_path = getattr(exc, "artifact_path", None)
            if not isinstance(error_path, Path):
                error_path = _write_fallback_persistence_error(
                    output_dir,
                    paths["unified_opportunity_report"],
                    exc,
                )
            paths["unified_persistence_error"] = error_path

    opportunities = collection.inventory_opportunities
    individuals = collection.individual_clothing_items
    verified_count = sum(
        1 for row in exact_item_evidence.values() if row.get("exact_item_page_verified") is True
    )
    print(f"Categories scanned: {len(result.scans)}")
    for scan in result.scans:
        print(
            f"- {scan.category.label} ({scan.category.category_id}): "
            f"reported={scan.reported_size}, pages={scan.pages_fetched}, "
            f"items={scan.items_received}, complete={scan.scan_complete}"
        )
    print(f"Combined reported size: {collection.reported_size}")
    print(f"Pages fetched across categories: {collection.pages_fetched}")
    print(f"Items received across categories: {collection.items_received}")
    print(f"Full multi-category scan complete: {result.scan_complete}")
    print(f"Active clothing items: {len(collection.listings)}")
    print(f"Parser rescue terms loaded: {len(learned_terms)}")
    print(f"Parser rescue promotions: {rescued_count}")
    print(f"Valid inventory opportunities: {len(opportunities)}")
    print(f"Exact item pages attempted: {len(exact_item_evidence)}")
    print(f"Exact item pages verified: {verified_count}")
    print(f"Individual clothing items excluded from Top 5: {len(individuals)}")
    print(f"Errors: {len(collection.errors)}")
    print("Paid Brave/OpenAI calls: 0")
    if opportunities:
        first = opportunities[0]
        print(f"First inventory opportunity: {first.title}")
        print(f"First inventory URL: {first.url}")
    else:
        print("No valid inventory-lot opportunities found.")
    for name, path in paths.items():
        print(f"{name}: {path}")

    if persistence_failure is not None:
        print(f"Unified persistence failed: {persistence_failure}", file=sys.stderr)
        return 2
    return 0 if result.scan_complete and not collection.errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
