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
- Wave 4A V2.6.6 historical diagnostic audit merged in PR #231.
- Wave 4B preservation-evidence definition merged in PR #232.
- Wave 4B initial evidence document merged in PR #233.
- Wave 4B final preservation run accepted with run ID `30175512518`, artifact ID `8624093715`, and artifact digest `sha256:57cc918d719a1aafa6720bff486035daf157a5e09e641f6e61214b6c8ff89420`.
- Wave 4C reversible disablement merged in PR #234; the V2.6.6 workflow remains preserved, manual-only, and reversible.
- Post-Wave 4C checkpoint merged in PR #235.
- Wave 4D V2.7.2.5 coverage audit merged in PR #237 as `NOT_READY`.
- Wave 4E V2.7.2.3 coverage audit merged in PR #239 as `NOT_READY`.
- Wave 4F V2.7.2.2 coverage audit merged in PR #241 as `NOT_READY`.
- Post-Wave 4F status reconciliation merged in PR #242.
- Wave 4G V2.7.2.4.1 task definition merged in PR #243; result merged in PR #244 as `NOT_READY`.
- Wave 4H V2.7.2.4.2 task definition merged in PR #245; result merged in PR #246 as `NOT_READY`.
- Wave 4I V2.7.2.4.3 task definition merged in PR #247; result merged in PR #248 as `NOT_READY`.
- Wave 4J V2.7.2.4.4 task definition merged in PR #249; result merged in PR #250 as `NOT_READY`.
- Wave 4K V2.7.2.4.5 task definition merged in PR #251; result merged in PR #253 as `NOT_READY`.
- Post-Wave 4K status reconciliation merged in PR #254.
- Wave 4L V2.7.2.4.7 task definition merged in PR #255; result merged in PR #256 as `NOT_READY`.
- Wave 4 Historical Diagnostics completed: all ten workflows classified as `HISTORICAL_DIAGNOSTIC` in the accepted cleanup plan have been handled.

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
- It remains available only for intentional manual execution.
- Wave 4D through Wave 4L each completed with result `NOT_READY`.
- None of those nine workflows is approved for a final preservation run, disablement, archival, relocation, rename, or deletion.
- All remain unchanged pending equivalent coverage.
- Deletion remains unapproved.
- Branch protection, external consumers, operator dependence, historical artifact links, repository-secret ownership, hosted-cache continuity, and external retention requirements remain `MANUAL_VERIFICATION_REQUIRED`.

## Current phase

**Phase:** Operator Workflow Simplification — Wave 4 Historical Diagnostics  
**Status:** `COMPLETE`

Wave 4 is formally closed because all ten historical-diagnostic workflows in the accepted cleanup plan have been handled.

## Current implementation checkpoint

```text
WORKFLOW_SIMPLIFICATION_POST_WAVE4_CHECKPOINT
```

Status: `NEXT`

Current task document:

```text
Not yet approved. The next change must inspect the accepted cleanup plan, the remaining unfinished Wave 2 and Wave 3 items, and the product blueprint, then select exactly one next task without modifying any workflow or production code.
```

## Accepted Wave 4 results

```text
Wave 4A–4C — V2.6.6 preserved and reversibly made non-routine
Wave 4D — NOT_READY
Wave 4E — NOT_READY
Wave 4F — NOT_READY
Wave 4G — NOT_READY
Wave 4H — NOT_READY
Wave 4I — NOT_READY
Wave 4J — NOT_READY
Wave 4K — NOT_READY
Wave 4L — NOT_READY
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

The post-Wave 4 checkpoint succeeds only when:

1. the accepted cleanup plan and product blueprint are inspected;
2. completed Wave 1 through Wave 4 work is excluded;
3. unfinished Wave 2 and Wave 3 items are identified;
4. exactly one next task is selected and documented;
5. no workflow or production-code change occurs during selection;
6. all unresolved external facts remain `MANUAL_VERIFICATION_REQUIRED`;
7. all repository checks pass for the checkpoint PR.

## Immediate next action

Execute the post-Wave 4 checkpoint only:

1. inspect `docs/WORKFLOW_CLEANUP_IMPLEMENTATION_PLAN_v1.0.md`;
2. inspect `docs/Opportunity_Discovery_Analysis_Blueprint_v2.0.md`;
3. exclude all work completed through Wave 4L;
4. identify unfinished Wave 2 and Wave 3 items;
5. select exactly one next task and create its task document;
6. do not modify or run any workflow in this task.
