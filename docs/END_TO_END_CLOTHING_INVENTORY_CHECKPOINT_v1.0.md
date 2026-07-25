# End-to-End Clothing Inventory Implementation Checkpoint v1.0

**Status:** APPROVED — NEXT IMPLEMENTATION TASK  
**Domain:** `CLOTHING_INVENTORY`

## Objective

Prove one complete evidence-based cycle from discovery through final report using the completed Clothing Inventory Opportunity Map and the existing Analysis Engine.

## Required path

```text
Opportunity Map
  -> Discovery Candidate
  -> Scenario Classification
  -> Opportunity Dossier
  -> Eligibility Gate
  -> Existing Analysis Engine
  -> Final Investment Report or Evidence-Required Outcome
```

## Scope

This checkpoint covers exactly one real or controlled Clothing Inventory opportunity.

It must not:

- add another domain;
- add a new fixed-source architecture;
- modify V2.8–V3.7 financial formulas;
- invent missing facts;
- create an automatic purchase, bid, or contact decision.

## Required implementation outputs

### 1. Discovery candidate

Preserve at minimum:

- source URL or controlled fixture identity;
- source title;
- source text;
- location when available;
- contact route when public;
- discovered timestamp;
- source traceability.

### 2. Scenario classification

Classify the candidate against the ten approved knowledge cards.

Required output:

- primary scenario;
- optional secondary scenario;
- supporting signals;
- contradictory signals;
- classification confidence;
- qualification status.

A weak signal alone must not create a confirmed opportunity.

### 3. Opportunity Dossier

Create a dossier that separates:

- confirmed facts;
- seller claims;
- supported inferences with confidence;
- unknown fields;
- missing evidence;
- questions for the seller;
- text, image, attachment, and company-record provenance.

### 4. Eligibility gate

Only a confirmed sale with sufficient traceability may enter financial analysis.

Unconfirmed closure, bankruptcy, liquidation, or inventory signals must remain in a contact-required or evidence-required state.

### 5. Existing Analysis Engine

Use the existing downstream capabilities without rebuilding them:

- V2.8 Market Comparables;
- V2.9 Acquisition Cost;
- V2.10 Financial Integration;
- V2.11 Live Validation;
- applicable V3.x ranking, state, and review outputs.

### 6. Final output

Produce exactly one of:

#### A. Final Investment Report

Used when sufficient verified evidence exists.

The report must distinguish facts, estimates, seller claims, and unknowns.

#### B. Evidence-Required Outcome

Used when the opportunity is promising but key evidence is missing.

This is a valid honest result and must not be converted into a rejection merely because price, quantity, VAT, transport, brands, sizes, or comparables are incomplete.

## Acceptance criteria

The checkpoint passes only when:

- one candidate is preserved with source traceability;
- one approved scenario classification is produced;
- one complete Opportunity Dossier is generated;
- unsupported values remain `null` or explicitly unknown;
- only eligible confirmed data reaches Analysis;
- the existing financial formulas remain unchanged;
- the result reaches either a Final Investment Report or an honest Evidence-Required Outcome;
- no automatic purchase, bid, or contact action occurs;
- all existing relevant tests remain passing.

## First implementation sequence

1. Select one real or controlled Clothing Inventory case.
2. Build the canonical discovery record.
3. Classify it using the completed knowledge cards.
4. Generate the Opportunity Dossier.
5. Apply the eligibility gate.
6. Connect eligible data to the existing Analysis Engine.
7. Produce the final report or evidence-required result.
8. Add one end-to-end acceptance test.
9. Update `docs/00_PROJECT_STATUS.md` only after the checkpoint result is verified.

## Expansion gate

No new domain may begin until this checkpoint is accepted and merged.
