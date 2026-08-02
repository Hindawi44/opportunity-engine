# Multi-Market Daily Operator Checkpoint Task v1.0

**Status:** NEXT APPROVED PRODUCT TASK AFTER PROJECT-STATE RECONCILIATION  
**Markets:** Norway (`NO`), Sweden (`SE`), Germany (`DE`)  
**Domain:** `CLOTHING_INVENTORY`

## Objective

Create one read-only operator checkpoint that summarizes the existing Norway, Sweden and Germany discovery outputs without rebuilding any market or adding a new source.

The checkpoint must answer:

```text
What was searched?
Which market and source paths succeeded or failed?
Which records are active, historical, blocked or unresolved?
Which records are eligible for end-to-end review?
What is the single next human action?
```

## Required inputs

Reuse existing artifacts and contracts from:

- the principal Clothing Inventory discovery workflow;
- Sweden Clothing Inventory Live Pilot;
- Germany Clothing Inventory Live Pilot;
- Riegermann Active Clothing Auctions;
- VENTA Active Clothing Watch;
- Deutsche Pfandverwertung Active Clothing Watch;
- unified opportunity reports and SQLite persistence summaries.

No new collector is authorized by this task.

## Required output

Produce one phone-readable summary and one structured JSON report containing:

- execution timestamp;
- market coverage for `NO`, `SE` and `DE`;
- source execution status;
- failure versus valid-zero-result distinction;
- active, upcoming, historical, ended and unresolved counts;
- deduplicated opportunity identities;
- Top 5 eligibility and Analysis eligibility counts;
- missing evidence and activation blockers;
- one bounded next human action;
- links or artifact references to source-specific evidence.

## Mandatory rules

1. Reuse existing market profiles and source adapters.
2. Preserve source-native currencies: `NOK`, `SEK`, `EUR`.
3. Do not convert source-native prices without a documented FX basis.
4. Treat a valid zero-result run as success.
5. Treat source failure separately from zero opportunities.
6. Preserve historical records without promoting them to active opportunities.
7. Apply the strict public-verification and post-verification Top 5 gates.
8. Keep missing price, quantity, VAT, customs, logistics and profit data unknown.
9. Produce no automatic purchase, bid, contact, reservation, payment or external financial action.
10. Keep `BUY_REVIEW` as a human-review state only.

## Initial implementation boundary

The first implementation must be manual and read-only.

It must not:

- add a fourth country;
- add a source adapter;
- change existing source schedules;
- change source runtime statuses;
- modify the Opportunity Dossier contract;
- modify V2.8–V3.7 formulas;
- alter investment scoring or final-decision semantics;
- delete or disable existing workflows;
- contact sellers or auction providers.

## Acceptance criteria

The task passes only when:

1. all three completed market foundations are represented;
2. every included source reports success, valid zero, blocked, or failure explicitly;
3. identities are deduplicated across the consolidated result;
4. historical and ended records remain outside active Top 5;
5. source-native currencies do not leak into NOK fields;
6. SQLite and JSON record counts reconcile where persistence is enabled;
7. the phone summary identifies no more than one immediate human action;
8. repository-wide tests and focused integration tests pass;
9. no new source, country, financial assumption or automatic action is introduced.

## Project sequence lock

```text
PROJECT_STATE_RECONCILIATION
  -> MULTI_MARKET_DAILY_OPERATOR_CHECKPOINT
```

Do not restart Norway, Sweden or Germany before this checkpoint is implemented and validated.
