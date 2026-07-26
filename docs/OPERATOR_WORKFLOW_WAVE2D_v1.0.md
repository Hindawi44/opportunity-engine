# Operator Workflow Wave 2D — V3.0 Ranking Trigger and Regression Audit v1.0

**Status:** APPROVED — NEXT OPERATOR TASK  
**Scope:** prerequisite audit and documentation only

## Post-Wave 4 checkpoint conclusion

Wave 4 is complete. The accepted cleanup plan still contains unfinished Wave 2 and Wave 3 work.

The first two Discovery acceptance workflows and the primary Discovery workflow were already handled in Wave 2B and Wave 2C. The V2.8.2B comparable-evidence workflow is already path-scoped, retains manual dispatch, and runs a focused test plus deterministic acceptance report, so it is not selected for another cleanup task.

The next bounded unfinished Wave 2 candidate is:

```text
.github/workflows/v30-multi-opportunity-ranking.yml
```

## Why this task is selected

The accepted cleanup plan proposes that the V3.0 ranking acceptance workflow:

- retain manual dispatch;
- replace its broad pull-request trigger with an owned-file path scope;
- retain its focused ranking test and acceptance report;
- rely on `tests.yml` for repository-wide regression;
- preserve artifact behavior and the ranking contract.

The current workflow still has an unscoped `pull_request` trigger. It already runs a focused test rather than a duplicate full `pytest -q`, so trigger ownership is the principal unresolved cleanup question.

This selection is consistent with the product blueprint because it changes no ranking formula or Analysis Engine production code. It concerns workflow ownership and CI scope only.

## Objective

Determine the exact safe pull-request path scope for `.github/workflows/v30-multi-opportunity-ranking.yml` before any workflow modification is proposed.

## Required audit work

1. Inspect `.github/workflows/v30-multi-opportunity-ranking.yml`.
2. Inspect `tests/test_v30_multi_opportunity_ranking_e2e.py`.
3. Inspect `scripts/run_v30_multi_opportunity_ranking_acceptance.py`.
4. Trace all imported ranking modules, contracts, fixtures, and report dependencies.
5. Identify the minimal owned-file set that should trigger the workflow on pull requests.
6. Verify that `workflow_dispatch` must remain unchanged.
7. Verify that the focused ranking test and deterministic acceptance report remain unique and necessary.
8. Map artifact name, path, missing-file behavior, and any retention default.
9. Confirm that no broad repository regression runs inside this workflow.
10. Record branch-protection or external-check-name dependence as `MANUAL_VERIFICATION_REQUIRED` unless directly verified.
11. Define rollback as restoring the exact pre-change workflow blob.
12. Produce exactly one implementation recommendation:
   - `READY_FOR_PATH_SCOPING`, or
   - `NOT_READY`.

## Required comparison boundaries

- current unscoped `pull_request` trigger;
- manual `workflow_dispatch` availability;
- ranking contract ownership;
- focused E2E test ownership;
- deterministic report generator ownership;
- imported source modules and fixtures;
- artifact name `v3.0-multi-opportunity-ranking-acceptance`;
- report path `data/validation/v3.0-multi-opportunity-ranking-acceptance.json`;
- `if-no-files-found: warn` behavior;
- canonical regression ownership by `.github/workflows/tests.yml`;
- branch-protection and external consumers.

## Permitted repository changes

- one focused audit-result document under `docs/`;
- one focused verification test for the document, if necessary;
- a project-status update after the audit is accepted.

## Prohibited changes

- Do not modify or run `.github/workflows/v30-multi-opportunity-ranking.yml` in the audit task.
- Do not modify ranking formulas, scoring logic, thresholds, ordering, or production code.
- Do not modify any other workflow.
- Do not remove manual dispatch, focused tests, report generation, or artifact upload.
- Do not add a new domain.
- Do not make an automatic purchase, bid, contact, or financial decision.

## External facts

Unless directly verified, keep these as:

```text
MANUAL_VERIFICATION_REQUIRED
```

- branch-protection required-check dependence;
- external consumers of the check name;
- operator dependence on the current broad trigger;
- historical artifact links.

## Success criteria

1. All ranking workflow dependencies are mapped accurately.
2. A minimal proposed pull-request path scope is documented, or the reason path scoping is unsafe is documented.
3. Manual dispatch, focused testing, report generation, and artifact behavior are preserved.
4. Exactly one result is assigned: `READY_FOR_PATH_SCOPING` or `NOT_READY`.
5. No workflow or production-code change occurs.
6. All repository checks pass for the audit PR.

## Next decision

Only after this audit is accepted may a separate implementation task modify the V3.0 workflow trigger.