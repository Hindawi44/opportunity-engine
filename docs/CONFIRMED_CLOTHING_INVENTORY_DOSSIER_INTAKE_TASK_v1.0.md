# Confirmed Clothing Inventory Dossier Intake Task v1.0

**Task type:** Planning-only task definition  
**Domain:** `CLOTHING_INVENTORY`  
**Implementation status:** `NOT_STARTED`  
**Automatic commercial action:** Prohibited

## 1. Purpose

Define the minimum safe, source-agnostic machine-readable intake of one confirmed active Clothing Inventory opportunity into the existing single-case Opportunity Dossier and reporting boundary.

The implementation defined here must make opportunities such as the validated AXL case consumable by the program without hard-coding AXL, Auksjonen, FINN, Norsk Avvikling, or any other named source.

A confirmed opportunity with incomplete quantity, acquisition price, VAT, fees, condition, pickup, packing, transport, or market evidence must remain visible in the generated reports as an evidence-required opportunity. Missing decision evidence must not become an economic rejection.

This planning PR creates this document only. It must not modify production code, workflows, tests, fixtures, reports, artifacts, sources, state, cache, formulas, thresholds, or commercial behavior.

## 2. Governing product rules

The implementation must preserve the approved architecture:

```text
Discovery or human-verified public evidence
  -> confirmed opportunity intake
  -> Opportunity Dossier
  -> eligibility gate
  -> retained evidence-required report
  -> later verified market and acquisition-cost stages
```

The intake layer does not:

- discover websites;
- contact a seller;
- estimate missing values;
- calculate market value, profit, ROI, or a maximum bid;
- score the opportunity;
- produce `BUY_REVIEW`, `WATCH`, or `REJECT`;
- reserve, bid, purchase, or pay.

## 3. Existing contracts to reuse

### 3.1 Discovery data contracts

Reuse:

```text
src/opportunity_engine/discovery/models.py
```

Relevant existing types:

```text
DiscoveryCandidate
DiscoveryResult
```

The confirmed-intake adapter must create a `DiscoveryCandidate` only from validated input values. It must create a `DiscoveryResult` with explicit confirmed-sale status only after the intake contract passes validation.

The adapter must not depend on keyword reclassification of a human-verified confirmed opportunity. It must not manufacture confirmation from weak text.

### 3.2 Dossier and eligibility contracts

Reuse where compatible:

```text
src/opportunity_engine/discovery/e2e_checkpoint.py
```

Relevant existing boundaries:

```text
build_opportunity_dossier
validate/evaluate analysis eligibility through evaluate_analysis_eligibility
OpportunityDossier
EligibilityDecision
CheckpointOutcome
```

The baseline dossier returned by `build_opportunity_dossier` must be enriched with the field classifications and provenance supplied by the confirmed-intake contract. Unknown values remain unknown.

### 3.3 Single-case report boundary

Reuse:

```text
scripts/run_clothing_inventory_single_case.py
```

Relevant existing boundaries:

```text
build_operator_summary
write_report_outputs
```

The implementation must continue writing the stable filenames:

```text
opportunity-dossier.json
final-report.json
operator-summary.txt
```

## 4. Confirmed product gap

The current runner accepts:

- the preserved deterministic case; or
- one active Auksjonen listing selected from a public page.

It does not accept a general structured opportunity already confirmed through another public route or a human-verified evidence package.

The missing bridge is therefore:

```text
confirmed-clothing-inventory-dossier-intake-v1 JSON
  -> validated DiscoveryCandidate and DiscoveryResult
  -> enriched OpportunityDossier
  -> eligibility result
  -> retained final report and operator summary
```

## 5. Integration decision

Add one new CLI mode to the existing runner:

```bash
python scripts/run_clothing_inventory_single_case.py \
  --confirmed-intake-file path/to/confirmed-opportunity.json \
  --output-dir artifacts/confirmed-clothing-inventory-dossier
```

Rules:

- `--confirmed-intake-file` is mutually exclusive with `--live` and `--html-file`.
- Confirmed-intake mode must not fetch a website.
- Confirmed-intake mode must not require an API key.
- Confirmed-intake mode must not invoke seller contact.
- In this implementation, confirmed-intake mode must reject `--comparables-file` and `--costs-file`; the task is dossier intake and report retention only.
- Confirmed-intake mode must not call scoring or decision intelligence.
- The existing preserved-case and Auksjonen modes must remain unchanged.

## 6. Versioned JSON input contract

Canonical schema version:

```text
confirmed-clothing-inventory-dossier-intake-v1
```

### 6.1 Required top-level shape

```json
{
  "schema_version": "confirmed-clothing-inventory-dossier-intake-v1",
  "opportunity_id": "stable-source-independent-id",
  "domain": "CLOTHING_INVENTORY",
  "primary_scenario": "COMPANY_BANKRUPTCY",
  "record_type": "SALE_LISTING",
  "qualification_status": "SALE_CONFIRMED",
  "opportunity_status": "CONFIRMED_ACTIVE_CLOTHING_INVENTORY_OPPORTUNITY",
  "listing_status": "ACTIVE",
  "title": "Public opportunity title",
  "description": "Public description or null",
  "observed_at": "2026-07-27T12:00:00+00:00",
  "source": {},
  "fields": {},
  "supported_inferences": [],
  "missing_evidence": [],
  "seller_questions": [],
  "provenance": {},
  "safety": {}
}
```

### 6.2 Required identity and status rules

Required exact values:

```text
domain: CLOTHING_INVENTORY
record_type: SALE_LISTING
qualification_status: SALE_CONFIRMED
opportunity_status: CONFIRMED_ACTIVE_CLOTHING_INVENTORY_OPPORTUNITY
listing_status: ACTIVE
```

Allowed `primary_scenario` values:

```text
STORE_CLOSING
COMPANY_BANKRUPTCY
INVENTORY_LIQUIDATION
AUCTION
WAREHOUSE_SURPLUS
IMPORTER_LIQUIDATION
MANUFACTURER_EXCESS
LARGE_LOT_SALE
BUSINESS_MODEL_CHANGE
BRANCH_CLOSURE
```

`opportunity_id` must be non-empty and stable across repeated intake of the same opportunity. The implementation must preserve the supplied ID instead of replacing it with a URL hash.

`title` must be non-empty.

`observed_at` must be a timezone-aware ISO-8601 timestamp.

An `ENDED`, expired, inaccessible, contact-required, or unconfirmed record is outside this intake contract and must not produce an Opportunity Dossier.

### 6.3 Source object

Required shape:

```json
{
  "name": "PUBLIC_SALE_OPERATOR_OR_EVIDENCE_PACKAGE",
  "source_type": "PUBLIC_SALE_PAGE",
  "primary_url": "https://example.no/opportunity",
  "source_domain": "example.no",
  "evidence_refs": ["source-sale-page"]
}
```

Rules:

- `primary_url` must be HTTPS.
- `source_domain` must match the normalized hostname of `primary_url`.
- `evidence_refs` must contain at least one identifier present in `provenance.records`.
- Source names and types are descriptive values, not a fixed website allowlist.
- Authentication-only, private, invented, or non-traceable sources are not accepted as the sole confirmation evidence.

### 6.4 Field evidence envelope

Every required field uses this common envelope:

```json
{
  "value": null,
  "classification": "UNKNOWN",
  "evidence_refs": []
}
```

Allowed classifications:

```text
CONFIRMED_SOURCE_FACT
CONFIRMED_IMAGE_FACT
SELLER_CLAIM_UNVERIFIED
UNKNOWN
CONFLICTING_EVIDENCE
```

Required field keys:

```text
location
what_is_sold
quantity
asking_price_nok
contact
vat_statement
buyer_fees_nok
condition
pickup_terms
packing_terms
transport_terms
```

Additional optional field keys may include:

```text
sale_method
whole_or_partial_sale
inspection_availability
sale_deadline
brands
sizes
product_categories
inventory_list_reference
```

Rules:

- Every required key must be present even when its value is `null`.
- A `null` value normally requires `classification: UNKNOWN` and an empty `evidence_refs` list.
- A non-null value may not use `UNKNOWN`.
- `CONFIRMED_SOURCE_FACT`, `CONFIRMED_IMAGE_FACT`, and `SELLER_CLAIM_UNVERIFIED` require at least one valid evidence reference.
- `CONFLICTING_EVIDENCE` requires at least two valid evidence references and must not be silently resolved.
- `quantity.value` must be a positive integer or `null`; it may include `unit` such as `items`.
- `asking_price_nok.value` and `buyer_fees_nok.value` must be non-negative numbers or `null`; their currency is `NOK`.
- Missing values must never be converted to zero.

### 6.5 Supported inferences

Supported inferences remain separate from confirmed facts and seller claims.

Shape:

```json
{
  "field": "inventory_scope",
  "value": "Clothing and footwear are visibly relevant categories",
  "confidence": "MEDIUM",
  "reason": "Multiple public category and product pages support the category scope but not physical unit count",
  "evidence_refs": ["source-category-page", "source-product-page"]
}
```

Rules:

- Allowed confidence: `LOW`, `MEDIUM`, `HIGH`.
- A supported inference requires a non-empty reason and at least one evidence reference.
- An inference must not populate `quantity`, `asking_price_nok`, VAT, fees, or logistics as a confirmed value.
- Supported inferences remain in `OpportunityDossier.supported_inferences`.

### 6.6 Missing evidence and seller questions

`missing_evidence` is a non-empty list for an incomplete opportunity. It may include:

```text
verified inventory list
verified physical quantity
confirmed acquisition price or offer basis
VAT treatment
buyer fees
condition distribution
pickup deadline and removal terms
packing and loading information
transport requirements
verified market comparables
```

`seller_questions` may preserve a human-reviewed question list. The implementation may merge and deduplicate it with the existing generic dossier questions, but must not send it.

### 6.7 Provenance contract

Required shape:

```json
{
  "records": [
    {
      "evidence_id": "source-sale-page",
      "kind": "PUBLIC_WEB_PAGE",
      "url": "https://example.no/opportunity",
      "file_reference": null,
      "observed_at": "2026-07-27T12:00:00+00:00",
      "supports": [
        "opportunity_status",
        "listing_status",
        "title",
        "location"
      ]
    }
  ]
}
```

Allowed `kind` values:

```text
PUBLIC_WEB_PAGE
PUBLIC_COMPANY_RECORD
PUBLIC_BANKRUPTCY_RECORD
PUBLIC_IMAGE
PUBLIC_ATTACHMENT
HUMAN_VERIFIED_EVIDENCE_PACKAGE
```

Rules:

- `evidence_id` values must be unique.
- Every field and inference evidence reference must resolve to one record.
- A web-based record requires an HTTPS URL.
- A file-based record requires a preserved file reference.
- Every record requires a timezone-aware observation timestamp.
- Provenance must be copied to the output dossier without losing evidence identifiers.

### 6.8 Safety object

Required exact shape:

```json
{
  "automatic_purchase_decision": false,
  "automatic_bid": false,
  "automatic_contact": false,
  "automatic_reservation": false,
  "automatic_payment": false
}
```

Any `true` value makes the input invalid.

## 7. Intake mapping behavior

### 7.1 Validation first

The implementation must validate the complete input before creating a `DiscoveryCandidate`, `DiscoveryResult`, or Opportunity Dossier.

### 7.2 DiscoveryCandidate mapping

Map only compatible validated values:

```text
title          <- title
url            <- source.primary_url
source         <- source.name
discovered_at  <- observed_at
text           <- description or title
location       <- confirmed location value, otherwise null
quantity       <- confirmed or seller-claimed quantity value, otherwise null
price_nok      <- confirmed or seller-claimed asking-price value, otherwise null
contact        <- confirmed public contact value, otherwise null
```

Do not place estimates, conflicting values, or unsupported inferences into `DiscoveryCandidate`.

### 7.3 DiscoveryResult mapping

After successful validation, create a result directly:

```text
scenario: primary_scenario
record_type: SALE_LISTING
status: SALE_CONFIRMED
reason: confirmed active opportunity intake validated
evidence: stable referenced confirmation signals
```

Do not re-run the keyword classifier as the authority for the already-confirmed intake. The classifier remains unchanged for normal Discovery paths.

### 7.4 Dossier construction and enrichment

The implementation must:

1. call `build_opportunity_dossier` with the validated result;
2. preserve the supplied stable `opportunity_id`;
3. enrich the baseline dossier with all classified fields;
4. preserve confirmed source/image facts in `confirmed_facts`;
5. preserve seller claims in `seller_claims`;
6. preserve supported inferences separately;
7. populate `unknown_fields` from all `UNKNOWN` fields;
8. preserve conflicting evidence explicitly;
9. merge and deduplicate `missing_evidence` and seller questions;
10. preserve the complete provenance record set.

No input fact may be silently promoted to a stronger evidence class.

### 7.5 Eligibility behavior

Reuse `evaluate_analysis_eligibility` where compatible.

For the first implementation, confirmed-intake mode stops at the dossier and eligibility boundary. It does not invoke market comparables, acquisition-cost integration, financial analysis, scoring, or decision intelligence.

An incomplete valid opportunity must produce:

```text
opportunity_status: CONFIRMED_ACTIVE_CLOTHING_INVENTORY_OPPORTUNITY
dossier_status: DOSSIER_EVIDENCE_REQUIRED
final_outcome: EVIDENCE_REQUIRED
final_decision: NO_DECISION
retained_in_opportunity_report: true
analysis_invoked: false
market_analysis_invoked: false
acquisition_cost_analysis_invoked: false
scoring_invoked: false
decision_intelligence_invoked: false
```

The compatibility field `final_outcome: EVIDENCE_REQUIRED` remains unchanged while `dossier_status` carries the explicit dossier state.

The output must never set `REJECT` merely because decision evidence is incomplete.

## 8. Valid output contract

A successfully validated intake writes exactly:

```text
<output-dir>/opportunity-dossier.json
<output-dir>/final-report.json
<output-dir>/operator-summary.txt
```

### 8.1 opportunity-dossier.json

Must contain:

- supplied stable opportunity ID;
- domain and scenario;
- `SALE_CONFIRMED` qualification;
- confirmed facts;
- seller claims;
- supported inferences;
- unknown fields;
- missing evidence;
- seller questions;
- complete provenance.

### 8.2 final-report.json

Must contain at minimum:

```text
schema_version
execution_mode: CONFIRMED_DOSSIER_INTAKE
opportunity_status
dossier_status
final_outcome
final_decision
retained_in_opportunity_report
eligibility
dossier
analysis invocation flags
automatic commercial-action flags
```

No market value, expected profit, ROI, score, recommendation, or maximum bid field may be manufactured.

### 8.3 operator-summary.txt

The phone-readable summary must show:

```text
Opportunity title
Stable opportunity ID
Source and URL
Scenario
Opportunity status
Dossier status
Final decision: NO_DECISION
Quantity: value or unknown
Observed price NOK: value or unknown
Missing required evidence
Retained in opportunity report: yes
Automatic purchase/bid/contact/reservation/payment: false
```

## 9. Invalid and untraceable input behavior

The implementation must not manufacture a dossier from malformed, ended, unconfirmed, or untraceable input.

Structured validation statuses:

```text
INTAKE_VALIDATION_FAILED
INTAKE_REJECTED_UNTRACEABLE
INTAKE_REJECTED_NOT_ACTIVE
INTAKE_REJECTED_NOT_CONFIRMED
```

Behavior:

- return a structured validation outcome with explicit errors;
- exit the CLI with a non-zero status;
- do not write `opportunity-dossier.json`;
- do not write a normal `final-report.json` or normal operator summary;
- do not convert the validation failure into the investment decision `REJECT`;
- do not contact any source or seller to repair the input automatically.

## 10. Subsequent implementation scope

Exactly one implementation task may follow:

```text
CONFIRMED_CLOTHING_INVENTORY_DOSSIER_INTAKE_IMPLEMENTATION
```

Approved changed files:

```text
src/opportunity_engine/discovery/confirmed_dossier_intake.py
scripts/run_clothing_inventory_single_case.py
tests/test_confirmed_clothing_inventory_dossier_intake.py
tests/fixtures/confirmed_clothing_inventory_dossier_incomplete.json
```

No other file is approved for modification.

If implementation proves that `models.py`, `e2e_checkpoint.py`, a workflow, or an Analysis Engine component must change, work must stop and a separate compatibility task must be defined with repository evidence.

## 11. Focused test contract

The implementation test must prove:

1. a valid confirmed active incomplete opportunity is accepted;
2. the schema is source-agnostic and contains no named-source branching;
3. the supplied stable opportunity ID is preserved;
4. HTTPS source traceability and evidence references are preserved;
5. nullable quantity, price, contact, VAT, fees, condition, pickup, packing, and transport remain `null`/unknown;
6. the enriched dossier separates confirmed facts, seller claims, supported inferences, unknowns, conflicts, and missing evidence;
7. all three valid output files are written;
8. the opportunity remains retained in the final report;
9. the report contains `DOSSIER_EVIDENCE_REQUIRED`, `EVIDENCE_REQUIRED`, and `NO_DECISION` in their defined fields;
10. no `REJECT`, `WATCH`, `BUY_REVIEW`, score, profit, ROI, or maximum bid is produced;
11. analysis, scoring, decision intelligence, seller contact, bid, reservation, purchase, and payment remain false;
12. a non-HTTPS or unresolved source is rejected without a dossier;
13. an `ENDED` input is rejected without a dossier;
14. an unconfirmed input is rejected without a dossier;
15. unknown evidence references fail validation;
16. a `true` automatic-action safety flag fails validation;
17. confirmed-intake CLI mode is mutually exclusive with live-source modes;
18. the preserved and Auksjonen runner modes retain their existing behavior.

## 12. Required validation

The implementation PR must pass:

```bash
pytest tests/test_confirmed_clothing_inventory_dossier_intake.py -q
pytest tests/test_clothing_inventory_single_case_runner.py -q
pytest tests/test_e2e_clothing_inventory_checkpoint.py -q
pytest tests/test_live_clothing_candidate_ingestion.py -q
pytest tests/test_active_clothing_inventory_scan.py -q
```

The canonical repository regression suite must also pass.

## 13. Safety invariants

The implementation must preserve:

```text
automatic_purchase_decision: false
automatic_bid: false
automatic_contact: false
automatic_reservation: false
automatic_payment: false
```

It must also preserve:

- `BUY_REVIEW` always requires human approval in later eligible analysis stages;
- no seller contact is required to retain a confirmed opportunity in reporting;
- only explicitly confirmed active Clothing Inventory opportunities are accepted;
- ended or untraceable inputs do not produce dossiers;
- missing values remain `null` or explicitly unknown;
- evidence conflicts remain visible;
- source traceability is preserved;
- V2.8–V3.7 formulas and thresholds remain unchanged;
- no new source, domain, workflow, schedule, or automatic notification is introduced.

## 14. Out of scope

This task does not approve:

- sending the AXL evidence request;
- modifying Gmail or creating contact automation;
- scraping a new website;
- changing the Discovery classifier;
- changing the Opportunity Map;
- changing the existing Analysis Engine;
- automatically collecting market comparables;
- automatically estimating acquisition costs;
- producing investment decisions from incomplete dossier evidence;
- adding wedding dresses, sewing equipment, fabrics, store fixtures, or another domain;
- modifying any GitHub Actions workflow.

## 15. Definition of done

This planning task is complete only when:

1. this is the only file changed in the task-definition PR;
2. one versioned source-agnostic JSON input contract is defined;
3. required, nullable, classified, and provenance fields are exact;
4. existing candidate, dossier, eligibility, report, and summary boundaries are inventoried and reused where compatible;
5. incomplete confirmed opportunities remain retained with `DOSSIER_EVIDENCE_REQUIRED / NO_DECISION`;
6. malformed, ended, unconfirmed, and untraceable inputs do not manufacture a dossier;
7. no financial analysis or automatic commercial action is authorized;
8. exactly one implementation task and exact file scope are identified;
9. focused and canonical tests are required;
10. all repository checks pass.
