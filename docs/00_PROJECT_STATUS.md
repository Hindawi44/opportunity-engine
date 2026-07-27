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

No new domain implementation is approved until the Clothing Inventory live path repeatedly discovers traceable real opportunities, preserves incomplete evidence honestly, and completes the approved dossier and reporting cycle.

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

The product-facing implementation sequence is complete through active-scan operation, confirmed dossier intake, and structured discovery-search implementation:

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
- PR #307 defined the source-agnostic confirmed Clothing Inventory dossier-intake contract.
- PR #308 implemented confirmed dossier intake with retained `DOSSIER_EVIDENCE_REQUIRED / NO_DECISION` reporting.
- PR #310 implemented the structured sixteen-query Clothing Inventory Discovery search, three-state qualification, multi-source merging, bounded public-page verification, discovery-only scoring, and top-five artifacts.

Draft PR #309 remains deferred and must not be merged or mixed into the current Discovery task.

## Accepted operator surface

```text
1 — Discover Clothing Inventory Opportunities
2 — Review One Opportunity End to End
```

Before the current integration PR, the Discovery workflow exposes two manual operations:

```text
brave_discovery
active_clothing_scan
```

The current task adds exactly one third manual operation:

```text
structured_clothing_discovery
```

The three operations remain mutually exclusive. No schedule or automatic execution is added.

The structured operation must:

- run `scripts/run_clothing_inventory_discovery_search.py`;
- use `BRAVE_SEARCH_API_KEY` only from GitHub Secrets;
- enable bounded public-page verification;
- print `artifacts/clothing-inventory-discovery/operator-summary.txt`;
- upload the complete `artifacts/clothing-inventory-discovery/` directory;
- preserve the Discovery/Analysis separation.

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
- a structured Discovery run can retain `CONFIRMED_SALE` and `STRONG_LEAD_REQUIRES_VERIFICATION` candidates without using financial ranking;
- missing price or quantity does not delete a traceable opportunity;
- no automatic purchase, bid, contact, payment, or financial action occurs.

## AXL real-opportunity validation chain

The repository contains the first confirmed active Clothing Inventory opportunity discovered outside the narrow Auksjonen live-listing path:

```text
AXL Sport og Fritid Kolvereid AS konkursbo
```

Accepted sequence:

- PR #302 recorded the first active AXL Clothing Inventory lead and its evidence gate.
- PR #303 verified the active sale, company identity, clothing/footwear relevance, location, public sources, and contact traceability.
- PR #304 created the complete AXL Opportunity Dossier.
- PR #305 prepared a human-reviewable evidence-request package but did not send it.
- PR #307 defined general confirmed-dossier intake.
- PR #308 implemented the source-agnostic intake route.

Canonical AXL state:

```text
CONFIRMED_ACTIVE_CLOTHING_INVENTORY_OPPORTUNITY
DOSSIER_EVIDENCE_REQUIRED
NO_DECISION
```

AXL remains a validation example, not a hard-coded product rule. Missing quantity, acquisition price, VAT, fees, condition, pickup, packing, or transport evidence is not a rejection reason.

## Current product gap

The structured search implementation is merged, but it is not yet exposed as an operator choice in the primary Discovery workflow and has not yet completed its first live run through that operator surface.

The current gap is therefore operational, not architectural:

```text
merged structured Discovery search
  -> operator workflow choice
  -> live Brave run
  -> discovery-top5.json inspection
  -> strongest traceable active candidate
  -> existing Opportunity Dossier boundary
```

## Current phase

**Phase:** Structured Clothing Inventory Discovery Operator Integration and Live Validation  
**Status:** `ACTIVE`

## Current implementation checkpoint

```text
CLOTHING_INVENTORY_DISCOVERY_OPERATOR_INTEGRATION
```

Status: `IN_IMPLEMENTATION`

Current task document:

```text
docs/CLOTHING_INVENTORY_DISCOVERY_OPERATOR_INTEGRATION_v1.0.md
```

## Current task contract

The task must:

1. add `structured_clothing_discovery` to the existing manual Discovery operation choices;
2. keep all three Discovery operations mutually exclusive;
3. run `scripts/run_clothing_inventory_discovery_search.py --verify-pages`;
4. use `BRAVE_SEARCH_API_KEY` only from GitHub Secrets;
5. preserve the exact four-file artifact contract;
6. print the operator summary for phone review;
7. upload the complete artifact directory;
8. add focused workflow-contract tests;
9. add no schedule or automatic execution;
10. leave the Analysis Engine and review workflow unchanged.

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
- Select or change only one task in a single PR.
- Repository-setting facts and external consumers not visible in tracked files remain `MANUAL_VERIFICATION_REQUIRED`.
- Do not create another cleanup wave unless a concrete blocker is established with repository evidence.
- Do not promote an `ENDED` listing as a live opportunity.
- Do not manufacture an Opportunity Dossier when no traceable confirmed opportunity exists.
- Do not use ROI, expected profit, maximum bid, or investment decisions to rank initial Discovery candidates.

## Definition of current-task success

The operator-integration PR succeeds only when:

1. exactly three manual Discovery choices are present;
2. the structured choice invokes only the structured Discovery runner;
3. the runner receives the Brave key from GitHub Secrets;
4. public-page verification remains bounded and public-only;
5. the four artifacts are uploaded together;
6. the operator summary is printed;
7. the existing active scan and legacy Brave operation remain intact;
8. the review workflow remains separate;
9. focused and repository checks pass;
10. no automatic commercial behavior is added.

## Immediate next action

Complete and merge the current operator-integration PR, then manually run:

```text
1 — Discover Clothing Inventory Opportunities
operation = structured_clothing_discovery
```

Inspect:

```text
artifacts/clothing-inventory-discovery/discovery-top5.json
```

Select the strongest traceable active result and pass only that result to the existing Opportunity Dossier boundary. If no qualifying active opportunity exists, retain the honest no-opportunity result and do not invent one.
