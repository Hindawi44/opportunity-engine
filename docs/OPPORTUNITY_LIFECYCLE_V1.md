# Opportunity Lifecycle V1

This version adds a deterministic lifecycle classifier above the completed Norway,
Sweden, and Germany discovery paths. It does not rebuild a market, add a fourth
market, persist lifecycle events, or perform an external commercial action.

## Canonical stages

The existing `WorkflowStatus` enum remains the single stage model:

`EARLY_SIGNAL -> CANDIDATE -> REQUIRES_VERIFICATION -> ACTIVE_OPPORTUNITY -> QUALIFIED_OPPORTUNITY`

Terminal/non-current states are `HISTORICAL_MARKET_EVIDENCE`, `CLOSED`, and
`REJECTED`.

## Ordered rules

1. Explicit rejection becomes `REJECTED` and loses current-flow eligibility.
2. Verified inactive historical evidence becomes `HISTORICAL_MARKET_EVIDENCE`.
3. Any other inactive listing becomes `CLOSED`.
4. A traceable event lead becomes `EARLY_SIGNAL` and is never analysis eligible.
5. An active confirmed sale becomes `QUALIFIED_OPPORTUNITY` only when explicit
   verification and analysis eligibility are both present.
6. A verified active record with analysis eligibility becomes
   `ACTIVE_OPPORTUNITY` while awaiting a qualified commercial evaluation.
7. Strong leads, visible Top 5 candidates, and partially verified records become
   `REQUIRES_VERIFICATION`.
8. Everything else remains `CANDIDATE`.

## Safety invariants

- Ended, sold, unavailable, historical, and rejected records cannot remain current
  Top 5 or analysis eligible.
- Early signals may preserve existing Discovery Top 5 visibility, but cannot enter
  analysis.
- The classifier never estimates missing facts.
- No automatic contact, bid, purchase, reservation, or payment is introduced.

## Deferred work

SQLite lifecycle event history, transition persistence, repository methods, and
checkpoint lifecycle summaries belong to later changes after this classifier is
stable.
