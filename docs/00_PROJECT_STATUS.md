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
- PR #313 implemented the fail-closed verification-integrity correction.
- PR #314 added the source-channel identity guard.
- PR #315 separated Discovery Top 5 eligibility from Analysis eligibility and
  restored traceable early event leads.
- PR #316 rejected mixed non-clothing inventory shells.
- PR #317 added Norwegian Clothing Inventory lot vocabulary and preserved
  distinct stable listing identities.

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

**Phase:** Authorized FINN Playwright Collection Pilot
**Status:** `IN_IMPLEMENTATION`

## Current implementation checkpoint

```text
FINN_PLAYWRIGHT_PILOT_ADAPTER_v1.0
```

Current task document:

```text
docs/FINN_PLAYWRIGHT_PILOT_ADAPTER_TASK_v1.0.md
```

## Current implementation contract

The implementation must:

1. remain limited to `CLOTHING_INVENTORY`;
2. act only as a replaceable Discovery collection adapter;
3. require an explicit written FINN automation-permission reference before any
   browser launch;
4. collect only 20–50 public listings per manual run;
5. enforce a delay of at least two seconds between public-page visits;
6. accept only public HTTPS FINN Torget search and item URLs;
7. collect title, URL, description, verified price and location when available,
   public image URLs, listing status, stable listing ID, capture time, and search
   URL;
8. preserve unavailable values as `null`;
9. pass rendered pages through the existing bounded Clothing Inventory verifier;
10. write the existing four Discovery artifacts plus one raw collection artifact;
11. preserve all Analysis Engine and commercial-safety boundaries.

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

```text
src/opportunity_engine/discovery/finn_playwright_pilot.py
scripts/run_finn_playwright_clothing_pilot.py
tests/test_finn_playwright_clothing_pilot.py
requirements-playwright.txt
docs/FINN_PLAYWRIGHT_PILOT_ADAPTER_TASK_v1.0.md
docs/00_PROJECT_STATUS.md
```

## Required regression outcomes

- missing written-permission reference -> execution blocked before browser launch;
- fewer than 20 or more than 50 requested listings -> rejected configuration;
- delay below two seconds -> rejected configuration;
- non-FINN or non-search seed URL -> rejected configuration;
- duplicate FINN listing IDs -> one collected record;
- rendered page verification failure -> unresolved lead, never confirmed sale;
- public image URLs -> retained with the Discovery candidate;
- existing Discovery report fields and safety flags -> retained.

## Non-negotiable rules

- Do not modify the sixteen-query matrix.
- Do not add a new opportunity domain.
- Do not modify Brave credentials or provider behavior.
- Do not add or modify workflows, schedules, or automatic execution in this task.
- Do not modify the Opportunity Dossier contract.
- Do not modify confirmed-dossier intake.
- Do not modify market-comparable or acquisition-cost logic.
- Do not modify V2.8–V3.7 financial formulas.
- Do not modify investment scoring or decision intelligence.
- Do not invent price, quantity, company, location, or active status.
- Do not contact sellers.
- Do not bid, reserve, purchase, or pay.
- Do not log in, import session cookies, rotate proxies, bypass CAPTCHA, or bypass
  access controls.
- Do not run the FINN pilot without explicit written permission from FINN.

## Definition of current-task success

The implementation succeeds only when:

1. all mandatory focused tests pass;
2. all repository checks pass;
3. authorization and volume gates fail closed;
4. Playwright remains an optional dependency;
5. the pilot supports 20–50 listings without changing the sixteen-query matrix;
6. rendered public evidence uses the existing verifier;
7. images and capture provenance remain traceable;
8. `UNKNOWN` never becomes `CONFIRMED_SALE`;
9. no live FINN collection is performed during implementation or CI;
10. no Analysis Engine or commercial-action boundary is crossed.

## Immediate next action

Complete and merge the bounded adapter only after all checks pass. Do not run the
live FINN pilot until explicit written automation permission exists. Once it
exists, run one manual 20-listing pilot, inspect all five artifacts, and pass only
a confirmed, traceable specific listing to the existing Opportunity Dossier
boundary. An empty result is acceptable and must not be replaced with an
invented opportunity.
