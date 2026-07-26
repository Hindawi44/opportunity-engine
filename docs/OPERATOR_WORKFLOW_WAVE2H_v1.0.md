# Operator Workflow Wave 2H — V3.4 Trigger and Regression Audit v1.0

**Status:** APPROVED — NEXT AUDIT TASK  
**Scope:** documentation-only prerequisite audit  
**Workflow:** `.github/workflows/v3.4-persistent-opportunity-state.yml`

## Selection basis

The accepted cleanup plan classifies V3.4 Persistent Opportunity State as a Wave 2 acceptance workflow with a broad pull-request trigger and proposes conversion to a manual or path-scoped trigger later.

Wave 2 work completed through V3.1 is excluded. V3.4 is the next unfinished Wave 2 acceptance workflow in the cleanup-plan order. Wave 3 scheduled-production work remains separate and must not be mixed into this task.

## Objective

Determine whether the V3.4 persistent-state acceptance workflow has a finite, defensible owned-file boundary that permits a separate path-scoping implementation without changing state behavior, tests, fixtures, reports, artifacts, or production code.

The audit must return exactly one result:

```text
READY_FOR_PATH_SCOPING
```

or:

```text
NOT_READY
```

## Required inspection

Inspect and trace:

1. `.github/workflows/v3.4-persistent-opportunity-state.yml`;
2. `tests/test_v34_persistent_opportunity_state.py`;
3. every repository file imported, read, written, or otherwise required by that focused test and its implementation path;
4. canonical full-regression ownership in `.github/workflows/tests.yml`;
5. any state fixture, generated state file, report, artifact, cache, environment, permission, secret, or external dependency used by the acceptance boundary.

## Coverage matrix

The audit document must explicitly determine:

- current triggers and manual-dispatch preservation;
- focused test command and failure behavior;
- lifecycle operations and state-transition semantics;
- state schema and persistence format;
- fixture and deterministic-input ownership;
- generated state/report/artifact ownership, when present;
- duplicate, update, expiry, or review-state behavior covered by the test;
- all non-standard-library execution dependencies;
- whether the workflow duplicates the canonical repository-wide regression;
- rollback path for a future trigger-only implementation.

## READY criteria

Classify `READY_FOR_PATH_SCOPING` only when all of the following are true:

1. the focused V3.4 acceptance boundary is finite and traceable;
2. every tracked execution dependency can be listed as an owned path;
3. `workflow_dispatch` can remain unchanged;
4. a future change can add `pull_request.paths` without changing commands, state logic, schemas, tests, fixtures, outputs, artifacts, or production behavior;
5. `.github/workflows/tests.yml` remains the canonical full-regression owner;
6. rollback is an exact revert to the current broad pull-request trigger;
7. unresolved repository-setting and external-consumer facts remain `MANUAL_VERIFICATION_REQUIRED`.

## NOT_READY criteria

Classify `NOT_READY` when:

- execution dependencies cannot be bounded safely;
- state behavior depends on untracked or externally hosted continuity that cannot be separated from trigger ownership;
- the focused test does not cover the workflow contract adequately;
- a trigger-only change would require modifying state logic, fixtures, tests, permissions, caches, artifacts, or production code;
- equivalent regression ownership is unclear.

## Preserved behavior

No future implementation may change without separate approval:

- workflow display name or job identifier;
- Python version and environment;
- dependency installation;
- focused V3.4 test command;
- persistent-state schema or serialization;
- lifecycle transitions, duplicate protection, update behavior, expiry behavior, or review-state behavior;
- fixture contents;
- report or artifact contracts, if any;
- missing-evidence honesty;
- `automatic_purchase_decision: false` and all no-automatic-action safety contracts.

## Prohibited changes in this audit

- Do not modify or run any workflow.
- Do not modify tests, fixtures, state files, reports, artifacts, caches, or production code.
- Do not modify V2.8–V3.7 formulas, thresholds, ordering, validation, ranking, monitoring, ingestion, or review-queue behavior.
- Do not add a new domain.
- Do not select or implement another task.

## External facts

Unless directly verified in tracked repository evidence, record the following as:

```text
MANUAL_VERIFICATION_REQUIRED
```

- branch-protection required-check dependence;
- external consumers of the workflow or check name;
- operator dependence on the broad pull-request trigger;
- hosted cache or external state continuity;
- historical artifact links and retention expectations.

## Deliverable

Create one documentation-only audit result file for Wave 2H containing:

- dependency trace;
- coverage matrix;
- proposed minimal path scope when defensible;
- preserved-behavior contract;
- external-facts section;
- rollback statement;
- final classification: `READY_FOR_PATH_SCOPING` or `NOT_READY`.

No workflow implementation is permitted in the audit-result PR.