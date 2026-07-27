# Confirmed Dossier Intake Post-Merge Correction Task v1.0

**Task type:** Planning-only compatibility and integrity correction definition  
**Domain:** `CLOTHING_INVENTORY`  
**Implementation status:** `NOT_STARTED`  
**Automatic commercial action:** Prohibited

## 1. Purpose

Define the minimum safe post-merge correction required after the confirmed Clothing Inventory dossier-intake implementation was merged in PR #308.

The merged implementation establishes the intended source-agnostic intake path and passes its current tests. Post-merge review identified four bounded integrity defects that must be corrected before a real AXL intake package is accepted as product validation:

1. authoritative project documents still describe the implemented capability as missing or not started;
2. evidence references are validated for existence but are not yet required to semantically support the field that cites them;
3. a quantity or asking price classified as a confirmed fact may also survive in baseline `seller_claims`;
4. the retained evidence-required intake contract accepts an empty input `missing_evidence` list.

This task-definition PR creates this document only. It must not modify production code, tests, fixtures, reports, workflows, state, cache, source adapters, financial formulas, scoring thresholds, decision policy, or automatic commercial behavior.

## 2. Governing product rules

The approved architecture remains:

```text
Discovery or human-verified public evidence
  -> confirmed opportunity intake
  -> Opportunity Dossier
  -> eligibility gate
  -> retained evidence-required report
  -> later verified market and acquisition-cost stages
```

The correction must preserve:

```text
CONFIRMED_ACTIVE_CLOTHING_INVENTORY_OPPORTUNITY
DOSSIER_EVIDENCE_REQUIRED
EVIDENCE_REQUIRED
NO_DECISION
retained_in_opportunity_report: true
```

Missing evidence is not an economic rejection.

The correction does not:

- discover a new website;
- create an AXL-specific branch;
- contact a seller;
- estimate missing values;
- calculate market value, acquisition cost, profit, ROI, or maximum bid;
- invoke scoring or decision intelligence;
- produce `BUY_REVIEW`, `WATCH`, or investment `REJECT`;
- reserve, bid, purchase, or pay;
- modify a GitHub Actions workflow.

## 3. Verified merged baseline

PR #307 approved the planning contract for:

```text
confirmed-clothing-inventory-dossier-intake-v1
```

PR #308 implemented:

```text
src/opportunity_engine/discovery/confirmed_dossier_intake.py
scripts/run_clothing_inventory_single_case.py
tests/test_confirmed_clothing_inventory_dossier_intake.py
tests/fixtures/confirmed_clothing_inventory_dossier_incomplete.json
```

The merged implementation correctly provides:

- source-agnostic input validation;
- direct creation of a confirmed `DiscoveryResult` after validation;
- stable supplied opportunity-ID retention;
- separated confirmed facts, seller claims, supported inferences, unknowns, and conflicts;
- stable output filenames;
- retained `NO_DECISION` reporting;
- structured rejection for malformed, untraceable, inactive, and unconfirmed inputs;
- false automatic-action flags;
- no market, cost, scoring, or decision-intelligence invocation in confirmed-intake mode.

The existing implementation and its passing tests remain the baseline. This task authorizes only the bounded corrections defined below.

## 4. Defect A — authoritative documentation is stale

### 4.1 Current inconsistency

`docs/00_PROJECT_STATUS.md` still states that:

- the general machine-readable confirmed-opportunity intake is missing;
- the single-case runner accepts only the preserved case or Auksjonen live page;
- the task-definition checkpoint is `NEXT`;
- the task document is not yet approved.

Those statements became false after PR #307 and PR #308.

`docs/CONFIRMED_CLOTHING_INVENTORY_DOSSIER_INTAKE_TASK_v1.0.md` still states:

```text
Implementation status: NOT_STARTED
```

That statement is also stale after PR #308.

### 4.2 Required correction

The implementation PR must update both authoritative documents so they record:

- PR #307 as the accepted task definition;
- PR #308 as the merged implementation;
- the general confirmed-dossier intake as implemented and validated;
- the post-merge integrity correction as the current bounded task;
- no claim that AXL has already been executed through the machine-readable intake;
- exactly one next milestone after correction: real AXL confirmed-intake validation.

The prior task document status must become:

```text
IMPLEMENTED_AND_VALIDATED
```

The project-status document must not claim the correction is complete until its implementation PR is merged.

## 5. Defect B — evidence identity is checked without semantic support binding

### 5.1 Existing behavior

The validator currently proves that an `evidence_ref` resolves to an existing provenance record.

It does not yet require that the referenced record's `supports` list names the field or confirmation fact that cites the record.

A structurally valid but semantically mismatched package could therefore cite:

- a company-identity record as evidence for `location`;
- a category page as evidence for `listing_status` even when its `supports` list does not include that fact;
- a valid evidence ID unrelated to the field being classified.

### 5.2 Required source binding

For `source.primary_url` and `source.evidence_refs`, the implementation must require all of the following:

1. every source evidence reference resolves to a provenance record;
2. at least one referenced provenance record has a normalized HTTPS `url` equal to normalized `source.primary_url`;
3. the union of `supports` values across `source.evidence_refs` includes:

```text
opportunity_status
listing_status
title
what_is_sold
```

The required source confirmation may be distributed across multiple referenced records, but the primary URL itself must be represented by a referenced record.

A failure of these rules must produce:

```text
INTAKE_REJECTED_UNTRACEABLE
```

No dossier or normal report may be written.

### 5.3 Required field binding

For every field envelope classified as:

```text
CONFIRMED_SOURCE_FACT
CONFIRMED_IMAGE_FACT
SELLER_CLAIM_UNVERIFIED
CONFLICTING_EVIDENCE
```

each referenced provenance record must include the exact field key in its `supports` list.

Examples:

```text
fields.location -> supports contains location
fields.quantity -> supports contains quantity
fields.asking_price_nok -> supports contains asking_price_nok
fields.vat_statement -> supports contains vat_statement
```

For `CONFLICTING_EVIDENCE`, all cited records must support the conflicting field. Merely citing two existing records is insufficient.

A semantic support mismatch must produce:

```text
INTAKE_REJECTED_UNTRACEABLE
```

### 5.4 Required inference binding

For each supported inference, the union of `supports` values across its evidence references must include the inference's `field` value.

Example:

```text
supported_inferences[].field: inventory_scope
```

requires at least one cited record whose `supports` list includes:

```text
inventory_scope
```

An unresolved or semantically unsupported inference reference must produce:

```text
INTAKE_REJECTED_UNTRACEABLE
```

### 5.5 No stronger promotion

This correction must not promote an evidence class.

It only proves that the cited record declares support for the cited field. It does not independently prove that a seller claim is a confirmed fact, nor does it resolve conflicting evidence.

## 6. Defect C — confirmed quantity or price may remain in seller claims

### 6.1 Existing compatibility behavior

The existing baseline dossier builder places any candidate quantity and price into:

```text
seller_claims.quantity
seller_claims.asking_price_nok
```

The confirmed-intake adapter then adds fields classified as confirmed into:

```text
confirmed_facts
```

Without correction, a confirmed quantity or asking price may therefore appear in both evidence classes.

### 6.2 Required classification behavior

The enriched dossier must satisfy:

```text
CONFIRMED_SOURCE_FACT or CONFIRMED_IMAGE_FACT
  -> confirmed_facts only

SELLER_CLAIM_UNVERIFIED
  -> seller_claims only

UNKNOWN
  -> unknown_fields only

CONFLICTING_EVIDENCE
  -> conflicting_evidence only
```

Specifically:

- confirmed `quantity` must not remain in `seller_claims.quantity`;
- confirmed `asking_price_nok` must not remain in `seller_claims.asking_price_nok`;
- seller-claimed quantity and price must remain in `seller_claims` and must not be promoted;
- no other baseline dossier behavior may be changed.

The correction should remove only classification duplicates created by baseline compatibility. It must not broadly rewrite `build_opportunity_dossier`.

## 7. Defect D — empty missing-evidence input is accepted

### 7.1 Contract context

The current confirmed-intake implementation is intentionally restricted to retained evidence-required reporting. It does not invoke market comparables, acquisition-cost integration, financial analysis, scoring, or decision intelligence.

Its canonical outcome is:

```text
DOSSIER_EVIDENCE_REQUIRED
EVIDENCE_REQUIRED
NO_DECISION
```

### 7.2 Required validation

For this schema version, input `missing_evidence` must be a non-empty list of non-empty strings.

The validator must reject:

```json
"missing_evidence": []
```

with:

```text
INTAKE_VALIDATION_FAILED
```

The implementation must not invent a missing-evidence item to repair the input.

This rule applies only to:

```text
confirmed-clothing-inventory-dossier-intake-v1
```

It does not change eligibility or evidence requirements in other product paths.

## 8. Approved implementation task

Exactly one implementation task may follow this document:

```text
CONFIRMED_DOSSIER_INTAKE_POST_MERGE_CORRECTION_IMPLEMENTATION
```

The implementation may modify only:

```text
docs/00_PROJECT_STATUS.md
docs/CONFIRMED_CLOTHING_INVENTORY_DOSSIER_INTAKE_TASK_v1.0.md
src/opportunity_engine/discovery/confirmed_dossier_intake.py
tests/test_confirmed_clothing_inventory_dossier_intake.py
```

No fixture change is required because the existing fixture already contains:

- a primary URL represented by provenance;
- source confirmation supports;
- field-level supports;
- inference-level supports;
- a non-empty missing-evidence list.

If implementation proves that the fixture, runner, `models.py`, `e2e_checkpoint.py`, a workflow, source adapter, or Analysis Engine component must change, work must stop and a separate compatibility task must be defined with repository evidence.

## 9. Required focused tests

The implementation PR must add tests proving all of the following.

### 9.1 Source provenance binding

- a valid primary URL represented by a referenced provenance record is accepted;
- a source primary URL absent from all referenced records is rejected as untraceable;
- source evidence whose combined `supports` omit `opportunity_status` is rejected;
- source evidence whose combined `supports` omit `listing_status` is rejected;
- source evidence whose combined `supports` omit `title` is rejected;
- source evidence whose combined `supports` omit `what_is_sold` is rejected.

### 9.2 Field evidence binding

- a confirmed `location` reference whose provenance record does not support `location` is rejected;
- a seller-claimed `quantity` reference whose record does not support `quantity` is rejected;
- a conflicting `condition` package is rejected when either cited record does not support `condition`;
- valid field support remains accepted.

### 9.3 Supported-inference binding

- a valid inference whose referenced records support its field is accepted;
- an inference whose evidence records omit its field from `supports` is rejected as untraceable.

### 9.4 Classification separation

- confirmed quantity appears in `confirmed_facts` and not in `seller_claims`;
- confirmed asking price appears in `confirmed_facts` and not in `seller_claims`;
- seller-claimed quantity remains only in `seller_claims`;
- seller-claimed asking price remains only in `seller_claims`;
- unknown and conflicting values retain their existing separation.

### 9.5 Missing evidence

- the existing non-empty fixture remains accepted;
- an empty `missing_evidence` list is rejected with `INTAKE_VALIDATION_FAILED`;
- the validator does not invent replacement evidence requirements.

### 9.6 Regression and safety

The existing focused behavior must remain covered:

- valid incomplete opportunity retention;
- supplied stable opportunity ID;
- all three stable output files;
- malformed, non-HTTPS, ended, unconfirmed, unresolved-reference, and unsafe input rejection;
- confirmed-intake CLI separation;
- preserved-case runner behavior;
- no market, cost, scoring, or decision-intelligence invocation;
- no purchase, bid, contact, reservation, or payment;
- no `BUY_REVIEW`, `WATCH`, investment `REJECT`, profit, ROI, score, or maximum bid.

## 10. Required validation commands

The implementation PR must pass:

```bash
pytest tests/test_confirmed_clothing_inventory_dossier_intake.py -q
pytest tests/test_clothing_inventory_single_case_runner.py -q
pytest tests/test_e2e_clothing_inventory_checkpoint.py -q
pytest tests/test_live_clothing_candidate_ingestion.py -q
pytest tests/test_active_clothing_inventory_scan.py -q
```

The canonical repository regression suite must also pass.

## 11. Documentation result after implementation

After the correction implementation is merged, `docs/00_PROJECT_STATUS.md` must record:

```text
CONFIRMED_DOSSIER_INTAKE_POST_MERGE_CORRECTION_IMPLEMENTED
```

It must also record the next single milestone:

```text
AXL_CONFIRMED_DOSSIER_INTAKE_VALIDATION
```

That next milestone will create or validate a machine-readable AXL intake package and run it through the corrected general path. It must not hard-code AXL into production logic.

The earlier intake task document must record:

```text
Implementation status: IMPLEMENTED_AND_VALIDATED
```

No document may claim that AXL machine-readable intake validation has already occurred until a later accepted task proves it.

## 12. Safety invariants

The correction must preserve:

```text
automatic_purchase_decision: false
automatic_bid: false
automatic_contact: false
automatic_reservation: false
automatic_payment: false
```

It must also preserve:

- one active domain: `CLOTHING_INVENTORY`;
- source-agnostic production logic;
- stable opportunity IDs;
- source and evidence traceability;
- missing values as `null` or explicit unknowns;
- seller claims as unverified claims;
- conflicts as unresolved conflicts;
- no financial-formula change;
- no scoring-threshold change;
- no decision-policy change;
- no workflow or schedule change;
- no new source adapter;
- no automatic commercial execution;
- `BUY_REVIEW` as human-review-only in later eligible stages.

## 13. Out of scope

This task does not approve:

- creating the AXL machine-readable intake file;
- running AXL through the intake path;
- sending the AXL evidence request;
- changing Gmail or adding contact automation;
- adding a new public source;
- scraping a new website;
- modifying the Discovery classifier;
- modifying `build_opportunity_dossier`;
- modifying the single-case runner;
- modifying fixtures;
- modifying GitHub Actions workflows;
- changing market-comparable or acquisition-cost logic;
- changing V2.8–V3.7 formulas;
- adding another domain;
- automatic notification or scheduling.

## 14. Definition of done

This planning task is complete only when:

1. this document is the only changed file;
2. all four post-merge defects are recorded with repository-grounded behavior;
3. source-primary-URL and source-confirmation support binding are exact;
4. field and inference support binding are exact;
5. confirmed quantity and price cannot remain duplicated in seller claims;
6. empty `missing_evidence` is invalid for this evidence-required schema;
7. the implementation file boundary is exact;
8. focused and canonical regression tests are required;
9. documentation reconciliation is included in the implementation scope;
10. exactly one subsequent implementation task is identified;
11. exactly one next milestone after correction is identified;
12. all safety invariants remain explicit;
13. all repository checks pass.
