# Opportunity Engine — Project Status

**Last updated:** 2026-07-27  
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
  -> Verified Market Comparables
  -> Verified Acquisition Costs
  -> Existing Analysis Engine
  -> Opportunity Score
  -> Decision Intelligence
  -> Final Investment Report or Evidence-Required Outcome
```

Canonical investment decisions are:

```text
BUY_REVIEW / WATCH / REJECT
```

`BUY_REVIEW` is a human-review state only. It is never an automatic purchase instruction.

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

No new domain implementation is approved until the Clothing Inventory live operator path is integrated and repeated live-product validation is accepted.

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
- Wave 3F V3.3 path-scoping implementation merged in PR #282 as `COMPLETE`.
- Post-Wave 3F status reconciliation merged in PR #283.
- Workflow-simplification checkpoint task definition merged in PR #284.
- Workflow-simplification checkpoint result merged in PR #285 as `SIMPLIFICATION_ACCEPTED`.
- Clothing Inventory single-case execution task definition merged in PR #286.

## Accepted Clothing Inventory product implementation

The product-facing implementation sequence is complete through live no-candidate handling:

- PR #287 added the deterministic Clothing Inventory single-case end-to-end runner and focused tests.
- PR #288 added live Auksjonen Clothing Inventory candidate ingestion.
- PR #289 integrated verified market comparables through the existing V2.8 contract.
- PR #290 integrated verified acquisition-cost evidence through the existing V2.9/V2.10 contracts.
- PR #291 connected the single case to the existing opportunity scoring and canonical decision-intelligence policy.
- PR #292 stored and executed the first public Clothing Inventory investment report; its honest decision was `WATCH` because acquisition-cost evidence remained incomplete.
- PR #293 preserved Auksjonen listing status and prohibited ended listings from entering the live candidate path.
- PR #294 added an operational live scan result for the case where no active Clothing Inventory candidate exists.

## Accepted Clothing Inventory result

The merged implementation now proves:

- one public Clothing Inventory candidate can be preserved with source traceability;
- a candidate can be classified using the approved Opportunity Map;
- a complete Opportunity Dossier can be produced;
- three explicitly verified market comparables can be evaluated without inventing market value;
- six explicitly verified acquisition-cost components can be integrated without treating missing values as zero;
- the existing financial engine can calculate true acquisition cost, conservative resale value, expected profit, and ROI when evidence is complete;
- the existing scoring and decision-intelligence contracts can produce `BUY_REVIEW`, `WATCH`, or `REJECT`;
- incomplete evidence produces an honest `EVIDENCE_REQUIRED` or `WATCH` outcome;
- ended listings cannot be promoted as live opportunities;
- a scan with no active Clothing Inventory listing produces `NO_ACTIVE_CANDIDATE` and `NO_DECISION` rather than an error or a fabricated candidate;
- no automatic purchase, bid, contact, payment, or financial action occurs;
- repository checks pass for the merged implementation.

## Accepted live operating contract

```text
ACTIVE clothing candidate found
  -> ACTIVE_CANDIDATE_SELECTED
  -> Opportunity Dossier
  -> evidence and financial gates
  -> BUY_REVIEW / WATCH / REJECT
```

```text
No ACTIVE clothing candidate found
  -> NO_ACTIVE_CANDIDATE
  -> NO_DECISION
  -> analysis_invoked: false
```

Ended listings remain traceable evidence but never become live opportunities.

## Accepted operator surface

```text
1 — Discover Clothing Inventory Opportunities
2 — Review One Opportunity End to End
```

The primary Discovery workflow remains path-scoped and retains manual live execution. The end-to-end review workflow remains manual-only and retains its focused test, deterministic summary, and artifact.

The new active Clothing Inventory scan runner is not yet connected to the approved operator workflow surface. That integration requires a separately approved task definition and implementation PR.

## Accepted monitoring conclusion

Tracked repository evidence establishes:

- V3.2 is the primary continuous-monitoring owner;
- its hourly schedule remains collision-free relative to V3.7;
- stateful duplicate protection works when prior state is supplied;
- V3.2 and V3.3 share a state-file path but use separate cache namespaces;
- V3.3 remains the temporary repository-owned Auksjonen ingestion and snapshot-refresh workflow;
- V3.3 has a six-file pull-request path boundary while retaining manual and scheduled execution;
- live Clothing Inventory review now requires an explicitly preserved `ACTIVE` listing status;
- external consumers, branch protection, and hosted cache continuity remain `MANUAL_VERIFICATION_REQUIRED`.

## Current phase

**Phase:** Clothing Inventory Live Product Validation and Operator Integration  
**Status:** `ACTIVE`

Workflow simplification is accepted. The project has returned to the approved Clothing Inventory product path and has completed the first full public-case cycle from discovery through decision intelligence.

The remaining product-facing gap is operational: the active Clothing Inventory scan runner exists in production code but is not yet exposed through the approved manual operator surface.

## Current implementation checkpoint

```text
ACTIVE_CLOTHING_INVENTORY_OPERATOR_INTEGRATION_TASK_DEFINITION
```

Status: `NEXT`

Current task document:

```text
Not yet approved. Create one planning-only task document that defines the minimum safe integration of scripts/run_active_clothing_inventory_scan.py into exactly one existing approved manual operator workflow, while preserving ACTIVE-only selection, NO_ACTIVE_CANDIDATE behavior, reports, artifacts, source traceability, focused tests, and automatic_purchase_decision: false.
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
Wave 3A–3F — COMPLETE as accepted and recorded
Wave 4 Historical Diagnostics — COMPLETE with Wave 4D–4L retained as NOT_READY
Workflow Simplification Checkpoint — SIMPLIFICATION_ACCEPTED
```

Remaining unknowns such as external consumers, branch-protection configuration, and hosted-cache continuity remain monitored operational unknowns. They are not proven blockers to the Clothing Inventory product path.

## Non-negotiable rules

- Do not delete existing production code.
- Do not modify V2.8–V3.7 financial formulas unless a verified compatibility defect exists.
- Do not add a new domain.
- Do not invent missing values.
- Preserve source traceability.
- Do not make an automatic purchase, bid, contact, payment, or financial decision.
- `BUY_REVIEW` always requires human approval.
- Do not modify, run, disable, archive, rename, relocate, or delete a workflow until a separately approved task permits it.
- Select or change only one task in a single PR.
- Repository-setting facts and external consumers not visible in tracked files remain `MANUAL_VERIFICATION_REQUIRED`.
- Do not create another cleanup wave unless a concrete blocker is established with repository evidence.
- Do not promote an `ENDED` listing as a live opportunity.
- Do not manufacture an Opportunity Dossier when no active candidate exists.

## Definition of current-task success

The operator-integration task-definition PR succeeds only when:

1. exactly one planning-only task document is created;
2. exactly one existing approved manual workflow is selected as the integration target;
3. the document defines the runner command, inputs, outputs, report paths, summary, and artifact contract;
4. `ACTIVE_CANDIDATE_SELECTED` and `NO_ACTIVE_CANDIDATE` are both preserved as successful operational outcomes;
5. ended listings remain ineligible for live review;
6. focused tests and the canonical regression suite remain required;
7. `automatic_purchase_decision: false`, automatic bid, automatic contact, and automatic payment remain preserved;
8. no workflow, production code, test, fixture, state, cache, report, artifact, source, domain, scoring threshold, decision policy, or financial behavior is modified in the task-definition PR;
9. no more than one subsequent implementation task is identified;
10. all repository checks pass.

## Immediate next action

Execute the operator-integration task definition only:

1. create `docs/ACTIVE_CLOTHING_INVENTORY_OPERATOR_INTEGRATION_TASK_v1.0.md`;
2. inventory the two approved operator workflows and the active-scan runner contract;
3. select exactly one manual workflow as the integration target;
4. define the minimum trigger, command, output, report, summary, and artifact changes;
5. preserve both active-candidate and no-active-candidate outcomes;
6. prohibit workflow and production-code modifications in the task-definition PR;
7. identify exactly one subsequent implementation PR.
