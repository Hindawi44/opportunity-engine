#!/usr/bin/env python3
"""Build historical market evidence reports from the unified SQLite store."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from opportunity_engine.persistence.database import (  # noqa: E402
    DEFAULT_DATABASE_URL,
    create_database_engine,
    create_session_factory,
    session_scope,
)
from opportunity_engine.persistence.historical_market_evidence_report import (  # noqa: E402
    write_historical_market_evidence_report,
)
from opportunity_engine.persistence.unified_repository import (  # noqa: E402
    UnifiedOpportunityRepository,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.environ.get("OPPORTUNITY_DATABASE_URL", DEFAULT_DATABASE_URL),
        help="SQLAlchemy database URL containing unified opportunity records",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/historical-market-evidence",
        help="Directory for JSON and text reports",
    )
    args = parser.parse_args()

    if not str(args.database_url).strip():
        raise SystemExit("--database-url must not be empty")

    engine = create_database_engine(args.database_url)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            report, report_path, summary_path = write_historical_market_evidence_report(
                UnifiedOpportunityRepository(session),
                args.output_dir,
            )
    finally:
        engine.dispose()

    summary = report["summary"]
    print(f"Trusted historical evidence: {summary['trusted_historical_evidence_count']}")
    print(f"Trusted historical price records: {summary['trusted_historical_price_record_count']}")
    print(f"Manual review: {summary['manual_review_count']}")
    print(f"JSON report: {report_path}")
    print(f"Text summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
