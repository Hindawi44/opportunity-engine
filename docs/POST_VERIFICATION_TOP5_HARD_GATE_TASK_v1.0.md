# Post-Verification Top 5 Hard Gate v1.0

**Domain:** `CLOTHING_INVENTORY` only

**Trigger:** structured Discovery run `30390608947` on commit `69af63b`

**Scope:** verification and Top 5 eligibility correction only

## Problem

The live structured Discovery run completed successfully but placed three
unsupported candidates in `discovery-top5.json`:

1. two dated Dagsavisen articles whose URL years (`2024` and `2020`) were
   interpreted as listing IDs; and
2. Auksjonen listing `445743`, whose public verification returned only an
   unresolved site shell.

All three candidates had failed or unresolved verification. None was a
confirmed active Clothing Inventory sale, and none was eligible for financial
analysis or Opportunity Dossier intake.

## Root causes

1. Numeric URL identity extraction did not distinguish a dated editorial path
   (`/YYYY/MM/DD/`) from a commercial listing ID.
2. Discovery Top 5 eligibility could survive failed public verification when a
   search URL and snippet appeared to provide a stable item identity.
3. The early-opportunity recovery gate rebuilt Top 5 without enforcing the
   strict confirmation conjunction at the final post-verification boundary.

## Required correction

The structured Discovery runner must apply a final hard gate after public
verification and early-lead recovery.

A candidate may enter Top 5 only when all of the following are true:

```text
page_role == ITEM_LISTING
AND identity_stable == true
AND listing_status == ACTIVE
AND opportunity_state == CONFIRMED_SALE
AND at least one successful bounded item verification exists
AND that verification confirms Clothing Inventory evidence
AND that verification confirms sale evidence
```

The gate must fail closed. Failed, unresolved, ended, editorial, category,
source-channel, ordinary-store, and verification-not-attempted candidates must
remain outside Top 5 and Analysis.

## Required regression outcomes

```text
Dagsavisen /2024/01/24/... -> year is not a listing ID
Dagsavisen /2020/03/17/... -> year is not a listing ID
Auksjonen 445743 + unresolved shell -> top5_eligible=false
confirmed active bounded item listing -> remains in Top 5
no confirmed active listings -> discovery_top5=[]
```

When the Auksjonen page returns only an unresolved shell, the gate must not
invent `ENDED`, price, quantity, location, or inventory facts. Existing
unavailable-page evidence continues to classify listing `445743` as `ENDED`
when the explicit unavailable message is actually observed.

## Scope lock

This task must not:

- modify the sixteen-query matrix;
- add or expand a source;
- modify workflows or schedules;
- modify FINN email intake or the FINN Playwright pilot;
- run FINN collection;
- modify Opportunity Dossier, market-comparable, acquisition-cost, financial,
  scoring, or decision logic;
- invent commercial values or listing status;
- contact, bid, reserve, buy, or pay.

## Acceptance

The task succeeds when focused and repository-wide tests pass, the three live
false positives cannot enter Top 5, an empty Top 5 is accepted, and a genuinely
verified active Clothing Inventory sale still passes unchanged.
