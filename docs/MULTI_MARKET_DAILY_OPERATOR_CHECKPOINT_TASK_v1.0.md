# Multi-Market Daily Operator Checkpoint Task v1.0

**Status:** IMPLEMENTED IN PR #413 — POST-MERGE MANUAL LIVE VALIDATION REQUIRED  
**Markets:** Norway (`NO`), Sweden (`SE`), Germany (`DE`)  
**Domain:** `CLOTHING_INVENTORY`

## Objective

Create one read-only operator checkpoint that summarizes the existing Norway, Sweden and Germany discovery outputs without rebuilding any market or adding a new source.

The checkpoint answers:

```text
What was searched?
Which market and source paths succeeded or failed?
Which records are active, historical, blocked or unresolved?
Which records are eligible for end-to-end review?
What is the single next human action?
```

## Implemented source paths

The first implementation runs five bounded existing paths:

| Market | Source path | Role |
|---|---|---|
| `NO` | Auksjonen public clothing categories | Domestic active clothing inventory path |
| `SE` | Blinto bounded pilot | Swedish cross-border discovery evidence |
| `DE` | Riegermann active auctions | Active German source |
| `DE` | VENTA active clothing watch | Valid-zero-capable daily watch |
| `DE` | Deutsche Pfandverwertung active clothing watch | Valid-zero-capable daily watch |

The authoritative market-completion matrix contributes authorization and activation blockers. No new collector or source adapter is introduced.

## Implemented files

```text
src/opportunity_engine/discovery/multi_market_operator_checkpoint.py
scripts/run_multi_market_daily_operator_checkpoint.py
scripts/run_checkpoint_source_command.py
.github/workflows/multi-market-daily-operator-checkpoint.yaml
tests/test_multi_market_operator_checkpoint.py
tests/test_multi_market_operator_checkpoint_workflow.py
docs/WORKFLOW_INVENTORY_REPORT_v1.2.md
```

## Required output

The workflow produces:

```text
multi-market-daily-checkpoint.json
multi-market-phone-summary.txt
input-manifest.json
source-specific JSON, SQLite and execution-status evidence
```

The structured report contains:

- execution timestamp;
- market coverage for `NO`, `SE` and `DE`;
- source execution status;
- failure versus valid-zero-result distinction;
- active, upcoming, historical, ended and unresolved counts;
- deduplicated opportunity identities;
- Top 5 eligibility and Analysis eligibility counts;
- missing evidence and activation blockers;
- one bounded next human action;
- artifact references to source-specific evidence.

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

## Implementation boundary

The workflow is manual and read-only.

It does not:

- add a fourth country;
- add a source adapter;
- change existing source schedules;
- change source runtime statuses;
- modify the Opportunity Dossier contract;
- modify V2.8–V3.7 formulas;
- alter investment scoring or final-decision semantics;
- delete or disable existing workflows;
- contact sellers or auction providers.

## Decision precedence

The checkpoint emits exactly one human action using this bounded order:

```text
1. Review one verified active Top 5 opportunity.
2. Otherwise review one source failure.
3. Otherwise verify one unresolved record.
4. Otherwise take no immediate action and continue monitoring.
```

A valid zero result never becomes a failure, and a source failure never becomes zero opportunities.

## Validation completed on PR #413

```text
Focused checkpoint workflow tests = PASS
Full repository tests = 1292 passed
Sweden Clothing Inventory Live Pilot = PASS
Germany Clothing Inventory Live Pilot = PASS
Multi-Market Daily Operator Checkpoint contract job = PASS
```

The manual live aggregation job is intentionally excluded from pull-request events. After merge, it must be dispatched once from `main` and its JSON/phone artifacts must be inspected before this task is declared fully validated.

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
9. no new source, country, financial assumption or automatic action is introduced;
10. the first manual `main` run produces the two official checkpoint outputs.

## Project sequence lock

```text
PROJECT_STATE_RECONCILIATION
  -> MULTI_MARKET_DAILY_OPERATOR_CHECKPOINT
```

Do not restart Norway, Sweden or Germany and do not begin a fourth market before the post-merge manual checkpoint run is validated.
