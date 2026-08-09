# Workflow Cleanup — Legacy Batch V1

This batch removes only superseded workflow YAML files from `.github/workflows`.
Runtime source code, tests, adapters, SQLite/lifecycle code, and Git history remain intact.

Removed workflow files:

- `daily-opportunity-pipeline.yml`
- `scheduled-agent.yml`
- `discovery-v1-clothing-inventory.yml`
- `discovery-v1.1-live-search.yml`
- `discovery-v1.2-live-pilot.yml`
- `v3.2-continuous-opportunity-monitoring.yml`
- `v3.3-live-source-ingestion.yml`

Why these are safe to remove:

- the old automatic schedules were already retired by scheduler consolidation;
- the production owner is `multi-market-daily-operator-checkpoint.yaml`;
- the useful Norway cross-source capability formerly exposed through V1.2 was migrated into the production checkpoint through `run_cross_source_checkpoint_adapter.py`;
- V3.2/V3.3 runtime logic remains in normal Python modules and tests, but their standalone workflow shells are no longer production owners;
- Git retains complete history for rollback/reference.

Important GitHub Actions UI note:

Several `TEMP`/`Temporary` workflow names still appear in the Actions API even though their YAML files are already absent from the default branch. They are historical workflow records, not current repository workflow files. They cannot be removed by deleting a file that no longer exists.

This batch intentionally does not remove:

- `multi-market-daily-operator-checkpoint.yaml`;
- `tests.yml`;
- `one-opportunity-commercial-analysis.yaml`;
- current Sweden/Germany source diagnostic workflows;
- V2/V3 acceptance workflows, which will be handled separately after CI confirms this batch.
