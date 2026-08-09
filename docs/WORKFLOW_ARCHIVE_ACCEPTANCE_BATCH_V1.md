# Workflow Archive — Acceptance Batch V1

This batch removes historical V2/V3 acceptance and validation workflow shells from
`.github/workflows` while preserving their exact YAML under `docs/workflow-archive`.

## Archived in this batch

- `v2.6.6-live-dry-run.yml`
- `v2.7.1-real-dataset-validation.yml`
- `v2.7.2.2-internal-score-audit.yml`
- `v2.7.2.3-score-engine-trace-audit.yml`
- `v2.7.2.4.1-research-candidate-audit.yml`
- `v2.7.2.4.2-bootstrap-pipeline-integration.yml`
- `v2.7.2.4.3-external-evidence-execution-audit.yml`
- `v2.7.2.4.4-brave-transport-response-audit.yml`
- `v2.7.2.4.5-brave-response-content-audit.yml`
- `v2.7.2.4.7-comparable-acceptance-audit.yml`
- `v2.7.2.5-external-financial-final-score.yml`
- `v2.8.1-external-market-comparables.yml`
- `v2.8.2-comparable-evidence-integration.yml`
- `v2.8.2b-comparable-evidence-e2e-acceptance.yml`
- `v2.9-auction-cost-logistics-e2e.yml`
- `v2.10-verified-financial-integration.yml`
- `v2.11-live-opportunity-validation.yml`
- `v30-multi-opportunity-ranking.yml`
- `v31-live-batch-validation.yml`
- `v3.4-persistent-opportunity-state.yml`
- `v3.5-opportunity-alert-review-queue.yml`
- `v3.6-multi-source-ingestion.yml`
- `v3.7-production-pilot.yml`

These files are historical regression/acceptance contracts. Their production capabilities
have been superseded by the current unified runtime, lifecycle persistence, human-review flow,
one-opportunity analysis path, and Multi-Market Daily Operator Checkpoint.

## Current GitHub Actions surface after this batch

Exactly eight workflow files remain in `.github/workflows`:

1. `multi-market-daily-operator-checkpoint.yaml` — sole automatic production scheduler.
2. `tests.yml` — canonical repository CI.
3. `one-opportunity-commercial-analysis.yaml` — explicit human commercial analysis.
4. `sweden-clothing-inventory-live.yaml` — manual country/source diagnostic.
5. `germany-clothing-inventory-live.yaml` — manual country/source diagnostic.
6. `riegermann-active-auctions-live.yaml` — retained source diagnostic.
7. `venta-active-clothing-watch.yaml` — retained source diagnostic.
8. `dpv-active-clothing-watch.yaml` — retained source diagnostic.

The last three source diagnostics are reviewed separately for `pull_request` removal so they
cannot execute live source work merely because code changes.

## Compatibility

Historical tests that still read the former `.github/workflows/<name>` paths use the test-only
archive fallback in `tests/conftest.py`. The YAML remains byte-for-byte preserved in the archive;
GitHub Actions no longer registers it as runnable automation.

No Python runtime implementation is deleted by this batch. No market, OpenAI limit, automatic
schedule cadence, contact, bid, reservation, purchase, or payment behavior changes.
