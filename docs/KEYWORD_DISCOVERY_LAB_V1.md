# KEYWORD_DISCOVERY_LAB_V1

## Purpose

Evaluate search keywords for fashion stock, liquidation, warehouse remainders, business closure, and bankruptcy lots **before** those keywords are admitted to a live market-discovery feed.

This is a shadow laboratory. It does not create opportunities and it does not write to production state.

## V1 scope

- Market: Italy (`IT`)
- Candidate keywords: 10
- Default search budget: 10 keywords × 5 Brave results = at most 50 result slots
- Hard workflow ceiling: 10 keywords × 10 results
- Trigger: manual `workflow_dispatch` only
- Output: JSON artifact retained for 30 days

## Scoring

Each keyword receives a score from 0 to 100:

| Metric | Weight |
|---|---:|
| Genuine B2B language | 25 |
| Stock/lot evidence | 25 |
| Liquidation/closure/bankruptcy evidence | 20 |
| Quantity/price evidence | 10 |
| Seller/company identity evidence | 10 |
| Italy relevance | 5 |
| Clean result rate (not retail/news false positives) | 5 |

Decision gates:

- `PROMOTE`: score >= 80
- `SHADOW`: score >= 60 and < 80
- `REJECT`: score < 60

`PROMOTE` is only a lab verdict. V1 has `promotion_to_live_engine_enabled=false`; no keyword is automatically added to production.

## Evidence retained

For every result the artifact records:

- result rank, title, URL, host and provider
- matched B2B terms
- stock/lot terms
- liquidation/closure terms
- price/quantity evidence
- seller identity evidence
- geographic evidence
- false-positive reason(s)
- whether the result contributes to actionable keyword yield

The report also ranks all tested keywords and records false-positive ratio and actionable yield.

## Safety contract

The lab must remain isolated from production until a separate decision explicitly promotes a proven keyword set.

V1 guarantees:

- no production writes
- no opportunity promotion
- no automatic contact
- no automatic bid or reservation
- no automatic purchase or payment
- no scheduled run

## Ordered validation protocol

1. Merge code only after repository tests pass.
2. Run the workflow manually with the V1 default: 10 keywords × 5 results.
3. Inspect the JSON ranking and false-positive evidence.
4. Do not change thresholds after seeing the result merely to manufacture winners.
5. If the lab behaves correctly, repeat on another day before changing the live Italy query pack.
6. Only then consider a separate PR that promotes proven keywords into production discovery.
