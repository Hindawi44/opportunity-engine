# Operator Workflow Wave 2E — V3.0 Ranking Path Scoping v1.0

**Status:** APPROVED — NEXT IMPLEMENTATION TASK  
**Scope:** one workflow trigger change only

## Accepted prerequisite

Wave 2D completed with result:

```text
READY_FOR_PATH_SCOPING
```

The accepted audit established that `.github/workflows/v30-multi-opportunity-ranking.yml` owns a focused V3.0 ranking acceptance boundary and does not run repository-wide regression.

## Objective

Replace the broad pull-request trigger in:

```text
.github/workflows/v30-multi-opportunity-ranking.yml
```

with the approved owned-file path scope while preserving all existing manual, test, report, and artifact behavior.

## Approved change

Keep:

```yaml
workflow_dispatch:
```

Change only the pull-request trigger to use these paths:

```text
.github/workflows/v30-multi-opportunity-ranking.yml
src/opportunity_engine/multi_opportunity_ranking.py
tests/test_v30_multi_opportunity_ranking_e2e.py
scripts/run_v30_multi_opportunity_ranking_acceptance.py
```

## Behavior that must remain unchanged

- workflow display name;
- job identifier;
- Python version and environment;
- dependency installation;
- focused command `pytest -q tests/test_v30_multi_opportunity_ranking_e2e.py`;
- deterministic acceptance-report generation;
- report path `data/validation/v3.0-multi-opportunity-ranking-acceptance.json`;
- artifact name `v3.0-multi-opportunity-ranking-acceptance`;
- `if-no-files-found: warn`;
- ranking formulas, thresholds, ordering, validation rules, and production code;
- `automatic_purchase_decision: false` safety contract.

## Permitted repository changes

- `.github/workflows/v30-multi-opportunity-ranking.yml` only;
- one focused documentation or verification update only if required by repository checks;
- project-status update after implementation is accepted.

## Prohibited changes

- Do not modify ranking source code, tests, or report generator.
- Do not change any other workflow.
- Do not remove `workflow_dispatch`.
- Do not add schedules, permissions, secrets, or environment variables.
- Do not modify V2.8–V3.7 financial formulas.
- Do not add a new domain.
- Do not introduce automatic purchase, bid, contact, or financial decisions.

## Verification

The implementation PR must prove:

1. the YAML remains valid;
2. manual dispatch remains available;
3. the pull-request trigger contains exactly the four approved paths;
4. the focused V3.0 ranking test still passes;
5. the deterministic acceptance report still succeeds;
6. the artifact contract remains unchanged;
7. `.github/workflows/tests.yml` remains the repository-wide regression owner;
8. no file outside the approved implementation scope changes.

## External facts

Unless directly verified, keep these as:

```text
MANUAL_VERIFICATION_REQUIRED
```

- branch-protection required-check dependence;
- external consumers of the current check name;
- operator dependence on the broad trigger;
- historical artifact links and retention expectations.

## Rollback

Rollback is an exact revert of the implementation commit, restoring the previous unscoped `pull_request` trigger and the exact pre-change workflow blob.

## Next decision

Only after this task document is accepted may a separate implementation PR modify the V3.0 workflow trigger.