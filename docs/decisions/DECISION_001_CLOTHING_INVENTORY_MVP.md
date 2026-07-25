# Decision 001 — Clothing Inventory End-to-End MVP

**Status:** APPROVED  
**Date:** 2026-07-25

## Decision

The project will not add another opportunity domain or expand to new fixed sources until the Clothing Inventory domain completes one full operational cycle:

```text
Opportunity Map
  -> Discovery Engine
  -> Opportunity Dossier
  -> Existing Analysis Engine
  -> Final Investment Report
```

## Why this decision exists

Earlier development produced filters, tests, reports, and source-specific integrations before proving that the system could discover and analyze one real opportunity from beginning to end.

The new rule directs all work toward the final user outcome instead of adding components that do not change that outcome.

## Reference domain

```text
CLOTHING_INVENTORY
```

This domain is the reusable template for later domains.

## Scope lock

Until the Clothing Inventory cycle passes, the following are blocked:

- Wedding-dress domain development
- Sewing-equipment domain development
- Fabric and textile-lot domain development
- Store-fixture domain development
- New fixed-source adapters as the strategic starting point
- New financial formulas
- Rebuilding the existing Analysis Engine

## Required bridge artifact

Discovery must not send only a URL into analysis. It must produce an **Opportunity Dossier** containing the maximum publicly available evidence, explicit unknowns, and traceable sources.

## Acceptance condition

This decision is satisfied only when one case reaches either:

- a final evidence-based investment report, or
- an honest `EVIDENCE_REQUIRED` outcome that identifies exactly what prevents financial judgment.

A technically successful search that returns links without a dossier does not satisfy the decision.

## Supersession rule

This decision may be changed only by a later numbered decision document that states the reason, impact, and replacement acceptance criteria.
