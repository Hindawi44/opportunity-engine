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
- Wave 4B final preservation run accepted with run ID `30175512518`, artifact ID `8624093715`, complete archive inventory, and artifact digest `sha256:57cc918d719a1aafa6720bff486035daf157a5e09e641f6e61214b6c8ff89420`.
- Wave 4C reversible disablement merged in PR #234: `.github/workflows/v2.6.6-live-dry-run.yml` remains preserved at the same path, is manual-only through `workflow_dispatch`, and includes an explicit historical-diagnostic notice and documented rollback procedure.

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
- its hourly schedule `17 * * * *` is collision-free relative to V3.7 and should remain;
- stateful duplicate protection works when prior state is supplied;
- V3.2 and V3.3 share a state-file path but use separate cache namespaces;
- the V3.2 pull-request trigger is scoped to its six tracked dependencies;
- V3.3 remains the temporary repository-owned Auksjonen ingestion and snapshot-refresh workflow;
- the continued operational need for V3.3's hourly schedule remains `MANUAL_VERIFICATION_REQUIRED`;
- external consumers, branch protection, and hosted cache continuity remain `MANUAL_VERIFICATION_REQUIRED`.

## Accepted historical-diagnostic conclusion

Tracked repository evidence establishes:

- V2.6.6 is a preserved, manual-only historical production-readiness diagnostic;
- no tracked current workflow reproduces its exact live two-run evidence bundle and artifact contract;
- unit tests cover readiness, secret non-disclosure, missing-secret failure, and repeat-protection comparison;
- the final manual run completed successfully on `main`;
- its run metadata, artifact metadata, archive digest, complete inventory, readiness evidence, and repeat-protection evidence were preserved;
- the workflow is non-routine through a reversible repository change and remains available only for intentional manual execution;
- the workflow file was not deleted, renamed, relocated, or archived;
- branch protection, external consumers, operator dependence, and historical artifact links remain `MANUAL_VERIFICATION_REQUIRED`;
- deletion remains unapproved.

## Current phase

**Phase:** Operator Workflow Simplification — post-Wave 4C checkpoint  
**Current task:** No additional implementation task is approved. Select and define the next task from the approved cleanup plan before changing another workflow.

## Current implementation checkpoint

```text
OPERATOR_WORKFLOW_POST_WAVE4C_NEXT_TASK_SELECTION
```

Status: `AWAITING_APPROVAL`

Current task document:

```text
NONE — a separate status-definition PR must approve the next task first
```

## Non-negotiable rules

- Do not delete existing production code.
- Do not modify V2.8–V3.7 financial formulas unless a verified compatibility defect exists.
- Do not add a new domain.
- Do not invent missing values.
- Preserve source traceability.
- Do not make an automatic purchase, bid, or contact decision.
- Do not modify another workflow until its exact next-task document is approved.
- Preserve the Wave 4B evidence and the Wave 4C reversible state.
- Repository-setting facts and external consumers not visible in tracked files remain `MANUAL_VERIFICATION_REQUIRED`.

## Definition of current-task success

This checkpoint succeeds only when:

1. Wave 4C is recorded as completed and retained;
2. no unapproved workflow change is started;
3. the remaining candidates in `docs/WORKFLOW_CLEANUP_IMPLEMENTATION_PLAN_v1.0.md` are reviewed;
4. exactly one next task is selected with explicit scope, dependencies, rollback, and verification criteria;
5. a dedicated task document is approved before implementation begins.

## Immediate next action

Do not implement another workflow change yet:

1. review the remaining Wave 4 historical-diagnostic candidates in `docs/WORKFLOW_CLEANUP_IMPLEMENTATION_PLAN_v1.0.md`;
2. choose exactly one candidate based on verified dependencies and current coverage;
3. create a focused task-definition document and status update;
4. keep all unresolved repository-setting and external-consumer facts as `MANUAL_VERIFICATION_REQUIRED`;
5. begin implementation only after that task-definition PR is merged.
