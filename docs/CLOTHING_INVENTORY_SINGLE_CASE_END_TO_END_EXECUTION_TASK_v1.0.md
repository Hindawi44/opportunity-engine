# Clothing Inventory Single-Case End-to-End Execution Task v1.0

**Status:** PROPOSED — PLANNING ONLY  
**Repository:** `Hindawi44/opportunity-engine`  
**Domain lock:** `CLOTHING_INVENTORY` only  
**Scope:** define one product-facing end-to-end execution; no workflow or production implementation in this PR

## 1. Purpose

Define the smallest reversible implementation that executes one concrete, source-traceable Clothing Inventory candidate through the already approved product path:

```text
one source-traceable Clothing Inventory candidate
  -> Opportunity Map classification
  -> Discovery evidence preservation
  -> Opportunity Dossier
  -> eligibility gate
  -> Existing Analysis Engine
  -> final investment report or honest EVIDENCE_REQUIRED outcome
```

This task is the first product-facing step after the accepted workflow-simplification checkpoint. It must prove the existing architecture can produce an honest end-to-end outcome before any domain expansion or bulk processing is approved.

## 2. Authoritative inputs

The later implementation must reuse existing repository contracts before adding new architecture. At minimum, it must inspect and preserve:

- `docs/00_PROJECT_STATUS.md`;
- `docs/Opportunity_Discovery_Analysis_Blueprint_v2.0.md`;
- `docs/REPOSITORY_ARCHITECTURE_AUDIT_v2.0.md`;
- the approved Opportunity Dossier specification;
- the ten approved Clothing Inventory knowledge cards;
- the merged Controlled End-to-End Clothing Inventory checkpoint;
- the merged real Clothing Inventory case validation;
- the existing Discovery Engine contracts;
- the existing eligibility gate;
- the existing Analysis Engine V2.8–V3.7 contracts;
- the accepted two-workflow operator surface.

Conversation text is not authoritative evidence.

## 3. Single-case boundary

The implementation must process exactly one candidate.

The candidate must:

1. be classified as `CLOTHING_INVENTORY`;
2. have a stable source identifier or URL;
3. preserve all source-provided facts with traceability;
4. contain no invented market value, demand estimate, logistics cost, resale price, margin, or profit;
5. remain eligible for an honest `EVIDENCE_REQUIRED` result when evidence is incomplete.

The implementation must not add:

- wedding dresses;
- fabrics;
- sewing equipment;
- store fixtures;
- vehicles;
- another domain;
- bulk ingestion;
- automatic purchase, bid, contact, payment, or financial execution.

## 4. Candidate selection rule

The implementation PR must select one existing repository-supported candidate source path. Prefer an already preserved deterministic candidate or fixture when it provides complete source traceability and stable tests.

A live external page may be used only if the implementation also preserves a deterministic repository fixture or snapshot sufficient for repeatable testing.

Candidate selection must be documented with:

- source name;
- source identifier or URL;
- retrieval or preservation timestamp when available;
- original title and description fragments as permitted;
- observed price and currency when provided;
- location when provided;
- condition and quantity when provided;
- evidence gaps.

Missing fields must remain unknown.

## 5. Required execution stages

### 5.1 Opportunity Map classification

The candidate must be classified using the approved Opportunity Map.

The output must explicitly state:

```text
domain: CLOTHING_INVENTORY
classification_status: ACCEPTED | REJECTED | EVIDENCE_REQUIRED
```

A rejected or evidence-required classification must stop unsupported downstream assumptions.

### 5.2 Discovery evidence preservation

The Discovery stage must preserve source evidence and provenance without performing financial analysis.

Required minimum provenance fields:

```text
source_name
source_identifier
source_url_or_reference
observed_at
raw_or_normalized_title
observed_price
observed_currency
observed_location
observed_condition
observed_quantity
source_evidence_references
```

Unknown values must use the repository's existing unknown/null convention.

### 5.3 Opportunity Dossier

The implementation must produce one Opportunity Dossier using the approved schema.

The dossier must distinguish:

- observed facts;
- normalized facts;
- derived non-financial classifications;
- missing evidence;
- provenance;
- eligibility-gate inputs.

It must not turn missing evidence into zero, false certainty, or an estimated value.

### 5.4 Eligibility gate

The existing eligibility gate must decide whether the candidate has sufficient verified evidence for the Analysis Engine.

The gate output must include:

```text
eligible_for_analysis: true | false
missing_required_evidence: [...]
gate_reason_codes: [...]
```

If false, the downstream result must be `EVIDENCE_REQUIRED` without synthetic financial calculations.

### 5.5 Existing Analysis Engine

The implementation must reuse the existing Analysis Engine. It must not modify frozen V2.8–V3.7 financial formulas unless a verified compatibility defect is first documented in a separate task.

When eligible, only verified evidence may enter financial calculations.

When not eligible, the Analysis Engine boundary must remain protected and the final result must explain the missing evidence.

### 5.6 Final output

The implementation must generate one machine-readable final report and one concise operator-readable summary.

Permitted final outcomes:

```text
BUY
WATCH
REJECT
EVIDENCE_REQUIRED
```

`BUY`, `WATCH`, or `REJECT` is permitted only when supported by the existing verified-analysis contracts.

An honest `EVIDENCE_REQUIRED` result counts as successful end-to-end execution.

The final output must explicitly preserve:

```text
automatic_purchase_decision: false
automatic_bid: false
automatic_contact: false
automatic_payment: false
```

## 6. Required implementation deliverables

The later implementation PR must contain the smallest set of files required to execute and verify the single case. It must identify exact paths before editing.

Expected deliverables are:

1. one deterministic candidate input or preserved snapshot;
2. one runner or existing runner extension that connects approved stages;
3. one Opportunity Dossier output;
4. one final report output;
5. focused tests proving traceability, unknown preservation, gate behavior, and final outcome;
6. a concise operator-readable summary.

The implementation must prefer existing modules and scripts over creating parallel engines.

## 7. Testing requirements

Focused tests must prove:

1. exactly one Clothing Inventory candidate is processed;
2. source traceability survives normalization;
3. unsupported values remain unknown;
4. the Opportunity Dossier validates against the approved contract;
5. the eligibility gate blocks unsupported analysis;
6. the final result is deterministic for the preserved input;
7. `EVIDENCE_REQUIRED` is treated as a valid honest outcome;
8. no automatic action occurs;
9. existing repository tests still pass.

If the selected case is eligible for analysis, tests must also prove that only verified values reach the Analysis Engine.

## 8. Prohibited changes in this task-definition PR

This PR must add only this planning document.

Do not modify or run:

- any file under `.github/workflows/`;
- production code;
- tests or fixtures;
- source adapters;
- state or cache contracts;
- reports or artifacts;
- financial formulas;
- domain scope.

Do not create a parser, analyzer, workflow, scheduler, automated recommendation service, or purchase integration in this task-definition PR.

## 9. Later implementation safety boundaries

The later implementation must:

- remain single-case and reversible;
- use one implementation PR;
- list exact files changed;
- preserve existing workflows unless separately approved;
- preserve source traceability;
- preserve unknown values;
- preserve `automatic_purchase_decision: false`;
- avoid external side effects;
- produce deterministic test evidence;
- document rollback as reverting the implementation commit.

## 10. Definition of implementation success

The later implementation succeeds only when:

1. one source-traceable `CLOTHING_INVENTORY` candidate enters the approved path;
2. one valid Opportunity Dossier is produced;
3. the eligibility gate produces an explicit result;
4. the existing Analysis Engine is either safely invoked with verified evidence or honestly blocked;
5. one final machine-readable report is produced;
6. one operator-readable summary is produced;
7. the outcome is supported or is `EVIDENCE_REQUIRED`;
8. no automatic commercial or financial action occurs;
9. all focused and repository-wide tests pass.

## 11. Single subsequent task

After this task-definition PR is merged, the only approved next task is:

```text
CLOTHING_INVENTORY_SINGLE_CASE_END_TO_END_IMPLEMENTATION
```

That task must implement exactly the single case defined here. It must not create another planning wave, workflow-cleanup task, domain, or bulk-processing feature.
