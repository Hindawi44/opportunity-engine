# Wave 2H — V3.4 Trigger and Regression Audit

**Result:** `READY_FOR_PATH_SCOPING`  
**Scope:** documentation-only prerequisite audit  
**Workflow:** `.github/workflows/v3.4-persistent-opportunity-state.yml`

## Executive conclusion

The V3.4 persistent-opportunity-state acceptance workflow has a finite, traceable repository-owned execution boundary and is ready for a separate trigger-only path-scoping implementation.

The workflow currently retains manual dispatch, runs one focused lifecycle acceptance test, uses no schedule, secret, permission elevation, cache, hosted state, report upload, or artifact upload, and does not run the repository-wide regression suite. No workflow or production code was modified or run during this audit.

## Current workflow contract

The workflow currently:

- triggers on every pull request to `main`;
- retains `workflow_dispatch`;
- uses Python 3.11 with repository `src` and root on `PYTHONPATH`;
- installs only `pytest`;
- runs `pytest tests/test_v34_persistent_opportunity_state.py -q`;
- has no schedule, cache, secret, write permission, report-generation step, state-file write step, or artifact upload step;
- fails when the focused pytest command fails.

## Dependency trace

### Focused test

`tests/test_v34_persistent_opportunity_state.py`:

- imports `build_lifecycle_report` from `scripts/run_v34_persistent_opportunity_state.py`;
- constructs all three lifecycle snapshots inline, so no tracked fixture file is read;
- verifies `NEW`, `UPDATED`, `UNCHANGED`, `REMOVED`, and `ARCHIVED` transitions;
- verifies actionable records are limited to `NEW` and `UPDATED` records;
- verifies the handoff count to V3.2 monitoring;
- verifies repeat processing produces no new actionable opportunities;
- verifies `automatic_purchase_decision` remains `False`;
- verifies a successful report has no errors and status `PASS`.

### V3.4 lifecycle report

`scripts/run_v34_persistent_opportunity_state.py`:

- imports `compare_snapshot` and `actionable_records` from `src/opportunity_engine/persistent_opportunity_state.py`;
- imports `build_monitoring_report` from `scripts/run_v32_continuous_opportunity_monitoring.py`;
- compares the supplied snapshot with explicit lifecycle and monitoring state payloads;
- creates a changed-record batch containing only actionable lifecycle records;
- passes that changed batch to V3.2 monitoring;
- produces the V3.4 report, next lifecycle state, and next monitoring state;
- preserves `automatic_purchase_decision: false`;
- when executed through its CLI, reads and writes JSON state/report paths and exits non-zero only when report errors exist.

The focused workflow does not execute this CLI; it calls `build_lifecycle_report` directly through the test. Therefore the default snapshot, state, and report files are runtime CLI defaults, not deterministic inputs required by the current workflow acceptance boundary.

### Persistent-state implementation

`src/opportunity_engine/persistent_opportunity_state.py`:

- derives stable opportunity identities from source and listing ID or URL;
- fingerprints the tracked business fields `title`, `description`, `location`, `auction_price_nok`, `listing_status`, and `url`;
- uses state schema version `3.4` with a JSON-serializable `records` mapping;
- ignores duplicate IDs within a snapshot;
- classifies records as `NEW`, `UPDATED`, or `UNCHANGED`;
- classifies missing records as `REMOVED` and then `ARCHIVED` after two missing runs by default;
- exposes only `NEW` and `UPDATED` records as actionable;
- uses only Python standard-library dependencies.

### V3.2 monitoring dependency

`scripts/run_v32_continuous_opportunity_monitoring.py` and `src/opportunity_engine/continuous_opportunity_monitoring.py`:

- fingerprint actionable records and suppress already-seen records;
- advance explicit monitoring state schema version `3.2`;
- reject records with insufficient stable identity rather than inventing identity;
- pass unseen records to the V3.1 batch-validation boundary;
- preserve `automatic_purchase_decision: false`.

### V3.1, V2.11, and V3.0 dependencies

The V3.2 handoff reaches:

- `scripts/run_v31_live_batch_validation.py`;
- `scripts/run_v211_live_opportunity_validation.py`;
- `src/opportunity_engine/verified_financial_integration.py`;
- `src/opportunity_engine/multi_opportunity_ranking.py`.

These files provide the downstream focused validation, verified-financial gate, and deterministic ranking behavior exercised when actionable records are present. They remain part of the tracked non-standard-library execution boundary even though the V3.4 test data intentionally remains evidence-incomplete.

## Coverage matrix

| Audit question | Finding |
|---|---|
| Current trigger | Broad `pull_request` to `main`, plus `workflow_dispatch` |
| Manual dispatch preservable | Yes |
| Focused command | `pytest tests/test_v34_persistent_opportunity_state.py -q` |
| Failure behavior | Pytest failure returns a non-zero workflow step |
| Lifecycle semantics | `NEW`, `UPDATED`, `UNCHANGED`, `REMOVED`, `ARCHIVED` |
| Duplicate behavior | Duplicate opportunity IDs in one snapshot are ignored after the first record |
| Update behavior | Changes to tracked business fields produce `UPDATED` and a changed-field list |
| Expiry/archive behavior | First missing run is `REMOVED`; second missing run is `ARCHIVED` by default |
| Review/actionable behavior | Only `NEW` and `UPDATED` records are passed downstream |
| State schema | JSON-serializable V3.4 lifecycle state plus V3.2 monitoring state |
| Deterministic fixture ownership | Inline test snapshots; no external fixture required by the workflow |
| Generated files/artifacts | None generated or uploaded by the current workflow |
| Cache/hosted continuity | None used by the current workflow |
| Secrets/permissions | None |
| Broad regression duplication | No; only one focused test runs |
| Canonical full regression | `.github/workflows/tests.yml` remains the owner |
| Trigger-only rollback | Exact revert restoring the current broad PR trigger |

## Proposed minimal pull-request path scope

```text
.github/workflows/v3.4-persistent-opportunity-state.yml
tests/test_v34_persistent_opportunity_state.py
scripts/run_v34_persistent_opportunity_state.py
src/opportunity_engine/persistent_opportunity_state.py
scripts/run_v32_continuous_opportunity_monitoring.py
src/opportunity_engine/continuous_opportunity_monitoring.py
scripts/run_v31_live_batch_validation.py
scripts/run_v211_live_opportunity_validation.py
src/opportunity_engine/verified_financial_integration.py
src/opportunity_engine/multi_opportunity_ranking.py
```

This set covers the workflow definition, focused test, V3.4 lifecycle implementation, V3.2 handoff, and every tracked non-standard-library dependency reached by that handoff.

Default CLI data paths are not included because the accepted workflow does not execute the V3.4 CLI and the focused test constructs deterministic snapshots and states inline. A future change that adds CLI execution or tracked fixture usage would require a separate scope review.

## Preserved behavior required in a future implementation

A separate implementation PR must preserve:

- `workflow_dispatch`;
- `branches: [ main ]`;
- workflow display name and job identifier;
- Python version, environment, and dependency installation;
- focused V3.4 test command;
- lifecycle-state schema and serialization;
- stable-ID and fingerprint behavior;
- all lifecycle transitions and archive threshold;
- duplicate suppression and actionable-record rules;
- V3.2 monitoring handoff behavior;
- V3.1, V2.11, and V3.0 downstream contracts;
- inline test data and assertions;
- no report or artifact contract added;
- missing-evidence honesty;
- `automatic_purchase_decision: false` and all no-automatic-action protections.

## Canonical regression ownership

This workflow does not execute `pytest -q` across the repository. `.github/workflows/tests.yml` remains the canonical full-regression owner. A future path-scoping implementation must not add a duplicate broad regression step.

## External facts

The following remain:

```text
MANUAL_VERIFICATION_REQUIRED
```

- branch-protection required-check dependence;
- external consumers of the workflow or check name;
- operator dependence on the broad pull-request trigger;
- historical check links or repository-level retention expectations.

Hosted cache or external-state continuity is not part of this workflow's tracked execution contract because the workflow does not restore, persist, or upload state.

## Rollback

Rollback is an exact revert of the future trigger-only implementation, restoring:

- `pull_request.branches: [ main ]` without `paths`;
- the exact pre-change workflow blob.

## Final classification

```text
READY_FOR_PATH_SCOPING
```

A separate task-definition PR and a later implementation PR may add the ten-path owned-file scope documented above. No workflow change is included in this audit.