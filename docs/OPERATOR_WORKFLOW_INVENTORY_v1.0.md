# Operator Workflow Inventory v1.0

**Status:** APPROVED — NEXT IMPLEMENTATION TASK  
**Scope:** `.github/workflows/` inventory and classification only

## Objective

Create a complete, non-destructive inventory of the repository's GitHub Actions workflows so the project can later expose a simpler phone-friendly operator journey.

This task implements the approved operator-simplification planning phase from `docs/REPOSITORY_ARCHITECTURE_AUDIT_v2.0.md`.

## Why this task is next

The controlled Clothing Inventory checkpoint and the first real public case have both been merged and accepted. The repository now proves the safe path from Discovery to an honest `EVIDENCE_REQUIRED` outcome.

The architecture audit identifies the next approved phase as operator simplification:

```text
identify one primary discovery workflow
  -> identify one end-to-end review workflow
  -> classify all remaining workflows
  -> prepare a separate cleanup proposal
```

## Scope lock

This task covers workflow inventory and documentation only.

It must not:

- delete workflow files;
- move workflow files;
- disable workflows;
- rename workflows;
- change workflow triggers;
- change production code;
- modify V2.8–V3.7 formulas;
- add a new opportunity domain;
- add a new source adapter;
- create automatic purchase, bid, or contact actions.

## Required inventory fields

For every file under `.github/workflows/`, record:

- file path;
- displayed workflow name;
- trigger types;
- manual-dispatch availability;
- scheduled cadence when present;
- primary responsibility;
- owning engine or layer;
- production or acceptance role;
- overlap with other workflows;
- recommended classification;
- evidence or reason for the classification.

## Required classifications

Use exactly one primary classification per workflow:

1. `PRIMARY_DISCOVERY_CANDIDATE`
2. `END_TO_END_REVIEW_CANDIDATE`
3. `ACTIVE_PRODUCTION_SUPPORT`
4. `ACCEPTANCE_TEST`
5. `HISTORICAL_DIAGNOSTIC`
6. `UNCERTAIN_REVIEW_REQUIRED`

Classification is documentation only. It does not authorize a workflow change.

## Ownership labels

Use one of:

- `DISCOVERY_ENGINE`
- `OPPORTUNITY_DOSSIER_BRIDGE`
- `ANALYSIS_ENGINE`
- `MONITORING_AND_STATE`
- `REVIEW_QUEUE`
- `REPOSITORY_QUALITY`
- `MIXED_OR_UNCLEAR`

## Required outputs

### 1. Workflow inventory document

Create:

```text
docs/WORKFLOW_INVENTORY_REPORT_v1.0.md
```

The report must include all workflow files, not a sample.

### 2. Executive findings

The report must identify:

- the strongest candidate for the primary discovery workflow;
- the strongest candidate for the end-to-end review workflow;
- workflows that are clearly acceptance-only;
- workflows that appear diagnostic or historical;
- duplicated or overlapping responsibilities;
- workflows whose role cannot be determined safely.

### 3. Non-destructive next-step proposal

The report must propose a separate future PR that may simplify the Actions view.

The proposal must clearly state that no deletion, disabling, moving, renaming, or trigger changes were performed by this inventory task.

## Acceptance criteria

The task passes only when:

- every `.github/workflows/` file is represented;
- every workflow has its triggers documented;
- every workflow has an ownership label;
- every workflow has one primary classification;
- classifications are supported by repository evidence;
- candidate operator workflows are identified;
- overlaps are documented;
- uncertain cases remain uncertain rather than guessed;
- no workflow file is modified;
- all repository checks remain passing.

## Implementation sequence

1. Enumerate `.github/workflows/` completely.
2. Read each workflow file.
3. Extract name, triggers, jobs, and invoked commands.
4. Map commands to repository capabilities and ownership boundaries.
5. Classify each workflow.
6. Identify overlap and duplication.
7. Select candidate operator workflows.
8. Write `docs/WORKFLOW_INVENTORY_REPORT_v1.0.md`.
9. Add a verification test or script only if required to prove inventory completeness; do not alter workflow behavior.
10. Update `docs/00_PROJECT_STATUS.md` only after the inventory is verified and merged.

## Expansion gate

No new domain implementation or destructive workflow cleanup may begin until this inventory is accepted and merged.
