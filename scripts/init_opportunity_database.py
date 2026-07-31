#!/usr/bin/env python3
"""Initialize or upgrade the opportunity-engine database with Alembic."""
from __future__ import annotations

import argparse
import json
import os

from sqlalchemy import inspect, text

from opportunity_engine.persistence import (
    DEFAULT_DATABASE_URL,
    create_database_engine,
    upgrade_database,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply opportunity-engine database migrations"
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("OPPORTUNITY_DATABASE_URL", DEFAULT_DATABASE_URL),
    )
    parser.add_argument("--revision", default="head")
    parser.add_argument("--config", default="alembic.ini")
    args = parser.parse_args()

    upgrade_database(
        args.database_url,
        revision=args.revision,
        config_path=args.config,
    )
    engine = create_database_engine(args.database_url)
    inspector = inspect(engine)
    with engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()

    print(
        json.dumps(
            {
                "database_url": args.database_url,
                "revision": revision,
                "tables": sorted(inspector.get_table_names()),
                "changes_final_decision": False,
                "changes_ranking": False,
                "changes_top5": False,
                "changes_alerts": False,
            },
            ensure_ascii=False,
        )
    )
    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
