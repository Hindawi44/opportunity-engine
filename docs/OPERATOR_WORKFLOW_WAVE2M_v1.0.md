# Operator Workflow Wave 2M — V3.6 Path Scoping and Regression Deduplication v1.0

**Status:** APPROVED — NEXT IMPLEMENTATION TASK  
**Scope:** one workflow file only

## Accepted prerequisite

Wave 2L completed with classification:

```text
READY_FOR_PATH_SCOPING_AND_REGRESSION_DEDUPLICATION
```

The accepted audit established that V3.6 has a finite five-file acceptance boundary and that `.github/workflows/tests.yml` already owns repository-wide regression coverage.

## Objective

Modify only:

```text
.github/workflows/v3.6-multi-source-ingestion.yml
```

The later implementation PR must:

1. retain `workflow_dispatch`;
2. retain pull requests targeting `main`;
3. add exactly the five approved `pull_request.paths` entries;
4. retain the focused V3.6 acceptance test unchanged;
5. remove only the duplicate repository-wide regression step from V3.6.

## Approved pull-request paths

```text
.github/workflows/v3.6-multi-source-ingestion.yml
tests/test_v36_multi_source_ingestion.py
src/opportunity_engine/source_ingestion/auksjonen.py
src/opportunity_engine/source_ingestion/finn.py
src/opportunity_engine/source_ingestion/multisource.py
```

## Exact regression step approved for removal

```yaml
- name: Run regression suite
  env:
    PYTHONPATH: src:.
  run: pytest -q
```

Repository-wide regression remains owned by:

```text
.github/workflows/tests.yml
```

## Behavior that must remain unchanged

- workflow name `V3.6 Multi-Source Ingestion Acceptance`;
- job identifier `multi-source-ingestion`;
- runner `ubuntu-latest`;
- Python 3.11;
- dependency installation `pip install pytest`;
- focused command `pytest tests/test_v36_multi_source_ingestion.py -q`;
- focused-step `PYTHONPATH: src:.`;
- Auksjonen and FINN public-source restrictions;
- deterministic parsing, snapshot construction, merging, and duplicate detection;
- source traceability and missing-evidence honesty;
- `automatic_purchase_decision: false`;
- no automatic purchase, bid, contact, payment, or financial decision.

## Permitted repository changes

The implementation PR may change only:

```text
.github/workflows/v3.6-multi-source-ingestion.yml
```

A later, separate accepted status PR may update:

```text
docs/00_PROJECT_STATUS.md
```

## Prohibited changes

- Do not modify production code.
- Do not modify tests or fixtures.
- Do not modify `.github/workflows/tests.yml`.
- Do not modify any other workflow.
- Do not remove `workflow_dispatch`.
- Do not change the workflow name or job identifier.
- Do not add schedules, permissions, secrets, caches, state persistence, reports, or artifact uploads.
- Do not change source parsing, deduplication, schema, formulas, thresholds, ordering, or domain behavior.
- Do not add a new domain.
- Do not introduce automatic purchase, bid, contact, payment, or financial decisions.

## Verification requirements

The implementation PR must prove:

1. the YAML remains valid;
2. `workflow_dispatch` remains present;
3. `pull_request.branches` remains limited to `main`;
4. `pull_request.paths` contains exactly the five approved entries;
5. the focused V3.6 acceptance step remains unchanged;
6. the duplicate V3.6 `pytest -q` regression step is removed;
7. `.github/workflows/tests.yml` remains unchanged and continues to own full regression;
8. no file outside the approved implementation scope changes;
9. all required repository checks pass.

## External facts

Unless directly verified, retain as:

```text
MANUAL_VERIFICATION_REQUIRED
```

- branch-protection dependence on the V3.6 check name;
- external consumers of the workflow or check name;
- operator dependence on the former broad trigger;
- historical links or external automation referencing this workflow.

The implementation preserves the workflow name and job identifier, reducing compatibility risk.

## Rollback

Rollback is an exact revert of the implementation commit, restoring the broad pull-request trigger and the removed V3.6 regression step.

## Definition of success

Wave 2M is complete only when:

1. exactly the five approved paths are added;
2. only the duplicate regression step is removed;
3. all preserved behavior remains unchanged;
4. all checks pass;
5. the implementation PR is accepted and merged;
6. project status is reconciled separately.

## Next decision

Only after this planning document is accepted may a separate implementation PR modify the V3.6 workflow.