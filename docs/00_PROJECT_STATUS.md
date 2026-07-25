# Opportunity Engine — Project Status

**Last updated:** 2026-07-25  
**Status:** ACTIVE  
**Authoritative repository:** `Hindawi44/opportunity-engine`

## Session startup rule

Every new development session must begin by reading, in this order:

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

A third bridge artifact is required between them:

- **Opportunity Dossier:** gathers and organizes all available evidence about a discovered opportunity before financial analysis.

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

No new domain implementation is approved until the workflow-simplification checkpoint below is completed and accepted.

Blocked domains remain:

- Wedding dresses
- Sewing equipment
- Fabrics
- Store fixtures
- Other opportunity domains

## Completed and retained

- Blueprint v2.0 approved as strategic baseline.
- Repository Architecture Audit v2.0 merged.
- Discovery and Analysis ownership boundaries defined.
- Existing Analysis Engine V2.8–V3.7 retained and frozen.
- Legacy FINN/Auksjonen adapters retained as optional providers.
- Clothing Inventory selected as the reference MVP domain.
- Opportunity Dossier specification approved as the bridge evidence artifact.
- All ten Clothing Inventory knowledge cards approved and merged:
  - `STORE_CLOSING`
  - `BANKRUPTCY`
  - `INVENTORY_LIQUIDATION`
  - `LARGE_LOT`
  - `WAREHOUSE_SURPLUS`
  - `IMPORTER_CLEARANCE`
  - `FACTORY_SURPLUS`
  - `BUSINESS_CHANGE`
  - `AUCTION`
  - `BRANCH_CLOSURE`
- Controlled End-to-End Clothing Inventory checkpoint implemented and merged in PR #206.
- Real Clothing Inventory case validation implemented and merged in PR #208.
- Operator Workflow Inventory completed and merged in PR #210.

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

Accepted path:

```text
Real public candidate
  -> AUCTION
  -> SALE_CONFIRMED
  -> Opportunity Dossier
  -> Eligibility Gate
  -> EVIDENCE_REQUIRED
```

The `EVIDENCE_REQUIRED` result is an accepted checkpoint outcome, not a rejection and not a financial recommendation.

## Accepted workflow inventory result

The merged workflow inventory proves:

- all 31 files under `.github/workflows/` are represented;
- every workflow has documented triggers, responsibility, owner, and classification;
- `discovery-v1.2-live-pilot.yml` is the strongest primary discovery candidate;
- `v3.7-production-pilot.yml` is the strongest end-to-end review candidate;
- `tests.yml` is the canonical repository-wide quality gate;
- duplicated regression runs, schedule collisions, acceptance-only workflows, and historical diagnostics are documented;
- no workflow file was changed during inventory.

## Current phase

**Phase:** Operator Workflow Simplification — Cleanup Planning Only  
**Current task:** Produce an explicit, file-by-file, non-destructive cleanup plan based on the accepted inventory. Do not execute workflow changes in this task.

## Current implementation checkpoint

```text
OPERATOR_WORKFLOW_CLEANUP_PLAN
```

Status: `NEXT`

Current task document:

```text
docs/OPERATOR_WORKFLOW_CLEANUP_PLAN_v1.0.md
```

## Knowledge-card phase

Status: `COMPLETE`

All ten scenarios remain complete. No additional Clothing Inventory knowledge card is approved unless a verified gap is found.

## Non-negotiable rules

- Do not delete existing production code.
- Do not modify V2.8–V3.7 financial formulas unless a verified compatibility defect exists.
- Do not add a new domain in this task.
- Do not add a new fixed-source architecture.
- Do not reject a valid discovery merely because analysis data is missing.
- Do not invent missing values.
- Mark facts, estimates, seller claims, and unknowns separately.
- Preserve source traceability for text, images, prices, quantities, and comparisons.
- Do not make an automatic purchase, bid, or contact decision.
- Do not delete, move, disable, rename, or change triggers for workflows during cleanup planning.
- Every proposed workflow action must identify risk, dependency, rollback, and verification requirements.

## Definition of current-task success

The cleanup-plan task succeeds only when it produces:

1. A file-by-file proposed disposition for all 31 workflows.
2. A clear distinction between:
   - keep unchanged;
   - keep but rename later;
   - keep but narrow triggers later;
   - keep as scheduled production support;
   - convert to manual/path-scoped acceptance later;
   - archive or disable later after verification.
3. A proposed phone-friendly operator surface with one discovery workflow and one review workflow.
4. A schedule-collision resolution proposal.
5. A duplicated-regression reduction proposal that retains `tests.yml` as the canonical quality gate.
6. Risk, dependency, rollback, and verification notes for every proposed change category.
7. An ordered sequence for a later implementation PR.
8. No workflow file changes in this planning task.

## Immediate next action

Execute cleanup planning only:

1. read `docs/WORKFLOW_INVENTORY_REPORT_v1.0.md`;
2. produce a file-by-file future disposition for all 31 workflows;
3. define the intended operator-facing workflow names and roles;
4. propose safe trigger and schedule changes without applying them;
5. define regression, rollback, and artifact-preservation requirements;
6. identify changes that require separate PRs;
7. do not modify any file under `.github/workflows/`;
8. keep all domains and financial formulas unchanged.
