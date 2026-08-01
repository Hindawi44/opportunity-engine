# Optional Unified Persistence V1

## Purpose

The structured clothing discovery runner can now copy its completed canonical
`unified-opportunity-report.json` into SQLite when explicitly requested.

Normal discovery remains JSON-only. Persistence is opt-in and runs only after all
existing discovery artifacts and the unified report have been written.

## Run without persistence

```bash
PYTHONPATH=src python scripts/run_clothing_inventory_discovery_search.py \
  --output-dir artifacts/clothing-inventory-discovery
```

This remains the default behavior and does not initialize or write a database.

## Run with persistence

```bash
PYTHONPATH=src python scripts/run_clothing_inventory_discovery_search.py \
  --output-dir artifacts/clothing-inventory-discovery \
  --persist-unified \
  --database-url sqlite:///data/opportunity_engine.db
```

The database URL can also be supplied through `OPPORTUNITY_DATABASE_URL`.
Alembic migrations are applied before the report is copied.

## Result artifacts

On success:

```text
unified-opportunity-report.json
unified-persistence-summary.json
```

On persistence failure:

```text
unified-opportunity-report.json
unified-persistence-error.json
```

A persistence failure returns a non-zero process status, but it does not delete or
rewrite the discovery reports. JSON remains the official operational output.

## Durable state

The opt-in step stores:

- canonical opportunity snapshots;
- distinct evidence snapshots;
- first-seen and last-seen timestamps;
- append-only workflow status changes;
- one source-run row, including valid zero-record runs.

Repeated persistence of the same report is idempotent for opportunity identity,
evidence identity, and the deterministic source-run identity.

## Boundaries

This step does not:

- change discovery, lifecycle classification, ranking, Top 5, or alerts;
- make SQLite mandatory for normal discovery;
- replace JSON reports;
- contact sellers;
- bid, purchase, approve, or pay;
- add FastAPI, Streamlit, Docker, PostgreSQL, or external services.
