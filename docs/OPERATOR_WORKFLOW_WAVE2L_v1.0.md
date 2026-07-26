# Operator Workflow Wave 2L — V3.6 Trigger and Regression Audit Task v1.0

**Status:** APPROVED TASK DEFINITION CANDIDATE  
**Scope:** documentation-only audit planning

## Accepted starting point

Wave 2K completed in PR #274, and the post-Wave 2K status reconciliation was merged in PR #275. The single next task is the V3.6 trigger and regression ownership audit.

The workflow under review is:

```text
.github/workflows/v3.6-multi-source-ingestion.yml
```

## Objective

Perform a documentation-only audit that determines whether the V3.6 multi-source-ingestion acceptance workflow can later be simplified safely by:

1. replacing its broad pull-request trigger with an owned-file path scope; and
2. removing its duplicate repository-wide `pytest -q` step while preserving the focused V3.6 acceptance boundary and canonical regression ownership.

This task does not approve either implementation change. It only defines the evidence that a later audit must collect and the decisions that audit must produce.

## Current tracked workflow behavior

The audit must verify and document that the current workflow:

- triggers on every pull request to `main`;
- retains `workflow_dispatch`;
- uses `ubuntu-latest` and Python 3.11;
- installs `pytest`;
- runs the focused command:

```text
pytest tests/test_v36_multi_source_ingestion.py -q
```

- then runs the repository-wide command:

```text
pytest -q
```

- defines no schedule, secrets, permission elevation, cache, state persistence, report generation, or artifact upload.

## Required dependency trace

The audit must inspect at minimum:

```text
.github/workflows/v3.6-multi-source-ingestion.yml
tests/test_v36_multi_source_ingestion.py
src/opportunity_engine/source_ingestion/auksjonen.py
src/opportunity_engine/source_ingestion/finn.py
src/opportunity_engine/source_ingestion/multisource.py
.github/workflows/tests.yml
requirements.txt
```

Additional files may be included only when a direct tracked import, fixture, generated input, test configuration, or workflow contract proves they are part of the V3.6 execution boundary.

## Focused acceptance questions

The audit must document whether the focused V3.6 test independently covers:

- ingestion from Auksjonen.no public HTML;
- ingestion from FINN.no public HTML;
- rejection of non-public FINN URLs;
- rejection of listings without a verified positive asking price;
- stable opportunity identifiers;
- public HTTPS source traceability;
- preservation of missing cost evidence as `None`;
- deterministic source ordering;
- multi-source opportunity counts;
- cross-source duplicate detection;
- deterministic canonical retention;
- `automatic_purchase_decision: false`.

The audit must distinguish behavior explicitly asserted by the focused test from behavior that merely exists in production code.

## Regression-ownership questions

The audit must determine:

1. whether `.github/workflows/tests.yml` is the canonical repository-wide regression owner;
2. whether it runs on pull requests to `main` that also trigger V3.6;
3. whether removing `pytest -q` from the V3.6 workflow would reduce any unique tracked coverage;
4. whether dependency installation differences between the two workflows create a meaningful coverage difference;
5. whether branch-protection rules require the V3.6 job or its regression step specifically;
6. whether any external operator, integration, or historical process depends on the current workflow/check name or the second step.

Repository-setting and external-consumer facts not visible in tracked files must remain:

```text
MANUAL_VERIFICATION_REQUIRED
```

## Path-ownership questions

The audit must produce a proposed minimal pull-request `paths` list, or explain why no safe finite list exists.

The candidate list must be derived from the focused V3.6 execution boundary, not from the repository-wide regression suite. It must assess:

- the workflow file itself;
- the focused V3.6 test;
- all directly imported source-ingestion modules;
- any required fixtures or test configuration;
- shared modules whose changes can alter V3.6 behavior;
- whether `requirements.txt` belongs in the focused scope or remains covered only by the canonical regression workflow.

## Safety contracts that must remain unchanged

Any future implementation considered by the audit must preserve:

- `workflow_dispatch`;
- `branches: [main]`;
- workflow display name and job identifier unless separately approved;
- Python version and focused-test environment;
- public-source-only ingestion;
- no authentication bypass or private API use;
- no invention of missing prices, costs, comparables, or evidence;
- source URL traceability;
- positive asking-price validation;
- deterministic source and opportunity handling;
- duplicate detection and canonical retention semantics;
- missing-cost evidence honesty;
- `automatic_purchase_decision: false`;
- no automatic purchase, bid, contact, payment, or financial decision.

## Prohibited changes in this task

- Do not modify or run any workflow.
- Do not modify tests, production code, fixtures, requirements, configuration, reports, state files, artifacts, or caches.
- Do not remove the broad regression step yet.
- Do not add `paths` yet.
- Do not change source adapters, duplicate logic, schemas, thresholds, ordering, or financial behavior.
- Do not add a new source or domain.
- Do not make assumptions about branch protection or external consumers without direct evidence.

## Required audit output

The later Wave 2L audit must create exactly one audit-result document containing:

1. the current workflow contract;
2. a complete focused dependency trace;
3. a focused-test coverage matrix;
4. canonical regression ownership analysis;
5. a proposed minimal path scope, if safe;
6. unique-coverage analysis for the duplicate `pytest -q` step;
7. preserved behavior and rollback requirements;
8. external facts marked `MANUAL_VERIFICATION_REQUIRED` where appropriate;
9. one final classification:

```text
READY_FOR_PATH_SCOPING_AND_REGRESSION_REMOVAL
```

or

```text
READY_FOR_PATH_SCOPING_ONLY
```

or

```text
NOT_READY
```

## Definition of success

This task-definition checkpoint succeeds only when:

1. exactly one planning document is created;
2. no workflow or executable project file changes;
3. the future audit scope explicitly separates focused V3.6 ownership from repository-wide regression ownership;
4. no implementation is pre-approved before evidence is documented;
5. all repository checks pass.

## Next decision

Only after this task document is accepted may a separate Wave 2L audit PR create the audit-result document. No workflow modification is permitted until that audit is accepted.