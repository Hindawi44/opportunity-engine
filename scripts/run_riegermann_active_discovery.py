#!/usr/bin/env python3
"""Discover active public Riegermann clothing auctions and crawl their catalogs."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from opportunity_engine.discovery.clothing_inventory_search import (
    apply_post_verification_top5_hard_gate,
    write_discovery_artifacts,
)
from opportunity_engine.discovery.germany_riegermann_pagination_completion import (
    install_riegermann_catalog_completion_compatibility,
)

install_riegermann_catalog_completion_compatibility()

from opportunity_engine.discovery.germany_riegermann_active import (
    DEFAULT_ACTIVE_AUCTION_LIMIT,
    DEFAULT_ACTIVE_AUCTIONS_URL,
    run_riegermann_active_auction_discovery,
)
from opportunity_engine.discovery.germany_riegermann_live import (
    DEFAULT_MAX_RESPONSE_BYTES,
)
from opportunity_engine.discovery.unified_opportunity_report import (
    write_unified_opportunity_report,
)
from opportunity_engine.markets.germany import load_germany_market_profile


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
        default="artifacts/germany-riegermann-active",
    )
    parser.add_argument("--index-url", default=DEFAULT_ACTIVE_AUCTIONS_URL)
    parser.add_argument(
        "--auction-limit",
        type=int,
        default=DEFAULT_ACTIVE_AUCTION_LIMIT,
    )
    parser.add_argument("--catalog-page-limit", type=int, default=100)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument(
        "--max-response-bytes",
        type=int,
        default=DEFAULT_MAX_RESPONSE_BYTES,
    )
    parser.add_argument(
        "--item-verification-limit",
        type=int,
        default=10,
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

    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    if args.max_response_bytes <= 0:
        raise SystemExit("--max-response-bytes must be positive")
    if not 0 <= args.item_verification_limit <= 50:
        raise SystemExit("--item-verification-limit must be between 0 and 50")
    if not 1 <= args.auction_limit <= 25:
        raise SystemExit("--auction-limit must be between 1 and 25")
    if not 1 <= args.catalog_page_limit <= 200:
        raise SystemExit("--catalog-page-limit must be between 1 and 200")
    if args.persist_unified and not str(args.database_url).strip():
        raise SystemExit("--database-url must not be empty with --persist-unified")

    profile = load_germany_market_profile(ROOT)
    active = run_riegermann_active_auction_discovery(
        args.index_url,
        timeout=args.timeout,
        max_response_bytes=args.max_response_bytes,
        item_verification_limit=args.item_verification_limit,
        catalog_page_limit=args.catalog_page_limit,
        auction_limit=args.auction_limit,
    )
    result = apply_post_verification_top5_hard_gate(active.discovery_result)
    report = result["search_run_report"]
    report["market_code"] = profile.market_code
    report["market_name"] = profile.market_name
    report["currency"] = profile.currency_code
    report["language_codes"] = list(profile.language_codes)
    report["transaction_scope"] = profile.transaction_scope
    report["market_profile_id"] = profile.profile_id
    report["source_mode"] = "RIEGERMANN_ACTIVE"
    report["source_target"] = "RIEGERMANN_ACTIVE_AUCTIONS"
    report["query_pack"] = "RIEGERMANN_ACTIVE_INDEX_V1"
    report["currency_conversion_performed"] = False
    report["tax_calculation_performed"] = False
    report["customs_calculation_performed"] = False
    report["logistics_calculation_performed"] = False

    output_dir = Path(args.output_dir)
    paths = write_discovery_artifacts(result, output_dir)
    diagnostics_path = output_dir / "riegermann-active-diagnostics.json"
    diagnostics_path.write_text(
        json.dumps(
            active.diagnostics,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    paths["riegermann_active_diagnostics"] = diagnostics_path

    unified_report_path = write_unified_opportunity_report(
        result,
        output_dir,
        market_code=profile.market_code,
        currency=profile.currency_code,
        domain="CLOTHING_INVENTORY",
    )
    paths["unified_opportunity_report"] = unified_report_path

    persistence_failure: Exception | None = None
    if args.persist_unified:
        try:
            from opportunity_engine.persistence import (
                UnifiedOpportunityRepository,
                create_database_engine,
                create_session_factory,
                session_scope,
            )
            from opportunity_engine.persistence.historical_market_evidence_report import (
                write_historical_market_evidence_report,
            )
            from opportunity_engine.persistence.live_unified_persistence import (
                persist_unified_report_with_artifacts,
            )

            _, persistence_summary_path = persist_unified_report_with_artifacts(
                unified_report_path,
                output_dir,
                database_url=args.database_url,
                config_path=args.alembic_config,
            )
            paths["unified_persistence_summary"] = persistence_summary_path

            engine = create_database_engine(args.database_url)
            try:
                factory = create_session_factory(engine)
                with session_scope(factory) as session:
                    _, historical_report_path, historical_summary_path = (
                        write_historical_market_evidence_report(
                            UnifiedOpportunityRepository(session),
                            output_dir,
                        )
                    )
                paths["historical_market_evidence_report"] = historical_report_path
                paths["historical_market_evidence_summary"] = historical_summary_path
            finally:
                engine.dispose()
        except Exception as exc:
            persistence_failure = exc
            error_path = getattr(exc, "artifact_path", None)
            if not isinstance(error_path, Path):
                error_path = _write_fallback_persistence_error(
                    output_dir,
                    unified_report_path,
                    exc,
                )
            paths["unified_persistence_error"] = error_path

    diagnostics = report["riegermann_active"]
    print(f"Status: {report['status']}")
    print(f"Market: {profile.market_code} / {profile.market_name}")
    print(f"Currency: {profile.currency_code}")
    print(f"Source: {report['source_mode']}")
    print(
        "Auction entries discovered: "
        f"{diagnostics['auction_entries_discovered']}"
    )
    print(
        "Active clothing auctions: "
        f"{diagnostics['active_clothing_entries_discovered']}"
    )
    print(f"Selected auctions: {diagnostics['selected_auction_count']}")
    print(f"Catalog item URLs: {diagnostics['catalog_item_url_count']}")
    print(f"Parsed child lots: {diagnostics['parsed_child_lot_count']}")
    print(f"Promoted bulk lots: {diagnostics['promoted_bulk_lot_count']}")
    print(f"Top opportunities: {report['top5_count']}")
    for name, path in paths.items():
        print(f"{name}: {path}")

    if persistence_failure is not None:
        print(f"Unified persistence failed: {persistence_failure}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
