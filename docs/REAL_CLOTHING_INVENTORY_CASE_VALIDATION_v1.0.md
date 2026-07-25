# Real Clothing Inventory Case Validation v1.0

**Status:** APPROVED — NEXT IMPLEMENTATION TASK  
**Domain:** `CLOTHING_INVENTORY`

## Objective

Run exactly one real, publicly traceable Clothing Inventory candidate through the merged end-to-end checkpoint and produce either a Final Investment Report or an honest Evidence-Required Outcome.

## Scope

This checkpoint covers one real candidate only.

It must not:

- add another domain;
- create a new fixed-source architecture;
- modify V2.8–V3.7 financial formulas;
- invent missing facts, prices, quantities, VAT, transport, brands, sizes, or comparables;
- make an automatic purchase, bid, or contact decision.

## Required source package

Preserve all publicly available evidence for the selected candidate:

- source URL;
- source title;
- source text;
- source name;
- publication or discovery timestamp;
- location when available;
- public contact route when available;
- asking price or bid basis when available;
- quantity when available;
- image and attachment references when available;
- provenance for every captured field.

## Required execution path

```text
Real public candidate
  -> Scenario Classification
  -> Opportunity Dossier
  -> Eligibility Gate
  -> Existing Analysis Engine when eligible
  -> Final Investment Report or Evidence-Required Outcome
```

## Classification output

The result must include:

- primary scenario;
- optional secondary scenario;
- supporting signals;
- contradictory signals;
- confidence or explicit rule basis;
- qualification status.

A weak or ambiguous signal alone must not become a confirmed sale.

## Opportunity Dossier output

The dossier must separate:

- confirmed facts;
- seller claims;
- supported inferences with confidence;
- unknown fields;
- missing evidence;
- seller questions;
- text, image, attachment, and company-record provenance.

## Eligibility gate

Only a confirmed sale with sufficient traceability and verified decision inputs may enter financial analysis.

Missing evidence must result in `EVIDENCE_REQUIRED`, not invented values and not automatic rejection.

## Existing Analysis Engine

When eligibility allows, use existing downstream capabilities without rebuilding them:

- V2.8 Market Comparables;
- V2.9 Acquisition Cost;
- V2.10 Financial Integration;
- V2.11 Live Validation;
- applicable V3.x ranking, state, and review outputs.

## Final output

Produce exactly one of:

### A. Final Investment Report

Used when sufficient verified evidence exists.

### B. Evidence-Required Outcome

Used when the candidate is commercially relevant but key evidence remains missing.

Both outputs must distinguish confirmed facts, seller claims, estimates, and unknowns.

## Acceptance criteria

The checkpoint passes only when:

- one real public candidate is preserved with source traceability;
- one approved scenario classification is produced;
- one complete Opportunity Dossier is generated;
- unsupported values remain `null` or explicitly unknown;
- only eligible confirmed data reaches Analysis;
- existing financial formulas remain unchanged;
- the result reaches either a Final Investment Report or an honest Evidence-Required Outcome;
- no automatic purchase, bid, or contact action occurs;
- all relevant tests remain passing.

## First implementation sequence

1. Select one real Clothing Inventory candidate.
2. Capture the public source package.
3. Build the canonical discovery record.
4. Classify it using the completed knowledge cards.
5. Generate the Opportunity Dossier.
6. Apply the eligibility gate.
7. Run existing Analysis only when eligible.
8. Produce the final report or evidence-required result.
9. Add one real-case acceptance fixture or snapshot test.
10. Update `docs/00_PROJECT_STATUS.md` only after the result is verified.

## Expansion gate

No new domain may begin until this real-case validation is accepted and merged.