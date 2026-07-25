# Workflow Inventory Report v1.0

**Scope:** every file currently under `.github/workflows/`  
**Inventory date:** 2026-07-25  
**Workflow files represented:** 31  
**Change policy:** documentation only; no workflow was deleted, moved, disabled, renamed, or given a different trigger.

## Executive findings

### Primary discovery workflow candidate

`discovery-v1.2-live-pilot.yml` is the strongest `PRIMARY_DISCOVERY_CANDIDATE`.

Reason: it starts from the Discovery Engine, runs the Brave-backed live pilot only when manually dispatched, applies the V1.5/V1.6 discovery-support filters, and creates phone-readable text plus JSON artifacts. It is closer to the approved scenario-driven operator journey than the older source-first automated pipeline.

### End-to-end review workflow candidate

`v3.7-production-pilot.yml` is the strongest `END_TO_END_REVIEW_CANDIDATE`.

Reason: it exercises the latest production-pilot orchestration, generates a summary artifact, and sits at the downstream end of the existing Analysis/Review path. Its hourly schedule and pull-request trigger should be reviewed in a separate cleanup PR; this inventory does not change them.

### Main overlap findings

1. `scheduled-agent.yml`, `daily-opportunity-pipeline.yml`, `discovery-v1.2-live-pilot.yml`, `v3.2-continuous-opportunity-monitoring.yml`, and `v3.3-live-source-ingestion.yml` all execute some form of repeated opportunity discovery or ingestion.
2. `daily-opportunity-pipeline.yml` is broad, writes many repository snapshots, and reflects the older fixed-source/source-first generation. It overlaps with the approved discovery-first path and should not become the primary operator entry point.
3. Most V2.7.2.x workflows are narrow audits created during development. They provide useful historical evidence but create substantial Actions-view noise.
4. V2.8 through V3.7 workflows are mostly acceptance boundaries around Analysis, monitoring, state, and review capabilities. Many run the full regression suite independently, producing duplicated pull-request checks.
5. `tests.yml` is the repository-wide quality gate and overlaps with the full-regression step embedded in many acceptance workflows.

## Trigger notation

- `PR`: `pull_request`
- `PUSH`: `push`
- `MANUAL`: `workflow_dispatch`
- `SCHEDULE`: cron schedule

## Complete workflow inventory

| # | File | Displayed workflow name | Triggers | Manual | Schedule | Main responsibility | Owner | Classification | Overlap / classification evidence |
|---:|---|---|---|---|---|---|---|---|---|
| 1 | `.github/workflows/tests.yml` | تشغيل الاختبارات | PUSH `main`; PR `main` | No | — | Full repository pytest gate and test-log artifact | `REPOSITORY_QUALITY` | `ACTIVE_PRODUCTION_SUPPORT` | Canonical repository-wide quality gate; duplicates regression runs embedded in acceptance workflows. |
| 2 | `.github/workflows/discovery-v1-clothing-inventory.yml` | Discovery V1 Clothing Inventory | PR `main`; MANUAL | Yes | — | Clothing Inventory Opportunity Map and classifier acceptance plus full regression | `DISCOVERY_ENGINE` | `ACCEPTANCE_TEST` | Acceptance-only; overlaps with `tests.yml` through full regression. |
| 3 | `.github/workflows/discovery-v1.1-live-search.yml` | Discovery V1.1 Live Search Adapter | PR `main`; MANUAL | Yes | — | Live-search adapter contract tests plus full regression | `DISCOVERY_ENGINE` | `ACCEPTANCE_TEST` | Tests the provider adapter; not the preferred operator workflow by itself. |
| 4 | `.github/workflows/discovery-v1.2-live-pilot.yml` | Discovery V1.6 Opportunity Quality Engine | PR `main`; MANUAL | Yes | — | Discovery quality/filter acceptance; manual Brave live pilot; phone and JSON reports | `DISCOVERY_ENGINE` | `PRIMARY_DISCOVERY_CANDIDATE` | Best phone-oriented scenario-driven discovery entry; live job is manual-only. |
| 5 | `.github/workflows/scheduled-agent.yml` | Scheduled ODS research agent | MANUAL; SCHEDULE | Yes | `17 */6 * * *` | Autonomous ODS research cycle, state cache, email delivery | `DISCOVERY_ENGINE` | `ACTIVE_PRODUCTION_SUPPORT` | Repeated discovery overlaps with daily pipeline and V3.2/V3.3; separate ODS state model. |
| 6 | `.github/workflows/daily-opportunity-pipeline.yml` | Automated opportunity pipeline | MANUAL; SCHEDULE | Yes | `15 */6 * * *` | Broad V2.3 source-first pipeline; commits many generated snapshots | `MIXED_OR_UNCLEAR` | `ACTIVE_PRODUCTION_SUPPORT` | Operationally active but architecturally legacy/source-first; high overlap and write surface. |
| 7 | `.github/workflows/v2.6.6-live-dry-run.yml` | V2.6.6 Live Dry Run | MANUAL | Yes | — | Runs production readiness and the daily pipeline twice to verify caching/repeat protection | `REPOSITORY_QUALITY` | `HISTORICAL_DIAGNOSTIC` | Development-era readiness diagnostic; not a normal operator entry point. |
| 8 | `.github/workflows/v2.7.1-real-dataset-validation.yml` | V2.7.1 Real Dataset Validation | MANUAL | Yes | — | Validates historical real-dataset behavior | `ANALYSIS_ENGINE` | `ACCEPTANCE_TEST` | Version-specific validation; retained as acceptance evidence. |
| 9 | `.github/workflows/v2.7.2.2-internal-score-audit.yml` | V2.7.2.2 Internal Score Audit | MANUAL | Yes | — | Audits internal scoring output | `ANALYSIS_ENGINE` | `HISTORICAL_DIAGNOSTIC` | Narrow score-debug workflow superseded by later verified financial integration. |
| 10 | `.github/workflows/v2.7.2.3-score-engine-trace-audit.yml` | V2.7.2.3 Score Engine Trace Audit | MANUAL | Yes | — | Produces score-engine trace evidence | `ANALYSIS_ENGINE` | `HISTORICAL_DIAGNOSTIC` | Narrow trace diagnostic; overlaps with internal-score and final-score audits. |
| 11 | `.github/workflows/v2.7.2.4.1-research-candidate-audit.yml` | V2.7.2.4.1 Research Candidate Audit | MANUAL | Yes | — | Audits research candidate selection | `ANALYSIS_ENGINE` | `HISTORICAL_DIAGNOSTIC` | Intermediate external-research debugging workflow. |
| 12 | `.github/workflows/v2.7.2.4.2-bootstrap-pipeline-integration.yml` | V2.7.2.4.2 Bootstrap Pipeline Integration | MANUAL | Yes | — | Verifies research bootstrap/pipeline integration | `ANALYSIS_ENGINE` | `HISTORICAL_DIAGNOSTIC` | Transitional integration audit; later V2.8–V2.10 boundaries are authoritative. |
| 13 | `.github/workflows/v2.7.2.4.3-external-evidence-execution-audit.yml` | V2.7.2.4.3 External Evidence Execution Audit | MANUAL | Yes | — | Audits external-evidence execution | `ANALYSIS_ENGINE` | `HISTORICAL_DIAGNOSTIC` | Narrow execution diagnostic with overlap across V2.8 evidence workflows. |
| 14 | `.github/workflows/v2.7.2.4.4-brave-transport-response-audit.yml` | V2.7.2.4.4 Brave Transport Response Audit | MANUAL | Yes | — | Audits Brave transport and HTTP response behavior | `DISCOVERY_ENGINE` | `HISTORICAL_DIAGNOSTIC` | Provider-specific debugging; not governing discovery architecture. |
| 15 | `.github/workflows/v2.7.2.4.5-brave-response-content-audit.yml` | V2.7.2.4.5 Brave Response Content Audit | MANUAL | Yes | — | Audits Brave response content/parsing | `DISCOVERY_ENGINE` | `HISTORICAL_DIAGNOSTIC` | Provider parsing diagnostic; overlaps with live-search adapter tests. |
| 16 | `.github/workflows/v2.7.2.4.7-comparable-acceptance-audit.yml` | V2.7.2.4.7 Comparable Acceptance Audit | MANUAL | Yes | — | Audits comparable acceptance conditions | `ANALYSIS_ENGINE` | `HISTORICAL_DIAGNOSTIC` | Predecessor diagnostic to V2.8 comparable evidence acceptance. |
| 17 | `.github/workflows/v2.7.2.5-external-financial-final-score.yml` | V2.7.2.5 External Financial Final Score | MANUAL | Yes | — | Audits final score after external financial evidence | `ANALYSIS_ENGINE` | `HISTORICAL_DIAGNOSTIC` | Superseded conceptually by V2.10 verified financial integration. |
| 18 | `.github/workflows/v2.8.1-external-market-comparables.yml` | V2.8.1 External Market Comparables Engine | MANUAL with limits/threshold inputs | Yes | — | Executes external comparable research | `ANALYSIS_ENGINE` | `ACTIVE_PRODUCTION_SUPPORT` | Real manual analysis capability; overlaps with V2.8.2 evidence integration. |
| 19 | `.github/workflows/v2.8.2-comparable-evidence-integration.yml` | V2.8.2 Comparable Evidence Integration | MANUAL | Yes | — | Integrates comparable evidence into analysis records | `ANALYSIS_ENGINE` | `ACCEPTANCE_TEST` | Analysis integration boundary; keep separate from operator discovery. |
| 20 | `.github/workflows/v2.8.2b-comparable-evidence-e2e-acceptance.yml` | V2.8.2b Comparable Evidence E2E Acceptance | PR; MANUAL | Yes | — | End-to-end comparable-evidence acceptance | `ANALYSIS_ENGINE` | `ACCEPTANCE_TEST` | Duplicates part of V2.8.2 and repository regression checks. |
| 21 | `.github/workflows/v2.9-auction-cost-logistics-e2e.yml` | V2.9 Auction Cost & Logistics E2E Acceptance | Path-scoped PR; MANUAL | Yes | — | Validates verified auction, fee, VAT, transport/logistics evidence | `ANALYSIS_ENGINE` | `ACCEPTANCE_TEST` | Required financial boundary but not an operator-facing workflow. |
| 22 | `.github/workflows/v2.10-verified-financial-integration.yml` | V2.10 Verified Financial Integration E2E Acceptance | Path-scoped PR; MANUAL | Yes | — | Validates financial integration and decision gate | `ANALYSIS_ENGINE` | `ACCEPTANCE_TEST` | Authoritative acceptance boundary; overlaps with V2.9 and V3.0 regression coverage. |
| 23 | `.github/workflows/v2.11-live-opportunity-validation.yml` | V2.11 Live Opportunity Validation | Path-scoped PR; MANUAL | Yes | — | Validates live opportunity snapshots and generates a report | `ANALYSIS_ENGINE` | `ACCEPTANCE_TEST` | Latest V2 validation boundary; possible component of future E2E review workflow. |
| 24 | `.github/workflows/v30-multi-opportunity-ranking.yml` | V3.0 Multi-Opportunity Ranking E2E Acceptance | PR; MANUAL | Yes | — | Ranking contract and multi-opportunity E2E acceptance | `ANALYSIS_ENGINE` | `ACCEPTANCE_TEST` | Analysis acceptance; not a phone operator entry. |
| 25 | `.github/workflows/v31-live-batch-validation.yml` | V3.1 Live Batch Opportunity Validation | PR `main`; MANUAL | Yes | — | Validates batch behavior and generates a batch report | `ANALYSIS_ENGINE` | `ACCEPTANCE_TEST` | Strong report generator but narrower than V3.7 production pilot. |
| 26 | `.github/workflows/v3.2-continuous-opportunity-monitoring.yml` | V3.2 Continuous Opportunity Monitoring | PR `main`; MANUAL; SCHEDULE | Yes | `17 * * * *` | Continuous monitoring with persisted seen-state | `MONITORING_AND_STATE` | `ACTIVE_PRODUCTION_SUPPORT` | Hourly overlap with V3.3 and V3.7; scheduled PR acceptance behavior is mixed. |
| 27 | `.github/workflows/v3.3-live-source-ingestion.yml` | V3.3 Live Source Ingestion & Snapshot Refresh | PR `main`; MANUAL; SCHEDULE | Yes | `12 * * * *` | Auksjonen-specific ingestion and snapshot refresh | `MONITORING_AND_STATE` | `ACTIVE_PRODUCTION_SUPPORT` | Fixed-source legacy adapter; hourly overlap with V3.2. |
| 28 | `.github/workflows/v3.4-persistent-opportunity-state.yml` | V3.4 Persistent Opportunity State Engine | PR `main`; MANUAL | Yes | — | Lifecycle/state persistence acceptance | `MONITORING_AND_STATE` | `ACCEPTANCE_TEST` | Acceptance-only workflow for state engine. |
| 29 | `.github/workflows/v3.5-opportunity-alert-review-queue.yml` | V3.5 Opportunity Alert & Review Queue | PR `main`; MANUAL | Yes | — | Alert and review-queue acceptance | `REVIEW_QUEUE` | `ACCEPTANCE_TEST` | Important review capability but file currently behaves as an acceptance workflow. |
| 30 | `.github/workflows/v3.6-multi-source-ingestion.yml` | V3.6 Multi-Source Ingestion Acceptance | PR `main`; MANUAL | Yes | — | Multi-source ingestion acceptance and full regression | `MONITORING_AND_STATE` | `ACCEPTANCE_TEST` | Fixed-source-generation acceptance; overlaps with Discovery provider and V3.3. |
| 31 | `.github/workflows/v3.7-production-pilot.yml` | V3.7 Production Pilot Acceptance | PR; MANUAL; SCHEDULE | Yes | `17 * * * *` | Latest production-pilot acceptance and summary generation | `REVIEW_QUEUE` | `END_TO_END_REVIEW_CANDIDATE` | Strongest downstream operator candidate; hourly overlap with V3.2 and schedule collision at minute 17. |

## Classification totals

| Classification | Count |
|---|---:|
| `PRIMARY_DISCOVERY_CANDIDATE` | 1 |
| `END_TO_END_REVIEW_CANDIDATE` | 1 |
| `ACTIVE_PRODUCTION_SUPPORT` | 6 |
| `ACCEPTANCE_TEST` | 14 |
| `HISTORICAL_DIAGNOSTIC` | 9 |
| `UNCERTAIN_REVIEW_REQUIRED` | 0 |
| **Total** | **31** |

## Recommended separate cleanup PR — proposal only

A later PR may simplify the Actions view, but it must begin with an explicit file-by-file plan and a full regression run. Recommended sequence:

1. Keep `tests.yml` as the canonical repository quality gate.
2. Present `discovery-v1.2-live-pilot.yml` as the primary manual discovery workflow, potentially with a clearer operator-facing display name in the separate cleanup PR.
3. Present `v3.7-production-pilot.yml` as the primary end-to-end review workflow after reviewing whether its hourly schedule and PR trigger are still appropriate.
4. Retain scheduled production-support workflows only after confirming ownership and eliminating cadence collisions:
   - `scheduled-agent.yml`
   - `daily-opportunity-pipeline.yml`
   - `v3.2-continuous-opportunity-monitoring.yml`
   - `v3.3-live-source-ingestion.yml`
5. Convert acceptance-only workflows to manual/path-scoped behavior where safe, rather than running many full regression suites on every pull request.
6. Move or disable historical diagnostics only in a dedicated, reviewed cleanup PR; preserve their history and documentation.
7. Do not delete production code, change V2.8–V3.7 formulas, add domains, or create automated purchase/bid/contact actions.

## Inventory integrity statement

This report represents all 31 workflow files found during the inventory. The task changed documentation only. No file under `.github/workflows/` was modified.