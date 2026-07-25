# Operator Workflow Wave 3A — End-to-End Review Schedule Audit v1.0

**Status:** APPROVED — NEXT AUDIT TASK  
**Scope:** prerequisite audit for one operator review workflow

## Accepted prerequisite

PR #220 completed Wave 2C successfully:

- the primary Discovery workflow received its approved pull-request path scope;
- manual dispatch, focused tests, the Brave pilot, reports, secrets, and artifacts were retained;
- the duplicated complete regression step was removed;
- `.github/workflows/tests.yml` remained unchanged and passed the complete regression suite.

## Objective

Before removing any automatic trigger from the end-to-end review workflow, audit the ownership and dependencies of:

```text
.github/workflows/v3.7-production-pilot.yml
```

This task is documentation and verification only. It does not authorize changing the workflow yet.

## Questions to resolve

1. Confirm every current trigger on `v3.7-production-pilot.yml`.
2. Confirm the exact hourly schedule and its collision with `v3.2-continuous-opportunity-monitoring.yml`.
3. Identify whether any external consumer depends on automatic V3.7 runs.
4. Map dependencies on V3.2 monitoring, V3.5 review queue, and V3.6 ingestion.
5. Identify all artifacts, summaries, state files, permissions, secrets, and generated outputs.
6. Confirm that manual dispatch can produce the complete end-to-end review result without an automatic schedule.
7. Define the exact rollback restoring the pre-change YAML blob and all triggers.

## Approved audit files

The audit may read:

```text
.github/workflows/v3.7-production-pilot.yml
.github/workflows/v3.2-continuous-opportunity-monitoring.yml
.github/workflows/v3.5-opportunity-alert-review-queue.yml
.github/workflows/v3.6-multi-source-ingestion.yml
.github/workflows/tests.yml
```

It may also inspect directly referenced scripts, tests, report paths, and tracked state contracts.

## Required output

Create a report that records:

- current V3.7 display name, jobs, triggers, schedule, commands, inputs, permissions, secrets, artifacts, and outputs;
- dependency status for V3.2, V3.5, and V3.6;
- automatic-run consumers as confirmed, unconfirmed, or `MANUAL_VERIFICATION_REQUIRED`;
- the exact future manual-only proposal;
- risk assessment;
- rollback procedure;
- verification bundle for the implementation PR.

## Safety constraints

Do not change:

- any workflow file;
- any trigger or schedule;
- workflow names or job identifiers;
- commands, permissions, secrets, artifacts, inputs, or environment variables;
- production code or financial formulas;
- domain scope;
- purchase, bid, or contact behavior.

## Definition of success

Wave 3A succeeds only when:

1. V3.7 ownership and dependencies are documented from tracked evidence;
2. unknown repository settings or external consumers are marked `MANUAL_VERIFICATION_REQUIRED`;
3. the minute-17 schedule collision is documented precisely;
4. manual-only implementation scope is defined without applying it;
5. rollback and verification requirements are explicit;
6. no workflow file changes;
7. all repository checks pass.

## Gate

Do not make V3.7 manual-only until this audit is merged and accepted. Do not change V3.2, V3.3, `scheduled-agent.yml`, or `daily-opportunity-pipeline.yml` in this task.
