# Operator Workflow Wave 2G — V3.1 Path Scoping Implementation v1.0

**Status:** APPROVED — NEXT IMPLEMENTATION TASK  
**Scope:** one workflow trigger change only

## Accepted prerequisite

Wave 2F completed with result:

```text
READY_FOR_PATH_SCOPING
```

The accepted audit established that `.github/workflows/v31-live-batch-validation.yml` owns a focused V3.1 live-batch acceptance boundary and does not run repository-wide regression.

## Objective

Replace the broad pull-request trigger in:

```text
.github/workflows/v31-live-batch-validation.yml
```

with the approved owned-file path scope while preserving all existing manual, test, report, artifact, validation, ranking, and safety behavior.

## Approved change

Keep:

```yaml
workflow_dispatch:
```

Retain the existing `branches: [ main ]` restriction and add exactly these pull-request paths:

```text
.github/workflows/v31-live-batch-validation.yml
tests/test_v31_live_batch_validation.py
scripts/run_v31_live_batch_validation.py
data/live_validation/v3.1-auksjonen-live-batch.json
scripts/run_v211_live_opportunity_validation.py
src/opportunity_engine/verified_financial_integration.py
src/opportunity_engine/multi_opportunity_ranking.py
```

## Behavior that must remain unchanged

- workflow display name;
- job identifier;
- Python version and environment;
- dependency installation;
- focused command `pytest tests/test_v31_live_batch_validation.py -q`;
- deterministic command `python scripts/run_v31_live_batch_validation.py`;
- report path `data/validation/v3.1-live-batch-validation.json`;
- artifact name `v3.1-live-batch-validation`;
- `if-no-files-found: warn`;
- V2.11 validation behavior;
- V3.0 ranking formulas, thresholds, ordering, and exclusion behavior;
- fixture contents;
- missing-evidence honesty;
- `automatic_purchase_decision: false` safety contract.

## Permitted repository changes

- `.github/workflows/v31-live-batch-validation.yml` only;
- one focused documentation or verification update only if required by repository checks;
- project-status update after implementation is accepted.

## Prohibited changes

- Do not modify V2.11 validation source, V3.0 ranking source, tests, fixture, or report generator.
- Do not modify any other workflow.
- Do not remove `workflow_dispatch`.
- Do not add schedules, permissions, secrets, or environment variables.
- Do not add a broad repository regression step.
- Do not modify V2.8–V3.7 financial formulas.
- Do not add a new domain.
- Do not introduce automatic purchase, bid, contact, or financial decisions.

## Verification

The implementation PR must prove:

1. the YAML remains valid;
2. manual dispatch remains available;
3. the pull-request trigger remains limited to `main` and contains exactly the seven approved paths;
4. the focused V3.1 batch-validation test still passes;
5. the deterministic report generator still succeeds;
6. the report and artifact contracts remain unchanged;
7. `.github/workflows/tests.yml` remains the repository-wide regression owner;
8. no file outside the approved implementation scope changes.

## External facts

Unless directly verified, keep these as:

```text
MANUAL_VERIFICATION_REQUIRED
```

- branch-protection required-check dependence;
- external consumers of the current workflow or check name;
- operator dependence on the broad pull-request trigger;
- historical artifact links and repository-level retention expectations.

## Rollback

Rollback is an exact revert of the implementation commit, restoring the prior `pull_request.branches: [ main ]` trigger without `paths` and restoring the exact pre-change workflow blob.

## Next decision

Only after this task document is accepted may a separate implementation PR modify the V3.1 workflow trigger.
