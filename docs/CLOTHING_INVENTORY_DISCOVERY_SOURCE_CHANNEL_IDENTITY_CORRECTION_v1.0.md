# Clothing Inventory Discovery Source-Channel Identity Correction v1.0

**Task:** `CLOTHING_INVENTORY_DISCOVERY_SOURCE_CHANNEL_IDENTITY_CORRECTION`  
**Domain:** `CLOTHING_INVENTORY` only  
**Status:** Implemented in this pull request  
**Automatic commercial action:** Prohibited

## 1. Purpose

Correct the remaining false-positive pattern found after the first verification-integrity correction:

```text
generic company homepage
+ inventory trading services
+ several unrelated news/case sections
+ locations and clothing terms from different sections
= incorrectly reconstructed as one opportunity
```

The observed regression example is the Miko Trading homepage. The production rule is not tied to Miko Trading or its domain. The page is retained only as a deterministic regression fixture.

## 2. Why Miko Trading is a regression fixture

The page contains real commercial signals, but they do not describe one sale object:

- the company buys damaged, surplus and irregular inventory;
- the company sells changing surplus lots;
- one section identifies an outlet location;
- one news item describes a motor-business bankruptcy liquidation;
- another case describes a smoke-damaged clothing store;
- the page invites companies to contact the service provider.

Combining those sections can falsely create:

```text
bankruptcy + clothing store + inventory + location + sale channel
```

No single identified clothing-inventory listing is established by that combination.

Correct semantic result:

```text
page_role = SOURCE_CHANNEL
opportunity_state = REJECTED_NOISE
top5_eligible = false
opportunity_identity = null
identity_stable = false
scenario = UNVERIFIED_EVENT
```

The source may still be useful for future discovery, but the source itself is not one investment opportunity.

## 3. Generic correction rule

A public page is downgraded to `SOURCE_CHANNEL` when all relevant evidence indicates a channel rather than one listing, especially when:

1. the URL is the site root;
2. the title is a generic inventory-trading title;
3. repeated language describes buying inventory from others and selling changing lots;
4. the page contains multiple news, case or service sections;
5. no independent listing ID, item URL or single bounded sale object exists.

Examples of source-channel language include:

```text
selge varepartier til oss
kjøpe varepartier fra oss
vi kjøper ukurante varer
vi selger overskuddsvarer
stadig skiftende utvalg
vi hjelper deg å selge varene
```

The rule must not depend on a company name, hostname or hard-coded denylist.

## 4. Required fail-closed transformation

When the guard identifies a source channel, it must clear listing-scoped evidence:

```text
location = null
inventory_type = null
price_nok = null
bid_price_nok = null
quantity = null
listing_status = UNKNOWN
opportunity_identity = null
identity_stable = false
clothing_inventory_evidence = false
sale_evidence = false
event_scenario = UNVERIFIED_EVENT
bounded_context = null
```

The page remains `verified = true` because it is a readable public source. Verification of a page does not mean verification of an opportunity.

## 5. Regression contract

The deterministic Miko Trading fixture must prove:

1. the page becomes `SOURCE_CHANNEL`;
2. it cannot retain a synthetic event-title identity;
3. unrelated location and clothing terms are cleared;
4. it cannot inherit bankruptcy or closure from a search query;
5. it becomes `REJECTED_NOISE` for opportunity ranking;
6. it cannot enter `discovery-top5.json`;
7. a valid non-root item listing remains unchanged.

Any future change that makes the fixture an `ITEM_LISTING` or `top5_eligible = true` must fail CI.

## 6. Live operator integration

The manual structured Discovery runner wraps public-page verification with:

```text
verify_public_page
  -> enforce_source_channel_identity
  -> run_clothing_inventory_discovery
```

No workflow change is required. The existing operation remains:

```text
structured_clothing_discovery
```

## 7. Files changed

```text
src/opportunity_engine/discovery/source_channel_guard.py
scripts/run_clothing_inventory_discovery_search.py
tests/test_clothing_inventory_source_channel_guard.py
tests/fixtures/clothing_inventory_discovery_verification/miko-trading-source-channel.html
docs/CLOTHING_INVENTORY_DISCOVERY_SOURCE_CHANNEL_IDENTITY_CORRECTION_v1.0.md
```

## 8. Explicit boundaries

This task does not:

- modify the sixteen-query matrix;
- add another opportunity domain;
- change Brave credentials or provider behavior;
- modify the Opportunity Dossier;
- modify confirmed dossier intake;
- modify Analysis Engine formulas;
- calculate ROI, expected profit or maximum bid;
- contact a seller;
- submit a form;
- bid, reserve, purchase or pay;
- add a schedule or automatic run;
- hard-code Miko Trading as a production denylist entry.

## 9. Acceptance criteria

The correction succeeds only when:

- the Miko regression fixture is excluded from Top 5;
- the candidate state becomes `REJECTED_NOISE`;
- the page role becomes `SOURCE_CHANNEL`;
- event, identity, location and inventory fields are cleared;
- a valid specific item listing is not downgraded;
- focused tests pass;
- the complete repository test suite passes;
- a new live run returns only specific listings or an honest empty result.

## 10. Next action after merge

Manually rerun:

```text
1 — Discover Clothing Inventory Opportunities
operation = structured_clothing_discovery
```

Inspect `search-run-report.json` and `discovery-top5.json`. Miko Trading must not appear in Top 5. The motorcycle-clothing listing may remain only as `STRONG_LEAD_REQUIRES_VERIFICATION` until its current public status is proven.
