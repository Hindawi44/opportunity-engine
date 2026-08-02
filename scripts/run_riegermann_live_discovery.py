#!/usr/bin/env python3
"""Run one bounded live Riegermann clothing-auction pilot."""
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
from opportunity_engine.discovery.germany_riegermann_query_pagination import (
    install_riegermann_query_catalog_compatibility,
)

install_riegermann_query_catalog_compatibility()

from opportunity_engine.discovery.germany_riegermann_live import (
    DEFAULT_MAX_RESPONSE_BYTES,
    run_riegermann_live_discovery,
)
from opportunity_engine.discovery.unified_opportunity_report import (
    write_unified_opportunity_report,
)
from opportunity_engine.markets.germany import load_germany_market_profile


DEFAULT_CATALOG_URL = (
    "https://www.riegermann.de/de/objekte/au-908/"
    "versteigerung_cabrini_gmbh?Lstatus=1"
)
DEFAULT_INFORMATION_URL = (
    "https://www.riegermann.de/de/2019_versteigerung_cabrini_gmbh/a/908"
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
        default="artifacts/germany-riegermann-live",
    )
    parser.add_argument("--catalog-url", default=DEFAULT_CATALOG_URL)
    parser.add_argument("--information-url", default=DEFAULT_INFORMATION_URL)
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
    if args.persist_unified and not str(args.database_url).strip():
        raise SystemExit("--database-url must not be empty with --persist-unified")

    profile = load_germany_market_profile(ROOT)
    live = run_riegermann_live_discovery(
        args.catalog_url,
        information_url=args.information_url or None,
        timeout=args.timeout,
        max_response_bytes=args.max_response_bytes,
        item_verification_limit=args.item_verification_limit,
    )
    result = apply_post_verification_top5_hard_gate(live.discovery_result)
    report = result["search_run_report"]
    report["market_code"] = profile.market_code
    report["market_name"] = profile.market_name
    report["currency"] = profile.currency_code
    report["language_codes"] = list(profile.language_codes)
    report["transaction_scope"] = profile.transaction_scope
    report["market_profile_id"] = profile.profile_id
    report["source_mode"] = "RIEGERMANN"
    report["source_target"] = "RIEGERMANN_AUCTION_908"
    report["query_pack"] = "RIEGERMANN_BOUNDED_EVENT_V1"
    report["currency_conversion_performed"] = False
    report["tax_calculation_performed"] = False
    report["customs_calculation_performed"] = False
    report["logistics_calculation_performed"] = False

    output_dir = Path(args.output_dir)
    paths = write_discovery_artifacts(result, output_dir)
    diagnostics_path = output_dir / "riegermann-live-diagnostics.json"
    diagnostics_path.write_text(
        json.dumps(
            live.diagnostics,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    paths["riegermann_live_diagnostics"] = diagnostics_path

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

    print(f"Status: {report['status']}")
    print(f"Market: {profile.market_code} / {profile.market_name}")
    print(f"Currency: {profile.currency_code}")
    print(f"Source: {report['source_mode']}")
    print(
        "Auction identity: "
        f"{report['riegermann_live']['auction_identity']}"
    )
    print(
        "Catalog item URLs: "
        f"{report['riegermann_live']['catalog_item_url_count']}"
    )
    print(
        "Parsed child lots: "
        f"{report['riegermann_live']['parsed_child_lot_count']}"
    )
    print(
        "Promoted bulk lots: "
        f"{report['riegermann_live']['promoted_bulk_lot_count']}"
    )
    print(f"Top opportunities: {report['top5_count']}")
    for name, path in paths.items():
        print(f"{name}: {path}")

    if persistence_failure is not None:
        print(f"Unified persistence failed: {persistence_failure}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
