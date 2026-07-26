# Wave 2L — V3.6 Trigger and Regression Audit Result

**Status:** COMPLETE  
**Classification:** `READY_FOR_PATH_SCOPING_AND_REGRESSION_DEDUPLICATION`

## Audited workflow

```text
.github/workflows/v3.6-multi-source-ingestion.yml
```

## Current trigger and execution behavior

The workflow currently:

- runs on every pull request targeting `main`;
- retains `workflow_dispatch`;
- installs `pytest`;
- runs the focused V3.6 acceptance command:

```text
pytest tests/test_v36_multi_source_ingestion.py -q
```

- then runs a second repository-wide command:

```text
pytest -q
```

The second command duplicates repository-wide regression coverage already owned by:

```text
.github/workflows/tests.yml
```

That canonical workflow runs on pull requests to `main`, installs the repository requirements, executes `pytest -q`, preserves the pytest output as an artifact, and fails the job when the regression suite fails.

## Focused acceptance dependency trace

The focused V3.6 test imports exactly these production modules:

```text
src/opportunity_engine/source_ingestion/auksjonen.py
src/opportunity_engine/source_ingestion/finn.py
src/opportunity_engine/source_ingestion/multisource.py
```

The focused test uses deterministic inline HTML and does not depend on tracked fixture files.

The finite V3.6 acceptance boundary is therefore:

```text
.github/workflows/v3.6-multi-source-ingestion.yml
tests/test_v36_multi_source_ingestion.py
src/opportunity_engine/source_ingestion/auksjonen.py
src/opportunity_engine/source_ingestion/finn.py
src/opportunity_engine/source_ingestion/multisource.py
```

## Behavior covered by the focused test

The focused acceptance test verifies:

- Auksjonen public-page parsing;
- FINN public-page parsing;
- rejection of non-public FINN URLs;
- rejection of listings with missing prices;
- deterministic snapshot construction;
- cross-source merging;
- duplicate detection;
- preservation of source traceability;
- positive asking-price requirements;
- unknown auction-fee evidence remaining `None`;
- `automatic_purchase_decision` remaining `False`.

## Trigger ownership conclusion

The V3.6 workflow has a finite, directly traceable acceptance boundary. It does not need to run for unrelated repository changes.

It is therefore safe to retain:

```yaml
pull_request:
  branches: [main]
workflow_dispatch:
```

and add exactly the five approved `pull_request.paths` entries listed above.

## Regression ownership conclusion

`.github/workflows/tests.yml` is the repository-wide regression owner because it:

- runs on pull requests to `main`;
- installs from `requirements.txt` rather than only installing `pytest`;
- executes the full `pytest -q` suite;
- captures pytest output as an artifact;
- propagates the test result as the job result.

The V3.6 workflow's second `pytest -q` step is duplicate coverage and is not required to preserve repository-wide regression ownership.

It is therefore safe to remove only this step from V3.6:

```yaml
- name: Run regression suite
  env:
    PYTHONPATH: src:.
  run: pytest -q
```

## Required behavior preservation

Any later implementation must preserve:

- workflow display name `V3.6 Multi-Source Ingestion Acceptance`;
- job identifier `multi-source-ingestion`;
- `workflow_dispatch`;
- pull requests targeting `main`;
- `ubuntu-latest`;
- Python 3.11;
- `pip install pytest`;
- focused command `pytest tests/test_v36_multi_source_ingestion.py -q`;
- existing `PYTHONPATH: src:.` behavior;
- Auksjonen and FINN public-source constraints;
- deterministic parsing and merging;
- duplicate detection behavior;
- missing-evidence honesty;
- source traceability;
- `automatic_purchase_decision: false`;
- no automatic purchase, bid, contact, payment, or financial decision.

## Permitted later implementation

A separately approved implementation PR may modify only:

```text
.github/workflows/v3.6-multi-source-ingestion.yml
```

It may:

1. add exactly the five approved `pull_request.paths` entries;
2. remove only the duplicate repository-wide regression step;
3. preserve all other trigger, job, environment, dependency, and focused-test behavior exactly.

## Prohibited changes

The implementation must not:

- modify production code;
- modify tests or fixtures;
- modify `.github/workflows/tests.yml`;
- modify any other workflow;
- remove `workflow_dispatch`;
- add schedules, secrets, permissions, caches, state persistence, report generation, or artifact uploads;
- change source parsing, deduplication, schema, thresholds, ordering, or financial behavior;
- add a new domain;
- add automatic purchase, bid, contact, payment, or financial decisions.

## External facts

The following remain:

```text
MANUAL_VERIFICATION_REQUIRED
```

- branch-protection dependence on the V3.6 check name;
- external consumers of the V3.6 workflow or check name;
- operator dependence on the broad trigger;
- historical links or external automation referencing this workflow.

These unknowns do not block the narrow trigger and regression-deduplication classification because the workflow display name and job identifier will remain unchanged.

## Final classification

```text
READY_FOR_PATH_SCOPING_AND_REGRESSION_DEDUPLICATION
```

No workflow modification is performed by this audit result.