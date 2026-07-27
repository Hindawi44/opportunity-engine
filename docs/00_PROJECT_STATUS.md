# Opportunity Engine — Project Status

**Last updated:** 2026-07-27  
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

No new domain implementation is approved until the Clothing Inventory path repeatedly discovers specific traceable opportunities and completes the dossier and reporting cycle.

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
- PR #308 implemented confirmed dossier intake with retained `DOSSIER_EVIDENCE_REQUIRED / NO_DECISION` reporting.
- PR #309 added the confirmed-dossier post-merge correction task document.
- PR #310 implemented the structured sixteen-query Clothing Inventory Discovery search.
- PR #311 integrated `structured_clothing_discovery` into the manual operator workflow.
- The first live structured Discovery run completed successfully and produced reviewable artifacts.
- That live run exposed five verification-integrity false positives; none was approved for dossier intake.
- PR #312 defined the bounded Discovery verification-integrity correction task.

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

## First structured live-run finding

The live run proved:

- all sixteen queries executed;
- broad search coverage works;
- duplicate merging works;
- four artifacts are produced;
- the operator workflow works;
- no financial ranking or commercial action occurs.

It also proved that the previous verifier could:

- combine unrelated fields from category pages;
- treat ordinary stores as bankruptcy opportunities;
- treat source portals as opportunities;
- extract `0 NOK` from shopping-cart context;
- promote unknown or unresolved pages too aggressively.

Therefore:

```text
No candidate from the first live discovery-top5.json is approved for Opportunity Dossier intake.
```

## Current phase

**Phase:** Clothing Inventory Discovery Verification Integrity Correction  
**Status:** `IN_IMPLEMENTATION`

## Current implementation checkpoint

```text
CLOTHING_INVENTORY_DISCOVERY_VERIFICATION_INTEGRITY_CORRECTION_IMPLEMENTATION
```

Current task document:

```text
docs/CLOTHING_INVENTORY_DISCOVERY_VERIFICATION_INTEGRITY_CORRECTION_TASK_v1.0.md
```

## Current implementation contract

The implementation must:

1. assign each verified page exactly one role:

```text
ITEM_LISTING
CATEGORY_INDEX
SOURCE_CHANNEL
ORDINARY_STORE
ARTICLE_OR_INFO
UNRESOLVED_SOURCE
```

2. require stable opportunity identity before confirmation;
3. extract price, quantity, location, inventory type, sale evidence, and status from one bounded listing context;
4. reject zero-value cart and placeholder prices;
5. prevent query-scenario leakage;
6. require all confirmation conditions for `CONFIRMED_SALE`;
7. allow `UNKNOWN` only for a specific listing retained as `STRONG_LEAD_REQUIRES_VERIFICATION`;
8. exclude category pages, source channels, ordinary stores, information pages, and unresolved generic sources from Top 5;
9. output up to five valid opportunities rather than filling the list with weak records;
10. separate execution health from opportunity-quality status;
11. retain all commercial-safety boundaries.

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

Search snippets alone cannot confirm a sale.

## Approved implementation scope

Only these paths may change in the current implementation PR:

```text
src/opportunity_engine/discovery/clothing_inventory_search.py
tests/test_clothing_inventory_discovery_search.py
tests/fixtures/clothing_inventory_discovery_verification/
docs/00_PROJECT_STATUS.md
```

## Required regression outcomes

- Auksjonen category page -> `CATEGORY_INDEX`, no cross-combined fields, not Top 5.
- Proffsport-style ordinary store -> `ORDINARY_STORE`, no bankruptcy inheritance, no `0 NOK` price.
- AltPåSalg-style buyer/reseller -> `SOURCE_CHANNEL`, not an opportunity.
- Specific motorcycle-clothing listing shell -> unresolved status, never confirmed.
- Konkursnett-style portal timeout -> no promotion and no Top 5 entry.
- One valid active specific Clothing Inventory listing -> `CONFIRMED_SALE`.
- Ended listing -> historical only.
- Fewer than five valid listings -> fewer than five Top 5 records.
- Zero valid listings -> honest empty Top 5.

## Report contract after correction

`search-run-report.json` must separately report:

```text
execution_status
opportunity_quality_status
top5_eligible_count
generic_pages_excluded
verification_failures
false_positive_guard_triggered
```

The compatibility field `status` reflects execution health only.

## Non-negotiable rules

- Do not modify the sixteen-query matrix.
- Do not add a new opportunity domain.
- Do not modify Brave credentials or provider behavior.
- Do not modify workflows in this task.
- Do not modify the Opportunity Dossier contract.
- Do not modify confirmed-dossier intake.
- Do not modify market-comparable or acquisition-cost logic.
- Do not modify V2.8–V3.7 financial formulas.
- Do not modify investment scoring or decision intelligence.
- Do not invent price, quantity, company, location, or active status.
- Do not contact sellers.
- Do not bid, reserve, purchase, or pay.
- Do not add schedules or automatic execution.
- Do not hard-code production behavior around named websites; named cases are regression examples only.

## Definition of current-task success

The implementation succeeds only when:

1. all mandatory focused tests pass;
2. all repository checks pass;
3. the five live false-positive cases produce conservative outcomes;
4. category pages and source channels cannot enter Top 5;
5. ordinary stores cannot inherit bankruptcy confirmation from search queries;
6. commercial fields come from one bounded listing context;
7. `UNKNOWN` never becomes `CONFIRMED_SALE`;
8. Top 5 may contain fewer than five records;
9. execution success is separate from opportunity-quality success;
10. no Analysis Engine or commercial-action boundary is crossed.

## Immediate next action

Complete and merge the current correction implementation PR only after all checks pass.

Then manually rerun:

```text
1 — Discover Clothing Inventory Opportunities
operation = structured_clothing_discovery
```

Inspect:

```text
search-run-report.json
all-discovered-candidates.json
discovery-top5.json
operator-summary.txt
```

Only a specific traceable candidate that passes the corrected gate may proceed to the existing Opportunity Dossier boundary. An empty result is acceptable and must not be replaced with an invented opportunity.
