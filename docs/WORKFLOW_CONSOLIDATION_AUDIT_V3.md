# Workflow Consolidation Audit V3

## Decision

`multi-market-daily-operator-checkpoint.yaml` is the single automatic production scheduler.
Its default market-intelligence path is limited to clothing inventory/liquidation in Norway,
Sweden, and Germany (NO/SE/DE).

Do not copy whole historical workflows into the checkpoint. Reuse only bounded runtime
capabilities that fill a current production gap.

## Production automatic owner

| Workflow | Classification | Decision |
| --- | --- | --- |
| `multi-market-daily-operator-checkpoint.yaml` | PRODUCTION_AUTOMATIC | KEEP. Sole live `schedule` owner. |

## CI owner

| Workflow | Classification | Decision |
| --- | --- | --- |
| `tests.yml` | CI | KEEP. Repository tests, not market discovery. |

## Manual operational tools retained

| Workflow | Classification | Decision |
| --- | --- | --- |
| `one-opportunity-commercial-analysis.yaml` | KEEP_MANUAL | Human-supplied commercial inputs; intentionally downstream of discovery. |
| `sweden-clothing-inventory-live.yaml` | KEEP_MANUAL | Country/source pilot and diagnostics; do not duplicate Blinto in daily runtime. |
| `germany-clothing-inventory-live.yaml` | KEEP_MANUAL | German pilot/open-web diagnostics; daily checkpoint already owns German production sources. |
| `riegermann-active-auctions-live.yaml` | KEEP_MANUAL | Source-specific diagnostic/manual rerun; standalone schedule retired. |
| `venta-active-clothing-watch.yaml` | KEEP_MANUAL | Source-specific diagnostic/manual rerun; standalone schedule retired. |
| `dpv-active-clothing-watch.yaml` | KEEP_MANUAL | Source-specific diagnostic/manual rerun; standalone schedule retired. |
| `discovery-v1.2-live-pilot.yml` | KEEP_MANUAL_REUSE_CODE | Contains useful cross-source verification capability; workflow itself is not a production owner. |
| `v3.7-production-pilot.yml` | KEEP_MANUAL | End-to-end human review pilot. |

## Legacy schedulers retained only for rollback/evidence

| Workflow | Classification | Decision |
| --- | --- | --- |
| `daily-opportunity-pipeline.yml` | LEGACY_MANUAL_ONLY | Automatic schedule retired in consolidation V1. |
| `scheduled-agent.yml` | LEGACY_MANUAL_ONLY | Automatic schedule retired in consolidation V1. |
| `v3.2-continuous-opportunity-monitoring.yml` | LEGACY_MANUAL_ONLY | Hourly schedule retired in consolidation V1. |
| `v3.3-live-source-ingestion.yml` | LEGACY_MANUAL_ONLY | Hourly schedule retired in consolidation V1. |

## Acceptance / historical workflows

These remain useful as regression evidence, focused acceptance tests, or rollback references.
They are not copied into the daily operator runtime.

- `discovery-v1-clothing-inventory.yml`
- `discovery-v1.1-live-search.yml`
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

## Side-feed scope correction

The former `scripts/build_domain_market_intelligence_feed.py` combined the established
NO/SE/DE bulletin with unrelated procurement/secondary B2B lanes. That widened the daily
scope and could add Brave/API activity outside the three approved markets.

V3 changes the default entry point to delegate only to
`scripts/build_domain_market_intelligence_feed_core.py`.

The former side-feed implementation is preserved intact as:

`scripts/build_optional_market_intelligence_side_feeds.py`

It contains fabric procurement and secondary B2B feeds (Merkandi, Fashion Stock Netherlands,
Stockhurt, Jobalots). It is not called by the automatic checkpoint.

This is separation, not deletion.

## Reuse next: Norway cross-source verification

The useful production candidate discovered during this audit is the cross-source verifier in
`scripts/run_cross_source_clothing_verification.py` (currently exposed through
`discovery-v1.2-live-pilot.yml`). It can correlate clothing insolvency leads with exact public
sale channels such as Auksjonen and related auction sources without relying on OpenAI.

Do **not** paste the whole V1.2 workflow into the checkpoint. The next bounded change should
add a checkpoint-compatible adapter/report contract for this verifier, then feed its verified
signals into the existing lifecycle/SQLite/intelligence path.

Until that adapter exists, V1.2 remains manual so the production manifest is not given an
incompatible artifact shape.

## Safety and ownership rules

- one automatic scheduler only;
- NO/SE/DE only in the default daily intelligence path;
- zero results remain valid success where source contracts permit;
- no automatic contact, bid, reservation, purchase, or payment;
- OpenAI remains bounded and advisory;
- optional procurement/B2B lanes do not silently consume the daily search budget;
- country/source pilots remain manual unless explicitly promoted through a tested adapter.
