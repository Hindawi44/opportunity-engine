# Operator Workflow Wave 3C — V3.2 Continuous Monitoring Ownership Audit v1.0

**Status:** APPROVED — NEXT AUDIT TASK  
**Scope:** prerequisite audit for one scheduled production-support workflow

## Accepted prerequisite

PR #223 completed Wave 3B successfully:

- `.github/workflows/v3.7-production-pilot.yml` is now manual-only;
- the broad pull-request trigger and hourly minute-17 schedule were removed;
- the focused V3.7 acceptance test, summary generation, printed output, and artifact were retained;
- the duplicated complete regression step was removed;
- `.github/workflows/tests.yml` remained the canonical full-suite gate and passed.

## Objective

Before changing any trigger, schedule, cache, state, or artifact behavior in:

```text
.github/workflows/v3.2-continuous-opportunity-monitoring.yml
```

audit whether V3.2 is the authoritative continuous-monitoring owner and whether its hourly minute-17 schedule must remain.

This task is documentation and verification only. It does not authorize changing the workflow yet.

## Questions to resolve

1. Confirm every V3.2 trigger, schedule, job, command, environment variable, cache key, state path, report path, and artifact.
2. Confirm whether the minute-17 hourly schedule is now collision-free after Wave 3B.
3. Map the producers and consumers of `data/monitoring/v3.2-seen-state.json`.
4. Map the producers and consumers of `data/validation/v3.2-continuous-monitoring.json`.
5. Confirm duplicate-protection behavior across two consecutive runs.
6. Determine whether the broad pull-request trigger is needed or can later be removed/path-scoped.
7. Record branch-protection, ruleset, external consumer, and operator-routine facts as confirmed, unconfirmed, or `MANUAL_VERIFICATION_REQUIRED`.
8. Define exact future implementation scope, risk, rollback, and verification.

## Approved audit files

The audit may read:

```text
.github/workflows/v3.2-continuous-opportunity-monitoring.yml
.github/workflows/v3.7-production-pilot.yml
.github/workflows/v3.3-live-source-ingestion.yml
.github/workflows/tests.yml
scripts/run_v32_continuous_opportunity_monitoring.py
tests/test_v32_continuous_opportunity_monitoring.py
```

It may also inspect directly referenced monitoring-state contracts and report consumers.

## Required output

Create a report that records:

- current V3.2 identity and complete workflow contract;
- schedule ownership and collision status;
- cache/state continuity behavior;
- report and artifact consumers;
- exact future proposal for the PR trigger while retaining or changing the schedule only if evidence supports it;
- risk assessment;
- rollback procedure;
- verification bundle for any implementation PR.

## Safety constraints

Do not change:

- any workflow file;
- any trigger, schedule, cache, state, command, environment variable, report, or artifact;
- workflow names or job identifiers;
- production code or financial formulas;
- domain scope;
- purchase, bid, or contact behavior.

## Definition of success

Wave 3C succeeds only when:

1. V3.2 monitoring ownership is documented from tracked evidence;
2. state continuity and duplicate protection are mapped;
3. minute-17 collision status is documented precisely;
4. unknown repository settings or external consumers are marked `MANUAL_VERIFICATION_REQUIRED`;
5. future trigger/schedule scope is defined without applying it;
6. rollback and verification requirements are explicit;
7. no workflow file changes;
8. all repository checks pass.

## Gate

Do not change V3.2 triggers, schedule, cache, state, or artifact behavior until this audit is merged and accepted. Do not change V3.3, `scheduled-agent.yml`, or `daily-opportunity-pipeline.yml` in this task.
