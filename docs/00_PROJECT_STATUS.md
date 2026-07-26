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
- Wave 2L V3.6 audit result merged in PR #277 as `READY_FOR_PATH_SCOPING_AND_REGRESSION_DEDUPLICATION`.
- Wave 2M V3.6 path-scoping and regression-deduplication implementation merged in PR #279 as `COMPLETE`.
- Wave 3F V3.3 path-scoping task definition merged in PR #281.
- Wave 3F V3.3 path-scoping implementation merged in PR #282 as `COMPLETE` with merge commit `1db30b72b57461010242f0802999c9dc00e63f4f`.
- The Wave 3E contract test was updated in PR #282 to validate the accepted six-file V3.3 path boundary rather than prohibit `paths:`.

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
- V3.3 now has a six-file pull-request path boundary while retaining manual and scheduled execution;
- external consumers, branch protection, and hosted cache continuity remain `MANUAL_VERIFICATION_REQUIRED`.

## Current phase

**Phase:** Workflow Simplification Checkpoint Review  
**Status:** `ACTIVE`

The planned low-risk workflow cleanup sequence is now implemented through V3.6 and V3.3. The project must not automatically continue into another workflow wave. It must first decide whether the simplification checkpoint is sufficient to return to the approved Clothing Inventory end-to-end product path.

## Current implementation checkpoint

```text
WORKFLOW_SIMPLIFICATION_CHECKPOINT_REVIEW_TASK_DEFINITION
```

Status: `NEXT`

Current task document:

```text
Not yet approved. Create one planning-only checkpoint-review document that reconciles completed Wave 1, Wave 2, Wave 3, and Wave 4 results; identifies only genuine remaining blockers; decides whether workflow simplification is ACCEPTED or NOT_READY; and, if accepted, selects one product-facing Clothing Inventory task rather than another cleanup wave.
```

## Accepted workflow-simplification results

```text
Wave 1 — COMPLETE
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
Wave 3A–3F — accepted as recorded above
Wave 4 Historical Diagnostics — COMPLETE with Wave 4D–4L retained as NOT_READY
```

## Why checkpoint review is next

The project has now completed the intended low-risk changes that reduce unnecessary workflow execution while preserving:

- the two-workflow operator surface;
- canonical regression ownership in `tests.yml`;
- manual execution paths;
- required schedules;
- source traceability;
- persistent-state and duplicate-protection contracts;
- evidence-first behavior;
- `automatic_purchase_decision: false`.

Remaining unknowns such as external consumers, branch-protection configuration, and hosted-cache continuity are already classified as `MANUAL_VERIFICATION_REQUIRED`. They must not automatically cause an endless sequence of speculative cleanup work.

The checkpoint review must distinguish:

1. a proven blocker to the Clothing Inventory end-to-end path;
2. a documented operational unknown that can remain monitored;
3. optional future cleanup that must not delay product validation.

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
- Do not create another cleanup wave unless the checkpoint review identifies a concrete blocker with repository evidence.

## Definition of current-task success

The checkpoint-review task definition succeeds only when:

1. exactly one planning-only task document is created;
2. completed Wave 1–4 results are reconciled against the cleanup plan;
3. remaining items are classified as blocker, monitored unknown, or optional future cleanup;
4. the document defines objective criteria for `SIMPLIFICATION_ACCEPTED` versus `NOT_READY`;
5. no workflow, production code, test, fixture, state, cache, report, artifact, source, domain, or financial behavior is modified;
6. if simplification is accepted, the next task must return to one Clothing Inventory product-facing end-to-end objective;
7. all repository checks pass.

## Immediate next action

Execute the checkpoint-review task definition only:

1. create `docs/WORKFLOW_SIMPLIFICATION_CHECKPOINT_REVIEW_TASK_v1.0.md`;
2. reconcile the accepted workflow inventory and Waves 1–4;
3. define blocker-versus-monitoring classification rules;
4. define the evidence required to accept the checkpoint;
5. prohibit workflow modifications in the task-definition PR;
6. identify no more than one subsequent task.