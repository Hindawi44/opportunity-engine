# Operator Workflow Wave 1 v1.0

**Status:** APPROVED — NEXT IMPLEMENTATION TASK  
**Scope:** display-name-only workflow changes

## Objective

Make the GitHub Actions screen easier to use from a phone by giving the two approved operator workflows clear displayed names while preserving all behavior.

## Approved files

Only these workflow files may be edited:

```text
.github/workflows/discovery-v1.2-live-pilot.yml
.github/workflows/v3.7-production-pilot.yml
```

`tests.yml` remains the canonical full-regression quality gate and must remain behaviorally unchanged.

## Required displayed names

### Primary discovery workflow

File:

```text
.github/workflows/discovery-v1.2-live-pilot.yml
```

Required top-level displayed name:

```text
1 — Discover Clothing Inventory Opportunities
```

### End-to-end review workflow

File:

```text
.github/workflows/v3.7-production-pilot.yml
```

Required top-level displayed name:

```text
2 — Review One Opportunity End to End
```

## Scope lock

Wave 1 may change only the first top-level `name:` value in each approved file.

It must not change:

- workflow filenames;
- `on:` triggers;
- cron schedules;
- permissions;
- secrets;
- environment variables;
- jobs;
- steps;
- commands;
- artifact names or paths;
- production code;
- financial formulas;
- opportunity domains.

## Verification

Add a focused test that:

1. confirms both required displayed names;
2. confirms the two files still contain their pre-Wave-1 trigger blocks and core commands;
3. confirms `tests.yml` still exists and remains the canonical quality gate;
4. prevents accidental Wave 2 trigger or schedule changes from entering this PR.

All repository checks must pass.

## Rollback

Rollback is a direct revert of the Wave 1 implementation commit or restoration of the previous two workflow files from the pre-Wave-1 `main` commit.

Because Wave 1 changes only displayed names, no state, secret, schedule, artifact, or production behavior should require migration.

## Acceptance criteria

Wave 1 is complete only when:

- the two displayed names exactly match this document;
- no other workflow behavior changes;
- `tests.yml` remains unchanged;
- the focused verification test passes;
- all repository checks pass.

## Expansion gate

Wave 2 trigger and regression reduction must not begin until Wave 1 is merged and accepted.