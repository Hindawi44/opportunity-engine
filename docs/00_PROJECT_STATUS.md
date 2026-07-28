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

**Phase:** FINN Saved-Search Email Intake Pilot
**Status:** `IN_IMPLEMENTATION`

## Current implementation checkpoint

```text
FINN_SAVED_SEARCH_EMAIL_INTAKE_ADAPTER_v1.0
```

Current task document:

```text
docs/FINN_SAVED_SEARCH_EMAIL_INTAKE_ADAPTER_TASK_v1.0.md
```

## Current implementation contract

The implementation must:

1. remain limited to `CLOTHING_INVENTORY`;
2. act only as a replaceable Discovery collection adapter;
3. parse only operator-supplied messages from `agent@finn.no` with a FINN
   new-advert subject;
4. decode FINN tracking URLs locally without following them;
5. accept only stable FINN item IDs and reject control/search links;
6. deduplicate stable listing IDs;
7. retain email price and location only as unverified source claims;
8. mark symbolic prices such as `1 kr` or request/contact wording;
9. keep every accepted lead at `STRONG_LEAD_REQUIRES_VERIFICATION`;
10. keep `analysis_eligible=false` until the existing manual verification
    boundary passes;
11. write the existing four Discovery artifacts plus one sanitized intake
    artifact;
12. preserve all Analysis Engine and commercial-safety boundaries.

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
src/opportunity_engine/discovery/finn_email_intake.py
scripts/run_finn_email_intake.py
tests/test_finn_email_intake.py
docs/FINN_SAVED_SEARCH_EMAIL_INTAKE_ADAPTER_TASK_v1.0.md
docs/decisions/DECISION_002_FINN_SAVED_SEARCH_EMAIL_INTAKE.md
docs/MASTER_BLUEPRINT.md
README.md
docs/00_PROJECT_STATUS.md
```

## Required regression outcomes

- wrong sender or non-alert subject -> rejected message;
- FINN click-tracking and direct item links -> one stable record;
- saved-search, unsubscribe, edit, and help links -> rejected;
- duplicate FINN item IDs -> one collected lead;
- `1 kr` or request/contact wording -> symbolic, never a verified price;
- non-Clothing saved-search results -> excluded from Discovery Top 5;
- no page request, tracking-link visit, or browser launch;
- raw message body, recipient, and mailbox message ID -> absent from artifacts;
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
- Do not add a mailbox poller, schedule, or workflow in this task.
- Do not contact sellers.
- Do not bid, reserve, purchase, or pay.
- Do not log in, import session cookies, rotate proxies, bypass CAPTCHA, or bypass
  access controls.
- Do not follow any FINN or tracking URL from an alert message.
- Do not run the Playwright pilot without explicit written permission from FINN.

## Definition of current-task success

The implementation succeeds only when:

1. all mandatory focused tests pass;
2. all repository checks pass;
3. sender, subject, item-link, and deduplication gates fail closed;
4. real FINN email-link shapes normalize without network access;
5. the sixteen-query matrix remains unchanged;
6. email price and location remain unverified source evidence;
7. every intake candidate remains `UNKNOWN` and Analysis-blocked;
8. sanitized capture provenance remains traceable;
9. no live FINN collection is performed during implementation or CI;
10. existing Playwright regressions remain passing;
11. no Analysis Engine or commercial-action boundary is crossed.

## Immediate next action

Complete and merge the email intake adapter only after all checks pass. Then
create Clothing Inventory saved searches in FINN and wait for the first genuine
alert. Supply that message to the adapter, inspect all five artifacts, manually
verify only the strongest specific advert, and pass it to the existing
Opportunity Dossier boundary only if the strict confirmation conjunction passes.
An empty result is acceptable and must not be replaced with an invented
opportunity. The live Playwright pilot remains frozen until explicit written
automation permission exists.
