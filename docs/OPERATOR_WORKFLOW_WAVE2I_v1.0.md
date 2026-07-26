# Operator Workflow Wave 2I — V3.4 Path Scoping Implementation v1.0

**Status:** APPROVED — NEXT IMPLEMENTATION TASK  
**Scope:** one workflow trigger change only

## Accepted prerequisite

Wave 2H completed with result:

```text
READY_FOR_PATH_SCOPING
```

The accepted audit established that `.github/workflows/v3.4-persistent-opportunity-state.yml` owns a focused V3.4 lifecycle acceptance boundary and does not run repository-wide regression.

## Objective

Replace the broad pull-request trigger in:

```text
.github/workflows/v3.4-persistent-opportunity-state.yml
```

with the approved owned-file path scope while preserving all existing manual, test, lifecycle, state-schema, monitoring-handoff, and safety behavior.

## Approved change

Keep:

```yaml
workflow_dispatch:
```

Retain the existing `branches: [ main ]` restriction and add exactly these pull-request paths:

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

## Behavior that must remain unchanged

- workflow display name;
- job identifier;
- Python version and environment;
- dependency installation;
- focused command `pytest tests/test_v34_persistent_opportunity_state.py -q`;
- lifecycle states `NEW`, `UPDATED`, `UNCHANGED`, `REMOVED`, and `ARCHIVED`;
- stable opportunity identity and fingerprint behavior;
- duplicate handling;
- archive-after-missing-runs behavior;
- V3.2 monitoring handoff;
- V3.1/V2.11/V3.0 downstream contracts;
- state schema and serialization;
- missing-evidence honesty;
- `automatic_purchase_decision: false` and all no-automatic-action safety contracts.

## Permitted repository changes

- `.github/workflows/v3.4-persistent-opportunity-state.yml` only;
- one focused documentation or verification update only if required by repository checks;
- project-status update after implementation is accepted.

## Prohibited changes

- Do not modify lifecycle, monitoring, validation, ranking, or financial source code.
- Do not modify tests, fixtures, generated state files, reports, artifacts, or caches.
- Do not modify any other workflow.
- Do not remove `workflow_dispatch`.
- Do not add schedules, permissions, secrets, environment variables, or artifact uploads.
- Do not add a broad repository regression step.
- Do not modify V2.8–V3.7 financial formulas, thresholds, or ordering.
- Do not add a new domain.
- Do not introduce automatic purchase, bid, contact, or financial decisions.

## Verification

The implementation PR must prove:

1. the YAML remains valid;
2. manual dispatch remains available;
3. the pull-request trigger remains limited to `main` and contains exactly the ten approved paths;
4. the focused V3.4 lifecycle test still passes;
5. lifecycle and monitoring-handoff behavior remain unchanged;
6. `.github/workflows/tests.yml` remains the repository-wide regression owner;
7. no file outside the approved implementation scope changes.

## External facts

Unless directly verified, keep these as:

```text
MANUAL_VERIFICATION_REQUIRED
```

- branch-protection required-check dependence;
- external consumers of the current workflow or check name;
- operator dependence on the broad pull-request trigger;
- hosted cache or external state continuity;
- historical artifact links and repository-level retention expectations.

## Rollback

Rollback is an exact revert of the implementation commit, restoring the prior `pull_request.branches: [ main ]` trigger without `paths` and restoring the exact pre-change workflow blob.

## Next decision

Only after this task document is accepted may a separate implementation PR modify the V3.4 workflow trigger.
