# Opportunity Engine — Project Status

**Last updated:** 2026-07-25  
**Status:** ACTIVE  
**Authoritative repository:** `Hindawi44/opportunity-engine`

## Session startup rule

Every development session must begin by reading, in this order:

1. `docs/00_PROJECT_STATUS.md`
2. `docs/Opportunity_Discovery_Analysis_Blueprint_v2.0.md`
3. `docs/REPOSITORY_ARCHITECTURE_AUDIT_v2.0.md`
4. The current-task document named below

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

## Current phase

**Phase:** Operator Workflow Simplification — Wave 3 Scheduled Production Support  
**Current task:** Audit V3.2 continuous-monitoring ownership before changing any trigger, schedule, state, cache, or artifact behavior.

## Current implementation checkpoint

```text
OPERATOR_WORKFLOW_WAVE3C_V32_MONITORING_AUDIT
```

Status: `NEXT`

Current task document:

```text
docs/OPERATOR_WORKFLOW_WAVE3C_v1.0.md
```

## Non-negotiable rules

- Do not delete existing production code.
- Do not modify V2.8–V3.7 financial formulas unless a verified compatibility defect exists.
- Do not add a new domain.
- Do not invent missing values.
- Preserve source traceability.
- Do not make an automatic purchase, bid, or contact decision.
- Wave 3C is documentation and verification only.
- Do not change any workflow, trigger, schedule, cache, state, command, report, or artifact in Wave 3C.
- Do not change V3.3, `scheduled-agent.yml`, or `daily-opportunity-pipeline.yml` in this task.
- Repository-setting facts not visible in tracked files remain `MANUAL_VERIFICATION_REQUIRED`.

## Definition of current-task success

Wave 3C succeeds only when:

1. V3.2 triggers, schedule, jobs, commands, state, cache, report, and artifact contracts are documented;
2. the minute-17 collision status after Wave 3B is confirmed;
3. state continuity and duplicate protection across runs are mapped;
4. tracked and external consumers are classified honestly;
5. a future trigger/schedule proposal is defined without applying it;
6. rollback and verification requirements are explicit;
7. no workflow or production-code changes occur;
8. all repository checks pass.

## Immediate next action

Execute Wave 3C audit only:

1. inspect V3.2 and its directly referenced scripts/tests;
2. map state/cache/report/artifact ownership;
3. verify the schedule is now collision-free relative to V3.7;
4. identify whether the broad PR trigger is still needed;
5. document risk, rollback, and implementation verification;
6. do not implement trigger or schedule changes yet.
