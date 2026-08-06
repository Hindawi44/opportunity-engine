# UNIFIED_DECISION_PRIORITY_V1

## Problem corrected

The first unified river ordered every market case mainly by source or discovery strength. That allowed a high-confidence insolvency signal with no available stock to appear above a current clothing offer.

Source strength remains useful evidence, but it is not commercial actionability.

## Decision lanes

The daily decision brief now has three explicit lanes:

1. `ACTIONABLE_NOW`
   - current canonical opportunities;
   - B2B stock offers;
   - active auction inventory;
   - fabric procurement candidates.

2. `MARKET_WATCH`
   - insolvency and business-closure signals without a linked offer;
   - bridal liquidation signals that still require stock verification;
   - other early market signals.

3. `HISTORICAL_EVIDENCE`
   - ended, sold, unavailable, and historical-only cases.

A liquidation case moves into `ACTIONABLE_NOW` when it contains a linked direct opportunity or commercial offer. The business event itself is never promoted into an opportunity.

## Priority order

Within `ACTIONABLE_NOW`, the bounded ordering is:

1. qualified direct opportunity;
2. active direct opportunity;
3. direct opportunity requiring review;
4. B2B offer with visible price and quantity;
5. B2B offer requiring verification;
6. active auction review;
7. fabric procurement review;
8. another linked commercial case requiring review.

`commercial_strength` remains visible as `source_strength` and is used only as a tie-break signal after actionability.

## Output fields

`unified-daily-decision-brief.json` now includes:

- `actionable_now`;
- `market_watch`;
- `historical_evidence`;
- `priority_counts`;
- `top_actionable_card`;
- `top_market_watch_card`;
- `top_decision_card` (the top actionable card when one exists);
- `priority_rule: ACTIONABILITY_BEFORE_SOURCE_SIGNAL_STRENGTH`.

Each case and decision card also includes:

- `decision_lane`;
- `actionability_tier`;
- `priority_class`;
- `actionability_score`;
- `source_strength`;
- `priority_reasons`.

## Safety boundary

This is a read-only ordering projection. It does not contact sellers, bid, reserve, purchase, pay, reject by quantity, or promote a signal into a canonical opportunity. The decision owner remains `HUMAN_OPERATOR`.
