# Operator Workflow Wave 3F — V3.3 Path-Scoping Task v1.0

**Status:** TASK DEFINITION  
**Classification:** PLANNING ONLY  
**Target workflow:** `.github/workflows/v3.3-live-source-ingestion.yml`

## Objective

Define one later, reversible implementation PR that path-scopes only the pull-request trigger of V3.3 while preserving its manual and scheduled live-source behavior exactly.

No workflow modification is authorized by this document.

## Accepted basis

Wave 3E established that V3.3 is the repository-owned Auksjonen ingestion and snapshot-refresh workflow and recommended path-scoping its broad pull-request trigger while retaining:

- `workflow_dispatch`;
- schedule `12 * * * *`;
- deterministic fixture-backed execution for pull requests;
- live Auksjonen execution for manual and scheduled runs;
- current state, cache, report, artifact, snapshot, and monitoring contracts.

## Permitted later implementation

A separately approved implementation PR may modify only:

```text
.github/workflows/v3.3-live-source-ingestion.yml
```

It may add `pull_request.paths` using exactly this six-file dependency boundary:

```text
.github/workflows/v3.3-live-source-ingestion.yml
scripts/run_v33_auksjonen_ingestion.py
src/opportunity_engine/source_ingestion/auksjonen.py
scripts/run_v32_continuous_opportunity_monitoring.py
tests/test_v33_live_source_ingestion.py
tests/fixtures/v33_auksjonen_page.html
```

## Required behavior preservation

The later implementation must preserve exactly:

- workflow display name `V3.3 Live Source Ingestion & Snapshot Refresh`;
- job identifier `auksjonen-source-ingestion`;
- pull requests targeting `main`;
- `workflow_dispatch`;
- schedule `12 * * * *`;
- `ubuntu-latest`;
- Python 3.11;
- current dependency installation;
- focused command `pytest tests/test_v33_live_source_ingestion.py -q`;
- fixture-backed PR command using `tests/fixtures/v33_auksjonen_page.html`;
- live-source execution for manual and scheduled runs;
- current Auksjonen public-source restrictions;
- source traceability and positive-price requirements;
- duplicate detection and monitoring handoff;
- failure behavior that does not overwrite valid snapshot, state, or reports;
- `automatic_purchase_decision: false`.

## State, cache, report, and artifact lock

The later implementation must not change:

```text
data/live_validation/v3.3-auksjonen-live-snapshot.json
data/monitoring/v3.2-seen-state.json
data/validation/v3.3-source-ingestion.json
data/validation/v3.2-continuous-monitoring.json
```

It must also preserve:

- existing V3.3 cache keys and restore behavior;
- artifact name `v3.3-auksjonen-source-ingestion`;
- artifact contents and upload conditions;
- the V3.4 dependency on the V3.3 snapshot path.

## Prohibited changes

The Wave 3F implementation must not:

- change or remove the hourly schedule;
- remove `workflow_dispatch`;
- modify production code, tests, or fixtures;
- modify V3.2 or V3.4 workflows;
- unify, rename, or migrate cache namespaces;
- change state ownership or synchronization;
- change snapshot, report, or artifact paths or schemas;
- add a source, domain, schedule, secret, permission, formula, threshold, ranking rule, purchase action, bid action, contact action, payment action, or financial decision;
- address unrelated cleanup.

## Verification requirements

The later implementation PR must prove:

1. exactly one workflow file changed;
2. exactly six approved `paths` entries were added under `pull_request`;
3. `branches: [main]`, `workflow_dispatch`, and schedule `12 * * * *` remain;
4. fixture-backed PR execution remains unchanged;
5. manual and scheduled live execution remains unchanged;
6. focused V3.3 tests pass;
7. repository-required checks pass;
8. no state, cache, report, artifact, source, or financial behavior changed.

## Rollback

Rollback is a direct revert of the later implementation commit, restoring the previous V3.3 workflow trigger. No data migration or state repair should be required because this task permits no state, cache, report, artifact, or schema changes.

## External facts

The following remain:

```text
MANUAL_VERIFICATION_REQUIRED
```

- branch-protection dependence on the V3.3 check name;
- external consumers of reports or artifacts;
- hosted-cache continuity;
- operator dependence on broad pull-request execution;
- source cadence and external service expectations.

These unknowns do not authorize any schedule, cache, state, report, artifact, or source change.

## Success criteria for this task-definition PR

This planning checkpoint succeeds only when:

- this is the only created or modified file;
- no workflow is modified or run;
- the six-file boundary and preservation constraints are explicit;
- all repository checks pass;
- the next task is one separate V3.3 trigger-only implementation PR.
