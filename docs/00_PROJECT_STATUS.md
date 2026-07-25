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
  -> Final Investment Report
```

## Current scope lock

The only active domain is:

```text
CLOTHING_INVENTORY
```

No new domain and no new source expansion is approved until one complete Clothing Inventory cycle succeeds from discovery through final report.

Blocked domains include:

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
- `STORE_CLOSING` knowledge card approved and merged.
- `BANKRUPTCY` knowledge card approved and merged.
- `INVENTORY_LIQUIDATION` knowledge card approved and merged.
- `LARGE_LOT` knowledge card approved and merged.
- `WAREHOUSE_SURPLUS` knowledge card approved and merged.

## Newly approved decision

The first real MVP is not a list of links. It is one complete cycle:

```text
Discover one Clothing Inventory opportunity
  -> build its Opportunity Dossier
  -> compare against the market
  -> run the existing analysis pipeline
  -> produce a final evidence-based report
```

## Current phase

**Phase:** Clothing Inventory Opportunity Map — scenario knowledge cards  
**Current task:** Review and approve the complete `IMPORTER_CLEARANCE` knowledge card.

## Current scenario

```text
IMPORTER_CLEARANCE
```

Status: `READY_FOR_REVIEW`

Current task document:

```text
docs/opportunity_maps/IMPORTER_CLEARANCE_KNOWLEDGE_CARD_v1.0.md
```

## Scenario queue

1. STORE_CLOSING — COMPLETE
2. BANKRUPTCY — COMPLETE
3. INVENTORY_LIQUIDATION — COMPLETE
4. LARGE_LOT — COMPLETE
5. WAREHOUSE_SURPLUS — COMPLETE
6. IMPORTER_CLEARANCE — READY FOR REVIEW
7. FACTORY_SURPLUS — NOT STARTED
8. BUSINESS_CHANGE — NOT STARTED
9. AUCTION — NOT STARTED
10. BRANCH_CLOSURE — NOT STARTED

Only one scenario may be developed at a time. After each scenario is completed, this file must be updated before starting the next one.

## Non-negotiable rules

- Do not delete existing production code.
- Do not modify V2.8–V3.7 financial formulas unless a verified compatibility defect exists.
- Do not add new domains.
- Do not add new fixed-source integrations as the project direction.
- Do not reject a valid discovery merely because analysis data is missing.
- Do not invent missing values.
- Mark facts, estimates, and unknowns separately.
- Preserve source traceability for text, images, prices, quantities, and comparisons.
- Do not make an automatic purchase, bid, or contact decision.

## Definition of MVP success

The Clothing Inventory MVP succeeds only when one real or controlled end-to-end case produces:

1. A valid discovered opportunity.
2. A complete Opportunity Dossier using all publicly available evidence.
3. Explicit missing-data fields and seller questions.
4. Evidence-based market comparables.
5. Existing acquisition-cost and financial integration results.
6. A final report that distinguishes confirmed facts, estimates, and unknowns.
7. An honest evidence-required outcome when the available data is insufficient.

## Immediate next action

Review `docs/opportunity_maps/IMPORTER_CLEARANCE_KNOWLEDGE_CARD_v1.0.md`.

After approval and merge:

1. mark `IMPORTER_CLEARANCE` complete;
2. set `FACTORY_SURPLUS` as the only next scenario;
3. do not begin any other scenario before that checkpoint is merged.
