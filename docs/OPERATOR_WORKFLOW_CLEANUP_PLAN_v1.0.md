# Operator Workflow Cleanup Plan v1.0

**Status:** APPROVED — NEXT IMPLEMENTATION TASK  
**Scope:** planning only; no `.github/workflows/` changes

## Objective

Convert the accepted 31-workflow inventory into a safe, explicit implementation plan for a later cleanup PR that simplifies the GitHub Actions view for a phone operator.

This task plans changes. It does not apply them.

## Governing evidence

Use these documents as the authoritative basis:

1. `docs/00_PROJECT_STATUS.md`
2. `docs/Opportunity_Discovery_Analysis_Blueprint_v2.0.md`
3. `docs/REPOSITORY_ARCHITECTURE_AUDIT_v2.0.md`
4. `docs/WORKFLOW_INVENTORY_REPORT_v1.0.md`

## Accepted operator candidates

### Primary discovery candidate

```text
.github/workflows/discovery-v1.2-live-pilot.yml
```

Target operator role:

- manually start scenario-driven Clothing Inventory discovery;
- use the existing Discovery Engine and Brave provider;
- generate a phone-readable text report and JSON artifact;
- never calculate unsupported financial values or make an automatic purchase/contact decision.

### End-to-end review candidate

```text
.github/workflows/v3.7-production-pilot.yml
```

Target operator role:

- manually run the latest downstream production-pilot review path;
- generate one review summary artifact;
- retain Analysis Engine and review-queue ownership;
- avoid acting as an automatic purchase, bid, or contact system.

### Canonical quality gate

```text
.github/workflows/tests.yml
```

Target repository role:

- remain the canonical full regression gate;
- preserve the uploaded pytest log;
- avoid duplicating the complete regression suite inside every acceptance workflow when a later implementation safely narrows those workflows.

## Scope lock

This task must not:

- edit any workflow file;
- delete, move, disable, or rename a workflow;
- change a trigger, cron expression, permission, secret, job, or command;
- change production code;
- modify V2.8–V3.7 financial formulas;
- add a new domain or source adapter;
- create automatic purchase, bid, or contact behavior.

## Required plan output

Create:

```text
docs/WORKFLOW_CLEANUP_IMPLEMENTATION_PLAN_v1.0.md
```

The document must represent all 31 workflow files and provide the following fields for each:

- file path;
- current classification;
- current triggers and schedule;
- proposed future disposition;
- exact future change, if any;
- reason;
- dependency;
- risk level;
- rollback method;
- verification requirement;
- recommended implementation PR or wave.

## Allowed proposed dispositions

Use exactly one primary proposed disposition per workflow:

1. `KEEP_UNCHANGED`
2. `KEEP_OPERATOR_FACING_RENAME_LATER`
3. `KEEP_NARROW_TRIGGERS_LATER`
4. `KEEP_SCHEDULED_SUPPORT`
5. `CONVERT_TO_MANUAL_OR_PATH_SCOPED_LATER`
6. `ARCHIVE_OR_DISABLE_AFTER_VERIFICATION`
7. `REVIEW_REQUIRED_BEFORE_CHANGE`

These are proposals only and do not authorize an implementation change.

## Required implementation waves

The plan must organize future work into separate, reversible waves.

### Wave 1 — Operator surface

Plan only:

- clarify the operator-facing display name of `discovery-v1.2-live-pilot.yml`;
- clarify the operator-facing display name of `v3.7-production-pilot.yml`;
- keep `tests.yml` clearly identifiable as the quality gate.

### Wave 2 — Trigger and regression reduction

Plan only:

- retain `tests.yml` as the full regression workflow;
- identify acceptance workflows that can later use focused tests without repeating `pytest -q`;
- preserve path-scoped acceptance boundaries where they protect financial or evidence contracts;
- define how branch protection remains safe.

### Wave 3 — Scheduled production support

Plan only:

Review ownership and cadence for:

- `scheduled-agent.yml`;
- `daily-opportunity-pipeline.yml`;
- `v3.2-continuous-opportunity-monitoring.yml`;
- `v3.3-live-source-ingestion.yml`;
- `v3.7-production-pilot.yml`.

The plan must resolve or explicitly retain schedule overlaps, including the collision at minute 17.

### Wave 4 — Historical diagnostics

Plan only:

- preserve historical traceability;
- define whether each diagnostic should remain manual, move to a documented archive location, or be disabled later;
- require a successful regression run and a rollback reference before any implementation.

## Risk levels

Use one of:

- `LOW` — display name or documentation-only future change;
- `MEDIUM` — trigger narrowing, schedule adjustment, or acceptance workflow behavior;
- `HIGH` — disabling, moving, or changing a workflow that writes state, sends email, uses secrets, or supports production monitoring.

## Verification requirements

The future implementation plan must require, as applicable:

- all repository tests passing;
- workflow YAML syntax validation;
- confirmation that all intended manual workflows remain dispatchable;
- artifact-name and artifact-content preservation;
- secret and permission review;
- schedule-collision review;
- branch-protection/check-name review;
- one manual discovery dry run;
- one manual end-to-end review dry run;
- confirmation that no automatic purchase, bid, or contact behavior exists.

## Rollback requirements

Every future change must be reversible through one of:

- reverting the implementation commit;
- restoring the previous workflow file from its exact commit SHA;
- restoring the previous trigger or schedule;
- re-enabling the previous workflow after documented verification.

No workflow may be deleted without a prior preserved reference and a separate explicit approval.

## Acceptance criteria

The planning task passes only when:

- all 31 workflows appear in the implementation plan;
- every workflow has one allowed proposed disposition;
- every proposed future change includes risk, dependency, rollback, and verification;
- the operator surface identifies exactly one discovery workflow and one review workflow;
- `tests.yml` remains the proposed canonical full-regression gate;
- schedule overlaps receive an explicit proposal;
- historical diagnostics are not guessed away or deleted;
- no `.github/workflows/` file is modified;
- all repository checks pass.

## Expansion gate

No workflow cleanup implementation and no new opportunity domain may begin until the cleanup implementation plan is accepted and merged.
