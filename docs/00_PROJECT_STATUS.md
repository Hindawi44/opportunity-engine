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

No new domain implementation is approved until the next task below is completed and accepted.

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

## Current phase

**Phase:** Operator Workflow Simplification — Inventory Only  
**Current task:** Inventory and classify the existing GitHub Actions workflows so the project can later expose one primary discovery workflow and one end-to-end review workflow without deleting or disabling anything in this task.

## Current implementation checkpoint

```text
OPERATOR_WORKFLOW_INVENTORY
```

Status: `NEXT`

Current task document:

```text
docs/OPERATOR_WORKFLOW_INVENTORY_v1.0.md
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
- Do not delete, move, disable, rename, or change triggers for workflows during the inventory task.

## Definition of current-task success

The workflow inventory succeeds only when it produces:

1. A complete list of GitHub Actions workflow files.
2. A classification for each workflow:
   - primary operator candidate;
   - end-to-end review candidate;
   - active production support;
   - acceptance test;
   - historical diagnostic;
   - uncertain and requiring review.
3. Trigger information for every workflow.
4. The main responsibility and owning engine for every workflow.
5. Overlap and duplication findings.
6. A non-destructive recommendation for the next cleanup PR.
7. No workflow file changes other than the inventory document itself.

## Immediate next action

Execute the workflow inventory only:

1. enumerate every file under `.github/workflows/`;
2. record workflow name, triggers, purpose, and owning engine;
3. classify each workflow without deleting or changing it;
4. identify the best primary discovery workflow candidate;
5. identify the best end-to-end review workflow candidate;
6. document overlaps and historical diagnostics;
7. propose—but do not execute—a separate cleanup plan;
8. keep all domains and financial formulas unchanged.
