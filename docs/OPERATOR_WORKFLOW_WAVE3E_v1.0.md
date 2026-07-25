# Operator Workflow Wave 3E — V3.3 Live Source Ingestion Ownership Audit v1.0

**Status:** APPROVED — NEXT AUDIT TASK  
**Scope:** documentation and verification only

## Accepted prerequisite

Wave 3D successfully scoped the V3.2 pull-request trigger while preserving its manual dispatch, hourly minute-17 schedule, state/cache contract, focused test, report, and artifact.

## Objective

Audit the ownership and production role of:

```text
.github/workflows/v3.3-live-source-ingestion.yml
```

before changing any trigger, schedule, state path, cache namespace, command, report, artifact, source adapter, or production behavior.

## Required audit questions

1. Does V3.3 remain the authoritative Auksjonen live-source ingestion and snapshot-refresh workflow?
2. Is its hourly schedule `12 * * * *` still operationally justified?
3. Which scripts, source adapters, fixtures, reports, and artifacts does it own?
4. How does its use of `data/monitoring/v3.2-seen-state.json` interact with V3.2?
5. Do the separate V3.2 and V3.3 cache namespaces permit divergent copies of one logical state?
6. Which tracked workflows or scripts consume V3.3 snapshots, reports, artifacts, or state?
7. Should its broad pull-request trigger remain, become path-scoped, or be removed in a later implementation PR?
8. What repository settings or external consumers remain `MANUAL_VERIFICATION_REQUIRED`?

## Permitted changes

Wave 3E may add only:

- one V3.3 ownership audit report under `docs/`;
- one focused verification test for that report.

## Prohibited changes

Do not modify:

- `.github/workflows/v3.3-live-source-ingestion.yml`;
- any trigger or schedule;
- state semantics, cache keys, source-adapter behavior, reports, or artifacts;
- V3.2, V3.7, `scheduled-agent.yml`, or `daily-opportunity-pipeline.yml`;
- production code or financial formulas;
- domain scope;
- purchase, bid, or contact behavior.

## Required evidence

The audit must inspect the V3.3 workflow and every directly referenced script, test, fixture, state path, report path, and artifact contract. It must distinguish tracked repository evidence from repository settings and external operational facts.

## Success criteria

Wave 3E succeeds only when:

1. V3.3 triggers, schedule, job, environment, commands, source ownership, state, cache, report, and artifact contracts are documented;
2. V3.2/V3.3 shared-state and separate-cache behavior is mapped precisely;
3. tracked and external consumers are classified honestly;
4. a future trigger/schedule proposal is documented without implementation;
5. risks, rollback, and verification requirements are explicit;
6. no workflow or production-code change occurs;
7. all repository checks pass.
