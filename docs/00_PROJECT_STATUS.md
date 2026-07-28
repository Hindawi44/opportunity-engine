# Opportunity Engine — Project Status

**Last updated:** 2026-07-28  
**Status:** ACTIVE  
**Authoritative repository:** `Hindawi44/opportunity-engine`

## Session startup rule

Every development session must begin by reading, in this order:

1. `docs/00_PROJECT_STATUS.md`
2. `docs/Opportunity_Discovery_Analysis_Blueprint_v2.0.md`
3. `docs/REPOSITORY_ARCHITECTURE_AUDIT_v2.0.md`
4. The current-task document named below

The repository is the source of truth.

## Product principle

The project has two independent engines:

- **Discovery Engine:** discovers and verifies traceable opportunities.
- **Analysis Engine:** analyzes confirmed opportunities.

Neither engine may perform the other engine's responsibility.

The bridge between them is the **Opportunity Dossier**.

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

Canonical investment decisions remain:

```text
BUY_REVIEW / WATCH / REJECT
```

`BUY_REVIEW` is a human-review state only.

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

No new domain implementation is approved until the Clothing Inventory path
repeatedly discovers specific traceable opportunities and completes the dossier
and reporting cycle.

## Completed and retained

- Blueprint v2.0 approved.
- Repository Architecture Audit v2.0 merged.
- Existing Analysis Engine V2.8–V3.7 retained and frozen.
- Clothing Inventory selected as the reference MVP domain.
- Opportunity Dossier specification approved.
- All ten Clothing Inventory knowledge cards approved and merged.
- Controlled end-to-end and real-case validations completed through PR #208.
- Operator workflow cleanup and ownership work completed through PR #285.
- Clothing Inventory single-case execution task merged in PR #286.
- PR #287–#301 implemented and hardened the first Clothing Inventory live path.
- PR #302–#305 preserved and verified the AXL real-opportunity validation chain.
- PR #307 defined source-agnostic confirmed dossier intake.
- PR #308 implemented confirmed dossier intake with retained
  `DOSSIER_EVIDENCE_REQUIRED / NO_DECISION` reporting.
- PR #310 implemented the structured sixteen-query Clothing Inventory Discovery
  search.
- PR #311 integrated `structured_clothing_discovery` into the manual operator
  workflow.
- PR #313 implemented the fail-closed verification-integrity correction.
- PR #314 added the source-channel identity guard.
- PR #315 separated Discovery Top 5 eligibility from Analysis eligibility and
  restored traceable early event leads.
- PR #316 rejected mixed non-clothing inventory shells.
- PR #317 added Norwegian Clothing Inventory lot vocabulary and preserved
  distinct stable listing identities.
- PR #318 added the authorization-gated FINN Playwright pilot; live use remains
  frozen without explicit written FINN permission.
- PR #319 added the FINN saved-search email intake adapter.
- PR #320 recognized explicit unavailable Auksjonen listings as ended.
- PR #321 rejected the Storegutter retail catalogue false positive.
- PR #322 corrected Brave Norwegian request handling.
- PR #323 added the final post-verification Top 5 hard gate.
- The post-merge live validation for PR #323 completed successfully with:

```text
execution_status = PASS
post_verification_top5_hard_gate_applied = true
top5_count = 0
analysis_eligible_count = 0
opportunity_quality_status = NO_VALID_OPPORTUNITIES
```

An empty Top 5 is an accepted safe outcome.

## Accepted operator surface

```text
1 — Discover Clothing Inventory Opportunities
2 — Review One Opportunity End to End
```

The Discovery workflow exposes three mutually exclusive manual operations:

```text
brave_discovery
active_clothing_scan
structured_clothing_discovery
```

No schedule or automatic execution is added.

## Current phase

**Phase:** Brave Search precision improvement  
**Status:** `DRAFT_PR_CI_GREEN`

## Current implementation checkpoint

```text
BRAVE_PRECISION_DISCOVERY_v1.0
```

Current task document:

```text
docs/BRAVE_PRECISION_DISCOVERY_TASK_v1.0.md
```

Current pull request:

```text
PR #324 — Improve Brave Clothing Inventory search precision
```

## Current implementation contract

The implementation must:

1. remain limited to `CLOTHING_INVENTORY`;
2. preserve all sixteen approved query IDs, scenarios, intents, asset scope, and
   rotation groups;
3. improve only the pre-verification Brave retrieval surface;
4. support Brave freshness presets and valid custom date ranges;
5. enable Brave search operators explicitly for structured discovery;
6. enable bounded extra snippets and deduplicate them before classification;
7. exclude predictable buyer-intent, job, ordinary-shop, generic-content, and
   stale-listing noise where appropriate;
8. default structured discovery to `freshness=pm`, with manual selection of
   `pd`, `pw`, `pm`, or `py`;
9. record the active Brave precision settings in the search-run artifact;
10. preserve all verification, dossier, Analysis Engine, and commercial-safety
    boundaries.

## Strict confirmation conjunction

`CONFIRMED_SALE` requires:

```text
page_role == ITEM_LISTING
AND stable opportunity identity
AND bounded clothing-inventory evidence
AND bounded sale evidence
AND listing_status == ACTIVE
AND successful public verification
```

Search snippets, including Brave extra snippets, cannot confirm a sale by
themselves.

## Approved implementation scope

```text
src/opportunity_engine/discovery/brave_search.py
src/opportunity_engine/discovery/brave_precision.py
scripts/run_clothing_inventory_discovery_search.py
tests/test_discovery_v11_live_search.py
tests/test_brave_precision.py
tests/test_active_clothing_inventory_operator_integration.py
.github/workflows/discovery-v1.2-live-pilot.yml
docs/BRAVE_PRECISION_DISCOVERY_TASK_v1.0.md
docs/00_PROJECT_STATUS.md
```

## Validation status

PR #324 checks are green:

```text
782 passed
Discovery V1.1 Live Search Adapter = success
1 — Discover Clothing Inventory Opportunities = success
Full repository test workflow = success
```

## Non-negotiable rules

- Do not add a new opportunity domain.
- Do not add a new source or browser collector in this task.
- Do not change the canonical sixteen-query scenario structure.
- Do not weaken page verification, the early-opportunity gate, or the
  post-verification Top 5 hard gate.
- Do not modify the Opportunity Dossier contract.
- Do not modify confirmed-dossier intake.
- Do not modify market-comparable or acquisition-cost logic.
- Do not modify V2.8–V3.7 financial formulas.
- Do not modify investment scoring or decision intelligence.
- Do not invent price, quantity, company, location, or active status.
- Do not add a schedule or automatic execution.
- Do not contact sellers.
- Do not bid, reserve, purchase, or pay.
- Do not run the Playwright pilot without explicit written permission from FINN.

## Definition of current-task success

The task succeeds only when:

1. all focused and repository-wide checks pass;
2. freshness validation fails closed for unsupported or invalid values;
3. the structured operation sends the selected freshness window,
   `extra_snippets=true`, and `operators=true`;
4. extra snippets remain bounded and deduplicated;
5. all sixteen query contracts remain unchanged;
6. the final verification and Top 5 boundaries remain unchanged;
7. a post-merge live run produces the existing four artifacts;
8. the live report records the Brave precision configuration;
9. the new run is compared against the baseline of 109 merged candidates and
   108 rejected results;
10. no opportunity proceeds to a dossier unless the strict confirmation
    conjunction passes.

## Immediate next action

Review and merge PR #324 only while all checks remain green. Then manually run:

```text
operation = structured_clothing_discovery
```

Inspect the four artifacts and compare retrieval efficiency against the previous
baseline. A lower result count is not automatically better; the goal is fewer
predictable false positives while preserving any genuine specific active sale.
An empty Top 5 remains valid and must not be replaced with an invented
opportunity.
