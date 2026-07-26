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
- V2.6.6 final preservation evidence retained with run ID `30175512518`, artifact ID `8624093715`, and digest `sha256:57cc918d719a1aafa6720bff486035daf157a5e09e641f6e61214b6c8ff89420`.
- Wave 4D through Wave 4L were accepted as `NOT_READY`; their workflows remain unchanged pending equivalent coverage.
- Wave 2D V3.0 ranking trigger audit merged in PR #259 as `READY_FOR_PATH_SCOPING`.
- Wave 2E V3.0 path-scoping implementation merged in PR #261 as `COMPLETE`.
- Wave 2F V3.1 trigger audit task definition merged in PR #263.
- Wave 2F V3.1 trigger audit result merged in PR #264 as `READY_FOR_PATH_SCOPING`.
- Wave 2G V3.1 path-scoping task definition merged in PR #265.
- Wave 2G V3.1 path-scoping implementation merged in PR #266 as `COMPLETE`.
- Wave 2H V3.4 trigger audit completed as `READY_FOR_PATH_SCOPING`.
- Wave 2I V3.4 path-scoping implementation merged in PR #271 as `COMPLETE` with merge commit `4545239e5e7016b7a2f5d356cf54a672b706091e`.

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

## Accepted historical-diagnostic conclusion

- V2.6.6 is a preserved, manual-only historical production-readiness diagnostic.
- Its final manual run evidence and artifact metadata are preserved.
- Wave 4D through Wave 4L each completed with result `NOT_READY`.
- None of those nine workflows is approved for disablement, archival, relocation, rename, or deletion.
- All remain unchanged pending equivalent coverage.
- Deletion remains unapproved.
- Repository-setting and external-consumer facts remain `MANUAL_VERIFICATION_REQUIRED`.

## Current phase

**Phase:** Operator Workflow Simplification — Wave 2 Trigger Ownership  
**Status:** `ACTIVE`

Wave 4 is formally closed. Post-Wave 4 work continues the unfinished Wave 2 trigger-ownership sequence.

## Current implementation checkpoint

```text
WAVE2J_V35_TRIGGER_AUDIT_TASK_DEFINITION
```

Status: `NEXT`

Current task document:

```text
Not yet approved. Create one planning-only task document for the V3.5 alert/review-queue workflow trigger audit. The task must inspect ownership, focused-test coverage, manual-dispatch requirements, downstream review-queue contracts, duplicate-alert safety, branch-protection/check-name dependence, and external consumers before any workflow modification.
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
Wave 3A–3E — accepted as recorded above
Wave 4 Historical Diagnostics — COMPLETE
```

## Non-negotiable rules

- Do not delete existing production code.
- Do not modify V2.8–V3.7 financial formulas unless a verified compatibility defect exists.
- Do not add a new domain.
- Do not invent missing values.
- Preserve source traceability.
- Do not make an automatic purchase, bid, or contact decision.
- Do not modify, run, disable, archive, rename, relocate, or delete a workflow until a separately approved task permits it.
- Select or change only one task in a single PR.
- Repository-setting facts and external consumers not visible in tracked files remain `MANUAL_VERIFICATION_REQUIRED`.

## Definition of current-task success

The Wave 2J task-definition checkpoint succeeds only when:

1. `.github/workflows/v3.5-opportunity-alert-review-queue.yml` and its owned files are inspected;
2. focused-test ownership and manual-dispatch requirements are documented;
3. review-queue, duplicate-alert, and downstream contract behavior is preserved;
4. branch-protection/check-name and external-consumer facts remain `MANUAL_VERIFICATION_REQUIRED` unless directly verified;
5. exactly one audit task document is created;
6. no workflow, production-code, test, fixture, state, report, artifact, or cache file changes;
7. all repository checks pass for the task-definition PR.

## Immediate next action

Execute Wave 2J task definition only:

1. inspect `.github/workflows/v3.5-opportunity-alert-review-queue.yml`;
2. inspect its focused test, runner, source module, and downstream contracts;
3. document trigger ownership, path-scope candidates, manual behavior, and safety constraints;
4. create exactly one Wave 2J audit task document;
5. do not modify or run any workflow in this task.
