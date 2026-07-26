# Wave 2F — V3.1 Trigger and Regression Audit

**Result:** `READY_FOR_PATH_SCOPING`  
**Scope:** documentation-only prerequisite audit  
**Workflow:** `.github/workflows/v31-live-batch-validation.yml`

## Executive conclusion

The V3.1 live-batch validation workflow is ready for a separate path-scoping implementation.

The workflow currently retains `workflow_dispatch`, runs one focused V3.1 batch-validation test, generates one deterministic report, and uploads one report artifact. It does not run a broad repository-wide regression. Its tracked execution boundary can be mapped to a finite owned-file set.

No workflow or production code was modified or run during this audit.

## Current workflow contract

The workflow currently:

- triggers on every pull request to `main`;
- retains manual execution through `workflow_dispatch`;
- runs `pytest tests/test_v31_live_batch_validation.py -q`;
- runs `python scripts/run_v31_live_batch_validation.py`;
- prints `data/validation/v3.1-live-batch-validation.json` when present;
- uploads artifact `v3.1-live-batch-validation`;
- uses `if-no-files-found: warn`;
- has no schedule, secret, write permission, or broad `pytest -q` regression step.

## Dependency trace

### Focused test

`tests/test_v31_live_batch_validation.py`:

- reads `data/live_validation/v3.1-auksjonen-live-batch.json`;
- imports `build_batch_report` from `scripts/run_v31_live_batch_validation.py`;
- verifies that four opportunities are evaluated;
- verifies that incomplete evidence remains incomplete;
- verifies that no opportunity is promoted to financial review;
- verifies that `automatic_purchase_decision` remains `False`.

### V3.1 report generator

`scripts/run_v31_live_batch_validation.py`:

- reads the V3.1 live-batch fixture;
- imports `build_report` from `scripts/run_v211_live_opportunity_validation.py`;
- imports `rank_evaluated_opportunities` from `src/opportunity_engine/multi_opportunity_ranking.py`;
- evaluates each object in the batch through V2.11;
- passes the evaluations into V3.0 ranking;
- writes `data/validation/v3.1-live-batch-validation.json`;
- exits non-zero only when report errors exist.

### V2.11 dependency

`scripts/run_v211_live_opportunity_validation.py`:

- validates public HTTPS source traceability and positive asking price;
- preserves missing evidence rather than inventing values;
- imports `integrate_verified_financial_evidence` from `src/opportunity_engine/verified_financial_integration.py`;
- produces the V2.11 evaluation records consumed by V3.1.

### V3.0 dependency

`src/opportunity_engine/multi_opportunity_ranking.py`:

- filters already-evaluated records;
- excludes incomplete or unsafe records;
- ranks only `READY_FOR_FINANCIAL_REVIEW` records deterministically;
- preserves `automatic_purchase_decision: false`.

### Fixture dependency

`data/live_validation/v3.1-auksjonen-live-batch.json` is the deterministic batch consumed by both the focused test and the report generator. Changes to this fixture can alter counts, exclusions, status, and report output and therefore belong in the trigger scope.

## Proposed minimal pull-request path scope

```text
.github/workflows/v31-live-batch-validation.yml
tests/test_v31_live_batch_validation.py
scripts/run_v31_live_batch_validation.py
data/live_validation/v3.1-auksjonen-live-batch.json
scripts/run_v211_live_opportunity_validation.py
src/opportunity_engine/verified_financial_integration.py
src/opportunity_engine/multi_opportunity_ranking.py
```

This set covers the workflow definition, its focused test, its deterministic input fixture, its report generator, and every tracked non-standard-library execution dependency reached by the V3.1 acceptance path.

## Preserved behavior required in a future implementation

A separate implementation PR must preserve:

- `workflow_dispatch`;
- workflow display name and job identifier;
- Python version and environment;
- focused V3.1 test command;
- deterministic report generation;
- report path `data/validation/v3.1-live-batch-validation.json`;
- artifact name `v3.1-live-batch-validation`;
- `if-no-files-found: warn`;
- V2.11 validation behavior;
- V3.0 ranking behavior;
- missing-evidence honesty;
- `automatic_purchase_decision: false`.

## Canonical regression ownership

This workflow does not run the repository-wide regression suite. `.github/workflows/tests.yml` remains the canonical full-regression owner. The future path-scoping change must not add a duplicate broad regression step.

## External facts

The following remain:

```text
MANUAL_VERIFICATION_REQUIRED
```

- branch-protection required-check dependence;
- external consumers of the workflow or check name;
- operator dependence on the current broad trigger;
- historical artifact links;
- repository-level retention expectations.

These unresolved external facts do not prevent a reversible path-scoping implementation because the workflow name, job identifier, manual trigger, commands, and artifact contract can remain unchanged.

## Rollback

Rollback is an exact revert of the future implementation commit, restoring:

- `pull_request.branches: [ main ]` without `paths`;
- the exact pre-change workflow blob.

## Final recommendation

```text
READY_FOR_PATH_SCOPING
```

A separate task-definition and implementation PR may now replace the broad pull-request trigger with the seven-path owned-file scope documented above. No such workflow modification is included in this audit.