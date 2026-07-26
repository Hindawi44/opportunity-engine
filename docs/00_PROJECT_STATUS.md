# Opportunity Engine — Project Status

**Last updated:** 2026-07-26  
**Status:** ACTIVE  
**Authoritative repository:** `Hindawi44/opportunity-engine`

## Session startup rule

Every development session must begin by reading, in this order:

1. `docs/00_PROJECT_STATUS.md`
2. `docs/Opportunity_Discovery_Analysis_Blueprint_v2.0.md`
3. `docs/REPOSITORY_ARCHITECTURE_AUDIT_v2.0.md`
4. The current-task document named below, when one is approved

The conversation is not the source of truth. The repository is the source of truth.

## Product principle

The project has two independent engines:

- **Discovery Engine:** discovers opportunities.
- **Analysis Engine:** analyzes confirmed opportunities.

Neither engine may perform the other engine's responsibility.

The bridge between them is the **Opportunity Dossier**, which gathers and organizes available evidence before financial analysis.

## Approved end-to-end path

```text
Opportunity Map
  -> Discovery Engine
  -> Opportunity Dossier
  -> Existing Analysis Engine
  -> Final Investment Report or Evidence-Required Outcome
```

## Current scope lock

The only validated domain is:

```text
CLOTHING_INVENTORY
```

Blocked domains remain:

- Wedding dresses
- Sewing equipment
- Fabrics
- Store fixtures
- Other opportunity domains

No new domain implementation is approved until the workflow-simplification checkpoint is completed and accepted.

## Completed and retained

- Blueprint v2.0 approved as strategic baseline.
- Repository Architecture Audit v2.0 merged.
- Existing Analysis Engine V2.8–V3.7 retained and frozen.
- Clothing Inventory selected as the reference MVP domain.
- Opportunity Dossier specification approved.
- All ten Clothing Inventory knowledge cards approved and merged.
- Controlled End-to-End Clothing Inventory checkpoint merged in PR #206.
- Real Clothing Inventory case validation merged in PR #208.
- Operator Workflow Inventory merged in PR #210.
- Operator Workflow Cleanup Implementation Plan merged in PR #212.
- Wave 1 operator display names merged in PR #214.
- Wave 2A prerequisite audit merged in PR #216.
- Wave 2B Discovery cleanup merged in PR #218.
- Wave 2C primary Discovery cleanup merged in PR #220.
- Wave 3A V3.7 schedule/dependency audit merged in PR #222.
- Wave 3B V3.7 manual-only conversion merged in PR #223.
- Wave 3C V3.2 monitoring ownership audit merged in PR #225.
- Wave 3D V3.2 pull-request trigger scoping merged in PR #227.
- Wave 3E V3.3 live-source ingestion ownership audit merged in PR #229.
- Wave 4 Historical Diagnostics completed through Wave 4L.
- Wave 4D through Wave 4L were accepted as `NOT_READY`; their workflows remain unchanged pending equivalent coverage.
- Wave 2D V3.0 ranking trigger audit merged in PR #259 as `READY_FOR_PATH_SCOPING`.
- Wave 2E V3.0 path-scoping implementation merged in PR #261 as `COMPLETE`.
- Wave 2F V3.1 trigger audit result merged in PR #264 as `READY_FOR_PATH_SCOPING`.
- Wave 2G V3.1 path-scoping implementation merged in PR #266 as `COMPLETE`.
- Wave 2H V3.4 trigger audit completed as `READY_FOR_PATH_SCOPING`.
- Wave 2I V3.4 path-scoping implementation merged in PR #271 as `COMPLETE`.
- Wave 2J V3.5 trigger audit merged in PR #272 as `READY_FOR_PATH_SCOPING`.
- Wave 2K V3.5 path-scoping implementation merged in PR #274 as `COMPLETE`.
- Wave 2L V3.6 trigger and regression audit task definition merged in PR #276.
- Wave 2L V3.6 audit result merged in PR #277 as `READY_FOR_PATH_SCOPING_AND_REGRESSION_DEDUPLICATION` with merge commit `ca2cc5e08a0b3442867707fff18d6320498da4ec`.
- Wave 2M V3.6 implementation task definition merged in PR #278.
- Wave 2M V3.6 path-scoping and regression-deduplication implementation merged in PR #279 as `COMPLETE` with merge commit `d7ae58be40165a56d21240ca6c2d16552f4e1e87`.

## Accepted Clothing Inventory result

The merged real case proves:

- one public Clothing Inventory candidate is preserved with source traceability;
- the candidate is classified using the approved Opportunity Map;
- a complete Opportunity Dossier is produced;
- unsupported values remain unknown rather than invented;
- the eligibility gate blocks incomplete evidence from financial analysis;
- the result reaches an honest `EVIDENCE_REQUIRED` outcome;
- no automatic purchase, bid, or contact action occurs;
- all repository checks pass.

## Accepted operator surface

```text
1 — Discover Clothing Inventory Opportunities
2 — Review One Opportunity End to End
```

The primary Discovery workflow is path-scoped and retains manual live execution. The end-to-end review workflow is manual-only and retains its focused test, deterministic summary, and artifact.

## Accepted monitoring conclusion

Tracked repository evidence establishes:

- V3.2 is the primary continuous-monitoring owner;
- its hourly schedule remains collision-free relative to V3.7;
- stateful duplicate protection works when prior state is supplied;
- V3.2 and V3.3 share a state-file path but use separate cache namespaces;
- V3.3 remains the temporary repository-owned Auksjonen ingestion and snapshot-refresh workflow;
- external consumers, branch protection, and hosted cache continuity remain `MANUAL_VERIFICATION_REQUIRED`.

## Current phase

**Phase:** Operator Workflow Simplification — unfinished trigger ownership  
**Status:** `ACTIVE`

Wave 2 trigger scoping through V3.6 is complete. The next lowest-risk unfinished item is the accepted Wave 3E recommendation to path-scope V3.3's broad pull-request trigger while preserving its schedule, manual dispatch, state paths, cache namespaces, reports, artifacts, and source behavior.

## Current implementation checkpoint

```text
WAVE3F_V33_PATH_SCOPING_TASK_DEFINITION
```

Status: `NEXT`

Current task document:

```text
Not yet approved. Create one planning-only task document for V3.3 pull-request path scoping. It must use the accepted Wave 3E dependency boundary, retain workflow_dispatch and the minute-12 hourly schedule, preserve the focused fixture-backed test, preserve snapshot/report/state/artifact paths and cache namespaces, and prohibit schedule, state, cache, source, report, artifact, and production-code changes.
```

## Accepted workflow-simplification results

```text
Wave 2B — COMPLETE
Wave 2C — COMPLETE
Wave 2D — READY_FOR_PATH_SCOPING
Wave 2E — COMPLETE
Wave 2F — READY_FOR_PATH_SCOPING
Wave 2G — COMPLETE
Wave 2H — READY_FOR_PATH_SCOPING
Wave 2I — COMPLETE
Wave 2J — READY_FOR_PATH_SCOPING
Wave 2K — COMPLETE
Wave 2L — READY_FOR_PATH_SCOPING_AND_REGRESSION_DEDUPLICATION
Wave 2M — COMPLETE
Wave 3A–3E — accepted as recorded above
Wave 4 Historical Diagnostics — COMPLETE
```

## Why Wave 3F is next

The accepted Wave 3E audit established that `.github/workflows/v3.3-live-source-ingestion.yml` still runs on every pull request to `main`, although its tracked execution boundary is finite.

The proposed dependency boundary is:

```text
.github/workflows/v3.3-live-source-ingestion.yml
scripts/run_v33_auksjonen_ingestion.py
src/opportunity_engine/source_ingestion/auksjonen.py
scripts/run_v32_continuous_opportunity_monitoring.py
tests/test_v33_live_source_ingestion.py
tests/fixtures/v33_auksjonen_page.html
```

Wave 3F must define a trigger-only implementation. It must not change:

- `workflow_dispatch`;
- schedule `12 * * * *`;
- cache keys or state ownership;
- snapshot, report, state, or artifact paths;
- Auksjonen source behavior;
- tests, fixtures, or production code.

## Non-negotiable rules

- Do not delete existing production code.
- Do not modify V2.8–V3.7 financial formulas unless a verified compatibility defect exists.
- Do not add a new domain.
- Do not invent missing values.
- Preserve source traceability.
- Do not make an automatic purchase, bid, contact, payment, or financial decision.
- Do not modify, run, disable, archive, rename, relocate, or delete a workflow until a separately approved task permits it.
- Select or change only one task in a single PR.
- Repository-setting facts and external consumers not visible in tracked files remain `MANUAL_VERIFICATION_REQUIRED`.

## Definition of current-task success

The Wave 3F task-definition checkpoint succeeds only when:

1. the accepted Wave 3E audit is used as the authority;
2. exactly one planning document is created;
3. the only later workflow change permitted is adding the six approved `pull_request.paths` entries;
4. `workflow_dispatch` and schedule `12 * * * *` are explicitly preserved;
5. fixture-backed PR execution and live manual/scheduled execution are preserved;
6. state paths, cache namespaces, reports, artifacts, source adapter behavior, tests, fixtures, and production code remain unchanged;
7. external-consumer and branch-protection facts remain `MANUAL_VERIFICATION_REQUIRED`;
8. all repository checks pass.

## Immediate next action

Execute Wave 3F task definition only:

1. create `docs/OPERATOR_WORKFLOW_WAVE3F_v1.0.md`;
2. record the six approved path entries from Wave 3E;
3. preserve manual and scheduled execution exactly;
4. prohibit schedule, cache, state, report, artifact, source, test, fixture, and production-code changes;
5. do not modify or run any workflow in this task.
