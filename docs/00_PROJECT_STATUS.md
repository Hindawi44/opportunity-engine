# Opportunity Engine — Project Status

**Last updated:** 2026-07-27  
**Status:** ACTIVE  
**Authoritative repository:** `Hindawi44/opportunity-engine`

## Session startup rule

Every development session must begin by reading, in this order:

1. `docs/00_PROJECT_STATUS.md`
2. `docs/Opportunity_Discovery_Analysis_Blueprint_v2.0.md`
3. `docs/REPOSITORY_ARCHITECTURE_AUDIT_v2.0.md`
4. The current-task document named below, when one is approved

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
  -> Verified Market Comparables
  -> Verified Acquisition Costs
  -> Existing Analysis Engine
  -> Opportunity Score
  -> Decision Intelligence
  -> Final Investment Report or Evidence-Required Outcome
```

Canonical investment decisions are:

```text
BUY_REVIEW / WATCH / REJECT
```

`BUY_REVIEW` is a human-review state only. It is never an automatic purchase instruction.

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

No new domain implementation is approved until the Clothing Inventory live path accepts repeated real opportunities through a general dossier-intake and reporting contract.

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
- Wave 3A–3F workflow ownership and path-scoping work completed through PR #283.
- Wave 4 Historical Diagnostics completed through Wave 4L; Wave 4D–4L remain retained as `NOT_READY` where recorded.
- Workflow-simplification checkpoint accepted in PR #285.
- Clothing Inventory single-case execution task definition merged in PR #286.

## Accepted Clothing Inventory product implementation

The product-facing implementation sequence is complete through active-scan operation and source-review evidence:

- PR #287 added the deterministic Clothing Inventory single-case end-to-end runner and focused tests.
- PR #288 added live Auksjonen Clothing Inventory candidate ingestion.
- PR #289 integrated verified market comparables through the existing V2.8 contract.
- PR #290 integrated verified acquisition-cost evidence through the existing V2.9/V2.10 contracts.
- PR #291 connected the single case to the existing opportunity scoring and canonical decision-intelligence policy.
- PR #292 stored and executed the first public Clothing Inventory investment report; its honest decision was `WATCH` because acquisition-cost evidence remained incomplete.
- PR #293 preserved Auksjonen listing status and prohibited ended listings from entering the live candidate path.
- PR #294 added an operational live scan result for the case where no active Clothing Inventory candidate exists.
- PR #295 reconciled project status after the first live product cycle.
- PR #296 defined the active Clothing Inventory operator-integration task.
- PR #297 integrated the active scan into `1 — Discover Clothing Inventory Opportunities` with the approved manual choices.
- PR #298 defined the Auksjonen live-extraction compatibility correction.
- PR #299 corrected current Auksjonen URL, price, listing-link, and source-verification behavior.
- PR #300 defined extracted-listing review evidence.
- PR #301 added `extracted-listings.json` for transparent review of every parsed listing and classifier match.

## Accepted operator surface

```text
1 — Discover Clothing Inventory Opportunities
2 — Review One Opportunity End to End
```

The Discovery workflow now exposes two manual operations:

```text
brave_discovery
active_clothing_scan
```

The active scan is integrated and operational. It:

- runs `scripts/run_active_clothing_inventory_scan.py`;
- preserves `ACTIVE_CANDIDATE_SELECTED`;
- preserves `NO_ACTIVE_CANDIDATE / NO_DECISION` as a successful result;
- preserves `SOURCE_EXTRACTION_UNVERIFIED` when a zero parse is not verified;
- prints an operator summary;
- uploads the complete scan artifact directory;
- does not require `BRAVE_SEARCH_API_KEY`;
- adds no schedule or automatic execution.

The V3.7 review workflow remains separate and manual-only.

## Accepted Clothing Inventory result

The merged implementation proves:

- one public Clothing Inventory candidate can be preserved with source traceability;
- a candidate can be classified using the approved Opportunity Map;
- an Opportunity Dossier can be produced without inventing missing facts;
- explicitly verified market comparables can be evaluated without inventing market value;
- explicitly verified acquisition-cost components can be integrated without treating missing values as zero;
- the existing financial engine can calculate true acquisition cost, conservative resale value, expected profit, and ROI when evidence is complete;
- the existing scoring and decision-intelligence contracts can produce `BUY_REVIEW`, `WATCH`, or `REJECT` when eligible evidence reaches Analysis;
- incomplete evidence produces an honest evidence-required result and must not be treated as an economic rejection;
- ended listings cannot be promoted as live opportunities;
- a verified scan with no active Clothing Inventory listing produces `NO_ACTIVE_CANDIDATE` and `NO_DECISION`;
- an unverified zero extraction produces `SOURCE_EXTRACTION_UNVERIFIED` rather than a false no-candidate claim;
- no automatic purchase, bid, contact, payment, or financial action occurs.

## AXL real-opportunity validation chain

The repository now contains the first confirmed active Clothing Inventory opportunity discovered outside the narrow Auksjonen live-listing path:

```text
AXL Sport og Fritid Kolvereid AS konkursbo
```

Accepted sequence:

- PR #302 recorded the first active AXL Clothing Inventory lead and its evidence gate.
- PR #303 verified the active sale, company identity, clothing/footwear relevance, location, public sources, and contact traceability.
- PR #304 created the complete AXL Opportunity Dossier.
- PR #305 prepared a human-reviewable evidence-request package but did not send it.

Canonical AXL state:

```text
CONFIRMED_ACTIVE_CLOTHING_INVENTORY_OPPORTUNITY
DOSSIER_EVIDENCE_REQUIRED
NO_DECISION
```

AXL must remain visible in opportunity reporting while active. Missing quantity, acquisition price, VAT, fees, condition, pickup, packing, or transport evidence is not a rejection reason.

The evidence-request package is a reusable documentation template. It does not require contact with AXL in order to continue building the product, and it does not authorize automatic contact.

## Confirmed product gap

The repository already contains a reusable `DiscoveryCandidate -> OpportunityDossier -> EVIDENCE_REQUIRED` code path. It also contains a source-specific live Auksjonen runner.

The missing product capability is a general, machine-readable intake route for a confirmed active Clothing Inventory opportunity such as AXL when the opportunity is discovered through another public route or human-verified evidence package.

Current limitations:

- `scripts/run_clothing_inventory_single_case.py` accepts only the preserved case or the Auksjonen live page;
- AXL evidence is preserved in documentation but is not yet consumable as a structured program input;
- no general operator output proves that a confirmed dossier with incomplete decision evidence remains retained in the final report with `NO_DECISION`;
- the program must not require contacting the seller before it can record and report the opportunity.

## Current phase

**Phase:** Confirmed Clothing Inventory Dossier Intake and Report Retention  
**Status:** `ACTIVE`

The next product milestone is to make the AXL pattern reusable without hard-coding AXL and without adding a new domain or source-specific architecture.

## Current implementation checkpoint

```text
CONFIRMED_CLOTHING_INVENTORY_DOSSIER_INTAKE_TASK_DEFINITION
```

Status: `NEXT`

Current task document:

```text
Not yet approved. Create one planning-only task document that defines the minimum safe machine-readable intake of one confirmed active Clothing Inventory opportunity into the existing single-case dossier and reporting boundary.
```

The task must remain source-agnostic. AXL is the validation example, not a hard-coded product rule.

## Required task contract

The task definition must specify:

1. one versioned JSON input contract for a confirmed active Clothing Inventory opportunity;
2. required source identity, scenario, status, title, URL, observation time, location, and evidence provenance fields;
3. nullable quantity, price, contact, VAT, fees, condition, pickup, packing, and transport fields;
4. explicit classification of confirmed facts, seller claims, supported inferences, unknowns, and missing evidence;
5. reuse of the existing `DiscoveryCandidate`, `build_opportunity_dossier`, `evaluate_analysis_eligibility`, final-report, and operator-summary boundaries where compatible;
6. exact outputs:

```text
opportunity-dossier.json
final-report.json
operator-summary.txt
```

7. a retained incomplete-opportunity state:

```text
CONFIRMED_ACTIVE_CLOTHING_INVENTORY_OPPORTUNITY
DOSSIER_EVIDENCE_REQUIRED
NO_DECISION
```

8. no invocation of market, acquisition-cost, scoring, or decision intelligence while eligibility evidence is incomplete;
9. no conversion of incomplete evidence into `REJECT`;
10. focused tests proving both a dossier-ready incomplete opportunity and a malformed/untraceable input outcome;
11. no workflow modification in the planning-only PR;
12. exactly one subsequent implementation task.

## Non-negotiable rules

- Do not delete existing production code.
- Do not modify V2.8–V3.7 financial formulas unless a verified compatibility defect exists.
- Do not add a new domain.
- Do not hard-code the product around AXL, Auksjonen, FINN, or another named source.
- Do not invent missing values.
- Preserve source traceability.
- Do not require seller contact to preserve an active confirmed opportunity in reporting.
- Do not make an automatic purchase, bid, contact, reservation, payment, or financial decision.
- `BUY_REVIEW` always requires human approval.
- Do not modify, run, disable, archive, rename, relocate, or delete a workflow until a separately approved task permits it.
- Select or change only one task in a single PR.
- Repository-setting facts and external consumers not visible in tracked files remain `MANUAL_VERIFICATION_REQUIRED`.
- Do not create another cleanup wave unless a concrete blocker is established with repository evidence.
- Do not promote an `ENDED` listing as a live opportunity.
- Do not manufacture an Opportunity Dossier when no traceable confirmed opportunity exists.

## Definition of current-task success

The dossier-intake task-definition PR succeeds only when:

1. exactly one planning-only task document is created;
2. the input is general and source-agnostic;
3. the input contract preserves public-source and evidence provenance;
4. incomplete quantity, price, VAT, fees, logistics, and market evidence remain explicitly unknown;
5. the opportunity remains visible in final and operator reports;
6. incomplete evidence results in `DOSSIER_EVIDENCE_REQUIRED / NO_DECISION`, not `REJECT`;
7. existing Analysis Engine formulas and thresholds remain unchanged;
8. no workflow, production code, test, fixture, state, cache, report, artifact, source adapter, or automatic commercial behavior is modified in the planning-only PR;
9. exactly one subsequent implementation task is identified;
10. all repository checks pass.

## Immediate next action

Execute the dossier-intake task definition only:

1. create `docs/CONFIRMED_CLOTHING_INVENTORY_DOSSIER_INTAKE_TASK_v1.0.md`;
2. inventory the existing `DiscoveryCandidate`, dossier, eligibility, final-report, and operator-summary contracts;
3. define the versioned machine-readable input schema;
4. define exact validation and evidence-classification behavior;
5. define retained reporting for incomplete active opportunities;
6. prohibit seller contact and financial analysis as prerequisites for report retention;
7. identify exactly one subsequent implementation PR.
