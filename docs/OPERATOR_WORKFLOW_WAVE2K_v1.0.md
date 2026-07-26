# Operator Workflow Wave 2K — V3.5 Path Scoping Implementation v1.0

**Status:** APPROVED — NEXT IMPLEMENTATION TASK  
**Scope:** one workflow trigger change only

## Accepted prerequisite

Wave 2J completed in PR #272 with result:

```text
READY_FOR_PATH_SCOPING
```

The accepted audit established that `.github/workflows/v3.5-opportunity-alert-review-queue.yml` owns a finite four-file V3.5 acceptance boundary. The workflow retains manual dispatch, runs one focused test, does not run repository-wide regression, and does not generate, persist, cache, or upload state or artifacts.

## Objective

Replace the broad pull-request trigger in:

```text
.github/workflows/v3.5-opportunity-alert-review-queue.yml
```

with the approved owned-file path scope while preserving all existing manual, focused-test, eligibility, duplicate-alert, material-update, queue-status, ordering, state-schema, and safety behavior.

## Approved change

Keep:

```yaml
workflow_dispatch:
```

Retain the existing `branches: [ main ]` restriction and add exactly these pull-request paths:

```text
.github/workflows/v3.5-opportunity-alert-review-queue.yml
tests/test_v35_opportunity_alert_review_queue.py
scripts/run_v35_opportunity_alert_review_queue.py
src/opportunity_engine/opportunity_review_queue.py
```

## Behavior that must remain unchanged

- workflow display name `V3.5 Opportunity Alert & Review Queue`;
- job identifier `alert-review-queue`;
- runner `ubuntu-latest`;
- Python 3.11 and the existing `PYTHONPATH` environment;
- dependency installation `pip install pytest`;
- focused command `pytest tests/test_v35_opportunity_alert_review_queue.py -q`;
- eligibility gate `READY_FOR_FINANCIAL_REVIEW`;
- requirement for a stable `opportunity_id`;
- minimum three verified comparables;
- minimum six verified cost components;
- numeric expected-profit and ROI requirements;
- fingerprint fields and duplicate-alert suppression;
- alert reasons `NEWLY_ELIGIBLE` and `MATERIAL_UPDATE`;
- queue statuses `PENDING_REVIEW`, `SNOOZED`, `IGNORED`, and `REVIEWED`;
- preservation of valid human-review status during later updates;
- priority thresholds and deterministic queue ordering;
- V3.5 state schema and JSON serialization;
- inline test candidates and state payloads;
- missing-evidence honesty;
- `automatic_purchase_decision: false` and all no-automatic-action contracts.

## Permitted repository changes

- `.github/workflows/v3.5-opportunity-alert-review-queue.yml` only;
- one focused documentation or verification update only if required by repository checks;
- project-status update after the implementation is accepted.

## Prohibited changes

- Do not modify `tests/test_v35_opportunity_alert_review_queue.py`.
- Do not modify `scripts/run_v35_opportunity_alert_review_queue.py`.
- Do not modify `src/opportunity_engine/opportunity_review_queue.py`.
- Do not modify fixtures, generated reports, state files, artifacts, or caches.
- Do not modify any other workflow.
- Do not remove `workflow_dispatch`.
- Do not add schedules, permissions, secrets, environment variables, caches, report steps, state-persistence steps, or artifact uploads.
- Do not add a broad repository regression step.
- Do not change eligibility thresholds, fingerprint fields, priority thresholds, queue ordering, or queue-status semantics.
- Do not modify V2.8–V3.7 financial formulas, thresholds, or ranking behavior.
- Do not add a new domain.
- Do not introduce automatic purchase, bid, contact, payment, or financial decisions.

## Verification

The implementation PR must prove:

1. the YAML remains valid;
2. manual dispatch remains available;
3. the pull-request trigger remains limited to `main` and contains exactly the four approved paths;
4. the focused V3.5 acceptance test still passes;
5. eligibility, duplicate-alert, material-update, queue-status, deterministic-ordering, and state-schema behavior remain unchanged;
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
- external consumers of the CLI report or state paths;
- historical check links and repository-level retention expectations.

## Rollback

Rollback is an exact revert of the implementation commit, restoring the prior `pull_request.branches: [ main ]` trigger without `paths` and restoring the exact pre-change workflow blob.

## Definition of success

Wave 2K is complete only when:

1. exactly the four approved paths are added under `pull_request.paths`;
2. `workflow_dispatch` and `branches: [ main ]` remain unchanged;
3. no job, command, environment, dependency, test, production-code, state, report, artifact, cache, formula, threshold, ordering, or domain changes;
4. all required checks pass;
5. the implementation PR is accepted and merged;
6. the project-status file is updated in a separate accepted status step.

## Next decision

Only after this task document is accepted may a separate implementation PR modify the V3.5 workflow trigger.