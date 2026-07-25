# Workflow Cleanup Implementation Plan v1.0

**Status:** PROPOSED — PLANNING ONLY  
**Scope:** future cleanup of all 31 GitHub Actions workflows  
**Safety:** this document changes no file under `.github/workflows/`

## 1. Target operator surface

The future phone-facing Actions surface should expose exactly two operator workflows:

1. `.github/workflows/discovery-v1.2-live-pilot.yml`
   - future display name: `1 — Discover Clothing Inventory Opportunities`
   - role: manual scenario-driven Discovery run with phone-readable and JSON artifacts.
2. `.github/workflows/v3.7-production-pilot.yml`
   - future display name: `2 — Review One Opportunity End to End`
   - role: manual downstream review and summary generation.

`tests.yml` remains the canonical repository-wide regression gate and is not an operator workflow.

## 2. Global implementation rules

- Implement changes in separate reversible PRs by wave.
- Do not delete workflow history.
- Preserve artifact names and contents unless a dedicated compatibility decision is approved.
- Review branch-protection check names before changing displayed names or triggers.
- Retain path-scoped financial/evidence acceptance boundaries.
- Remove duplicated full `pytest -q` runs only after `tests.yml` is confirmed as a required check.
- No workflow may purchase, bid, contact, or invent financial values.

## 3. File-by-file future disposition

| # | Workflow | Current class | Current trigger/schedule | Proposed disposition | Exact future proposal | Dependency | Risk | Rollback | Verification | Wave |
|---:|---|---|---|---|---|---|---|---|---|---|
| 1 | `tests.yml` | ACTIVE_PRODUCTION_SUPPORT | PUSH/PR `main` | `KEEP_UNCHANGED` | Keep as canonical full regression gate and pytest-log artifact uploader. | Branch protection/check name review. | LOW | Revert commit. | Full suite passes; artifact present. | 1 |
| 2 | `discovery-v1-clothing-inventory.yml` | ACCEPTANCE_TEST | PR `main`; manual | `CONVERT_TO_MANUAL_OR_PATH_SCOPED_LATER` | Keep focused Discovery V1 tests; remove duplicate full regression after quality-gate confirmation; path-scope to discovery files. | `tests.yml` required check. | MEDIUM | Restore prior YAML/trigger. | Focused tests plus canonical regression pass. | 2 |
| 3 | `discovery-v1.1-live-search.yml` | ACCEPTANCE_TEST | PR `main`; manual | `CONVERT_TO_MANUAL_OR_PATH_SCOPED_LATER` | Path-scope to live-search/provider files; keep manual dispatch; remove duplicate full regression. | Provider test ownership. | MEDIUM | Restore prior YAML. | Adapter tests, YAML validation, manual dispatch. | 2 |
| 4 | `discovery-v1.2-live-pilot.yml` | PRIMARY_DISCOVERY_CANDIDATE | PR `main`; manual | `KEEP_OPERATOR_FACING_RENAME_LATER` | Rename display only to `1 — Discover Clothing Inventory Opportunities`; retain focused tests and manual live job; later path-scope PR trigger. | Branch-protection/check-name review; Brave secret. | LOW | Restore previous `name:`. | Manual dry run; phone/JSON artifacts preserved. | 1 |
| 5 | `scheduled-agent.yml` | ACTIVE_PRODUCTION_SUPPORT | manual; `17 */6 * * *` | `REVIEW_REQUIRED_BEFORE_CHANGE` | Retain until ODS ownership, email dependency, and state model are explicitly approved; do not combine with primary discovery yet. | SMTP secrets; ODS state cache; owner decision. | HIGH | Restore schedule/YAML or re-enable. | One dry run, email/state/artifact audit. | 3 |
| 6 | `daily-opportunity-pipeline.yml` | ACTIVE_PRODUCTION_SUPPORT | manual; `15 */6 * * *` | `REVIEW_REQUIRED_BEFORE_CHANGE` | Freeze as legacy source-first support; later decide manual-only or retained schedule after snapshot consumers are mapped. | Many generated data consumers; write permission; source secrets. | HIGH | Restore schedule and exact file SHA. | Snapshot diff, permissions/secrets audit, consumer checks. | 3 |
| 7 | `v2.6.6-live-dry-run.yml` | HISTORICAL_DIAGNOSTIC | manual | `ARCHIVE_OR_DISABLE_AFTER_VERIFICATION` | Preserve as manual during one release; later disable or move to documented diagnostics archive. | Production-readiness scripts and historical evidence. | MEDIUM | Re-enable/restore file. | Manual execution before archival; artifacts preserved. | 4 |
| 8 | `v2.7.1-real-dataset-validation.yml` | ACCEPTANCE_TEST | manual | `KEEP_NARROW_TRIGGERS_LATER` | Keep manual acceptance evidence; no automatic trigger required. | Dataset fixture ownership. | LOW | Restore prior trigger. | Manual run passes. | 2 |
| 9 | `v2.7.2.2-internal-score-audit.yml` | HISTORICAL_DIAGNOSTIC | manual | `ARCHIVE_OR_DISABLE_AFTER_VERIFICATION` | Preserve reference, run once, then disable/archive after V2.10 coverage confirmation. | V2.10 owner approval. | MEDIUM | Re-enable/restore. | Compare outputs with verified integration tests. | 4 |
| 10 | `v2.7.2.3-score-engine-trace-audit.yml` | HISTORICAL_DIAGNOSTIC | manual | `ARCHIVE_OR_DISABLE_AFTER_VERIFICATION` | Disable/archive after trace artifact is preserved and later score tests cover the contract. | Trace artifact retention. | MEDIUM | Re-enable/restore. | Last manual trace run and artifact checksum. | 4 |
| 11 | `v2.7.2.4.1-research-candidate-audit.yml` | HISTORICAL_DIAGNOSTIC | manual | `ARCHIVE_OR_DISABLE_AFTER_VERIFICATION` | Archive after candidate-selection behavior is covered by current external-research tests. | External research owner confirmation. | MEDIUM | Re-enable/restore. | Focused tests and last audit artifact. | 4 |
| 12 | `v2.7.2.4.2-bootstrap-pipeline-integration.yml` | HISTORICAL_DIAGNOSTIC | manual | `ARCHIVE_OR_DISABLE_AFTER_VERIFICATION` | Archive transitional bootstrap audit after V2.8–V2.10 boundaries pass. | V2.8–V2.10 checks. | MEDIUM | Re-enable/restore. | Boundary tests and preserved report. | 4 |
| 13 | `v2.7.2.4.3-external-evidence-execution-audit.yml` | HISTORICAL_DIAGNOSTIC | manual | `ARCHIVE_OR_DISABLE_AFTER_VERIFICATION` | Archive after V2.8 evidence workflows demonstrate equivalent coverage. | Evidence integration mapping. | MEDIUM | Re-enable/restore. | Coverage comparison and manual final run. | 4 |
| 14 | `v2.7.2.4.4-brave-transport-response-audit.yml` | HISTORICAL_DIAGNOSTIC | manual | `ARCHIVE_OR_DISABLE_AFTER_VERIFICATION` | Keep manual until provider troubleshooting guide exists; then disable/archive. | Brave provider troubleshooting ownership. | MEDIUM | Re-enable/restore. | Last API-safe diagnostic; no secret leakage. | 4 |
| 15 | `v2.7.2.4.5-brave-response-content-audit.yml` | HISTORICAL_DIAGNOSTIC | manual | `ARCHIVE_OR_DISABLE_AFTER_VERIFICATION` | Archive after V1.1 live-search parser tests and troubleshooting documentation cover it. | Parser tests and docs. | MEDIUM | Re-enable/restore. | Parser suite and preserved artifact. | 4 |
| 16 | `v2.7.2.4.7-comparable-acceptance-audit.yml` | HISTORICAL_DIAGNOSTIC | manual | `ARCHIVE_OR_DISABLE_AFTER_VERIFICATION` | Archive after V2.8.2/V2.8.2b acceptance equivalence is verified. | Comparable owners. | MEDIUM | Re-enable/restore. | Comparable suites pass; final audit retained. | 4 |
| 17 | `v2.7.2.5-external-financial-final-score.yml` | HISTORICAL_DIAGNOSTIC | manual | `ARCHIVE_OR_DISABLE_AFTER_VERIFICATION` | Archive after V2.10 verified financial gate is confirmed authoritative. | V2.10 owner approval. | MEDIUM | Re-enable/restore. | V2.10 tests plus result comparison. | 4 |
| 18 | `v2.8.1-external-market-comparables.yml` | ACTIVE_PRODUCTION_SUPPORT | manual with inputs | `KEEP_UNCHANGED` | Retain manual analysis capability and inputs; not operator discovery surface. | Brave key; analysis evidence contract. | MEDIUM | Revert file. | Manual small-limit dry run; artifacts/evidence valid. | 3 |
| 19 | `v2.8.2-comparable-evidence-integration.yml` | ACCEPTANCE_TEST | manual | `KEEP_NARROW_TRIGGERS_LATER` | Retain manual focused integration acceptance. | V2.8 contract. | LOW | Restore trigger. | Focused suite passes. | 2 |
| 20 | `v2.8.2b-comparable-evidence-e2e-acceptance.yml` | ACCEPTANCE_TEST | PR; manual | `CONVERT_TO_MANUAL_OR_PATH_SCOPED_LATER` | Path-scope to comparable evidence files and remove duplicate full regression. | `tests.yml`; branch protection. | MEDIUM | Restore prior PR trigger/full suite. | Focused E2E plus canonical regression. | 2 |
| 21 | `v2.9-auction-cost-logistics-e2e.yml` | ACCEPTANCE_TEST | path PR; manual | `KEEP_UNCHANGED` | Preserve path-scoped financial/logistics boundary and manual dispatch. | Financial evidence contract. | LOW | Revert file. | Focused test and YAML validation. | 2 |
| 22 | `v2.10-verified-financial-integration.yml` | ACCEPTANCE_TEST | path PR; manual | `KEEP_UNCHANGED` | Preserve authoritative verified-financial decision gate. | V2.8/V2.9 contracts. | LOW | Revert file. | Focused E2E and no unsupported decision behavior. | 2 |
| 23 | `v2.11-live-opportunity-validation.yml` | ACCEPTANCE_TEST | path PR; manual | `KEEP_UNCHANGED` | Preserve path-scoped validation/report boundary. | Live snapshot fixtures. | LOW | Revert file. | Focused test and report artifact. | 2 |
| 24 | `v30-multi-opportunity-ranking.yml` | ACCEPTANCE_TEST | PR; manual | `CONVERT_TO_MANUAL_OR_PATH_SCOPED_LATER` | Path-scope to ranking files; remove duplicate broad trigger where safe. | Ranking contract; required checks. | MEDIUM | Restore trigger. | Ranking E2E and canonical regression. | 2 |
| 25 | `v31-live-batch-validation.yml` | ACCEPTANCE_TEST | PR `main`; manual | `CONVERT_TO_MANUAL_OR_PATH_SCOPED_LATER` | Path-scope to batch-validation files; keep manual report generator. | Batch report consumers. | MEDIUM | Restore trigger. | Focused suite and report artifact. | 2 |
| 26 | `v3.2-continuous-opportunity-monitoring.yml` | ACTIVE_PRODUCTION_SUPPORT | PR; manual; `17 * * * *` | `KEEP_SCHEDULED_SUPPORT` | Retain hourly monitoring; remove PR trigger later if tests are separately covered; keep minute 17 only if V3.7 schedule is removed. | Seen-state cache; monitoring owner. | HIGH | Restore trigger/schedule. | State continuity, two-run duplicate protection, schedule review. | 3 |
| 27 | `v3.3-live-source-ingestion.yml` | ACTIVE_PRODUCTION_SUPPORT | PR; manual; `12 * * * *` | `REVIEW_REQUIRED_BEFORE_CHANGE` | Retain temporarily; determine whether Auksjonen-specific schedule remains needed under discovery-first architecture; likely manual or lower cadence later. | Source adapter consumers; state cache. | HIGH | Restore trigger/schedule. | Snapshot/state comparison and source-owner approval. | 3 |
| 28 | `v3.4-persistent-opportunity-state.yml` | ACCEPTANCE_TEST | PR; manual | `CONVERT_TO_MANUAL_OR_PATH_SCOPED_LATER` | Path-scope to persistent-state files; keep manual lifecycle acceptance. | State contract. | MEDIUM | Restore trigger. | Lifecycle test and state artifact integrity. | 2 |
| 29 | `v3.5-opportunity-alert-review-queue.yml` | ACCEPTANCE_TEST | PR; manual | `CONVERT_TO_MANUAL_OR_PATH_SCOPED_LATER` | Path-scope to alert/review-queue files; keep manual acceptance. | Review queue contract. | MEDIUM | Restore trigger. | Focused test; no duplicate alerts. | 2 |
| 30 | `v3.6-multi-source-ingestion.yml` | ACCEPTANCE_TEST | PR; manual | `CONVERT_TO_MANUAL_OR_PATH_SCOPED_LATER` | Path-scope to V3.6 files and remove duplicate full regression; retain as legacy-adapter acceptance. | Multi-source contract; `tests.yml`. | MEDIUM | Restore trigger/full suite. | Focused test plus canonical regression. | 2 |
| 31 | `v3.7-production-pilot.yml` | END_TO_END_REVIEW_CANDIDATE | PR; manual; `17 * * * *` | `KEEP_OPERATOR_FACING_RENAME_LATER` | Rename to `2 — Review One Opportunity End to End`; make manual operator workflow in a later PR; remove hourly schedule and broad PR trigger after monitoring dependencies are confirmed. | Branch protection/check name; V3.2/V3.5/V3.6 dependencies; artifact consumers. | HIGH | Restore prior name/triggers/schedule. | Manual E2E dry run, summary artifact, canonical regression, no automatic action. | 1 and 3 |

## 4. Schedule-collision proposal

Current relevant schedules:

- `v3.3-live-source-ingestion.yml`: minute 12 hourly.
- `v3.2-continuous-opportunity-monitoring.yml`: minute 17 hourly.
- `v3.7-production-pilot.yml`: minute 17 hourly.
- `daily-opportunity-pipeline.yml`: minute 15 every six hours.
- `scheduled-agent.yml`: minute 17 every six hours.

Proposed future target:

1. Remove the schedule from `v3.7-production-pilot.yml`; it becomes manual operator review.
2. Retain `v3.2` at minute 17 only after confirming it owns continuous monitoring.
3. Keep `v3.3` at minute 12 temporarily, pending source-adapter ownership review.
4. Do not change `scheduled-agent` or `daily-opportunity-pipeline` until email, state, snapshot consumers, and ownership are documented.
5. When six-hour schedules are retained, stagger them to avoid simultaneous starts; exact cron changes require a dedicated schedule PR.

## 5. Regression reduction proposal

- `tests.yml` remains the only canonical full `pytest -q` gate.
- Acceptance workflows should run focused tests only unless they protect a unique end-to-end boundary.
- Before removing any duplicate regression step:
  1. confirm `tests.yml` is required in branch protection;
  2. record old and new check names;
  3. run the focused workflow and `tests.yml` on the same commit;
  4. preserve failure artifacts and logs.

## 6. Reversible implementation waves

### Wave 1 — Operator naming only

- Rename the display names of the two operator candidates.
- Do not alter jobs, commands, permissions, triggers, or schedules.
- Review branch-protection check names first.

### Wave 2 — Acceptance trigger and regression cleanup

- Work in small PRs grouped by engine.
- Add path scopes or manual-only behavior.
- Remove duplicate full regressions only after the canonical gate is enforced.

### Wave 3 — Scheduled production support

- Handle one scheduled workflow per PR.
- First make V3.7 manual-only, resolving the minute-17 collision.
- Review V3.2, V3.3, scheduled-agent, and daily pipeline ownership separately.

### Wave 4 — Historical diagnostics

- Preserve the exact pre-change commit SHA and final artifacts.
- Disable or archive only after equivalent current tests are demonstrated.
- Never delete in the first cleanup pass.

## 7. Required verification bundle for every implementation PR

- YAML syntax validation.
- All repository tests passing through `tests.yml`.
- Focused workflow tests passing.
- Manual-dispatch availability confirmed where intended.
- Artifact names and contents compared before and after.
- Secrets and permissions reviewed.
- Branch-protection/check-name impact documented.
- Rollback commit or prior file SHA recorded.
- Confirmation that no automatic purchase, bid, or contact action exists.

## 8. Acceptance statement

This plan represents all 31 workflows and proposes future changes only. No workflow file, trigger, schedule, permission, secret, job, command, production code, financial formula, or opportunity domain is changed by this planning document.