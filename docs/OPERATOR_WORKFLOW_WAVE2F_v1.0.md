# Operator Workflow Wave 2F — V3.1 Trigger and Regression Audit v1.0

**Status:** APPROVED — NEXT OPERATOR TASK  
**Scope:** prerequisite audit and documentation only

## Post-Wave 2E checkpoint conclusion

Wave 2E completed the approved V3.0 path-scoping implementation. The accepted cleanup plan still contains unfinished Wave 2 and Wave 3 work.

The next bounded unfinished Wave 2 candidate is:

```text
.github/workflows/v31-live-batch-validation.yml
```

## Why this task is selected

The accepted cleanup plan proposes that the V3.1 live-batch validation workflow:

- retain manual dispatch;
- replace its broad pull-request trigger with an owned-file path scope;
- retain its focused batch-validation test and report generator;
- rely on `.github/workflows/tests.yml` for repository-wide regression;
- preserve its artifact behavior and no-invention safety contract.

The current workflow still triggers on every pull request to `main`. It runs one focused V3.1 test and one deterministic report generator. Trigger ownership is therefore the principal unresolved cleanup question.

This selection changes no Analysis Engine formula or production behavior. It concerns workflow ownership and CI scope only.

## Objective

Determine the exact safe pull-request path scope for:

```text
.github/workflows/v31-live-batch-validation.yml
```

before any workflow modification is proposed.

## Required audit work

1. Inspect `.github/workflows/v31-live-batch-validation.yml`.
2. Inspect `tests/test_v31_live_batch_validation.py`.
3. Inspect `scripts/run_v31_live_batch_validation.py`.
4. Trace all directly imported V2.11 and V3.0 modules, data fixtures, report dependencies, and generated-file contracts.
5. Identify the minimal owned-file set that should trigger the workflow on pull requests.
6. Verify that `workflow_dispatch` must remain unchanged.
7. Verify that the focused test and deterministic report generator remain necessary and unique.
8. Map artifact name, path, missing-file behavior, and any retention default.
9. Confirm that no repository-wide regression runs inside this workflow.
10. Record branch-protection or external-check-name dependence as `MANUAL_VERIFICATION_REQUIRED` unless directly verified.
11. Define rollback as restoring the exact pre-change workflow blob.
12. Produce exactly one implementation recommendation:
    - `READY_FOR_PATH_SCOPING`, or
    - `NOT_READY`.

## Required comparison boundaries

- current pull-request trigger limited only by `branches: [ main ]`;
- manual `workflow_dispatch` availability;
- V3.1 batch-report ownership;
- focused test ownership;
- V2.11 report-builder dependency;
- V3.0 ranking dependency;
- live-batch fixture ownership;
- artifact name `v3.1-live-batch-validation`;
- report path `data/validation/v3.1-live-batch-validation.json`;
- `if-no-files-found: warn` behavior;
- canonical regression ownership by `.github/workflows/tests.yml`;
- branch protection and external consumers.

## Permitted repository changes

- one focused audit-result document under `docs/`;
- one focused verification test for the document, only if required;
- a project-status update after the audit is accepted.

## Prohibited changes

- Do not modify or run `.github/workflows/v31-live-batch-validation.yml` in this audit task.
- Do not modify V2.11 validation logic, V3.0 ranking logic, formulas, thresholds, ordering, tests, fixtures, or production code.
- Do not modify any other workflow.
- Do not remove manual dispatch, focused testing, report generation, or artifact upload.
- Do not add a new domain.
- Do not make an automatic purchase, bid, contact, or financial decision.

## External facts

Unless directly verified, keep these as:

```text
MANUAL_VERIFICATION_REQUIRED
```

- branch-protection required-check dependence;
- external consumers of the workflow or check name;
- operator dependence on the broad trigger;
- historical artifact links and retention expectations.

## Success criteria

1. All V3.1 workflow dependencies are mapped accurately.
2. A minimal proposed pull-request path scope is documented, or the reason path scoping is unsafe is documented.
3. Manual dispatch, focused testing, report generation, artifact behavior, and `automatic_purchase_decision: false` remain protected.
4. Exactly one result is assigned: `READY_FOR_PATH_SCOPING` or `NOT_READY`.
5. No workflow or production-code change occurs.
6. All repository checks pass for the audit PR.

## Next decision

Only after this audit is accepted may a separate implementation task modify the V3.1 workflow trigger.
