# MERKANDI_B2B_LIQUIDATION_FEED_V1

## Purpose

Monitor serious clothing-stock and liquidation listings on the official Merkandi
domain and preserve the evidence for human evaluation.

The engine does not decide whether a lot is too large, affordable, or suitable.
It extracts what is public, marks missing information, supports later calculation,
and leaves the commercial decision to the operator.

## Approved source and budget

- official domain: `merkandi.com`;
- one Brave Search request per daily run;
- at most 10 results requested and 8 retained signals;
- existing `BRAVE_SEARCH_API_KEY`; no new provider or secret.

## Visibility gate

A result must be on the official domain and show both clothing-inventory context
and a wholesale, stocklot, liquidation, clearance, surplus, overstock, or similar
B2B signal.

Only clearly irrelevant, unofficial, generic home-page, private-sale, or single-item
results are rejected.

Missing quantity, MOQ, price, seller identity, manifest, shipping information, or
brand-authenticity evidence does not automatically hide a serious result. It is
listed under `missing_information` and remains:

- `B2B_LEAD_REQUIRES_VERIFICATION` when the visible commercial evidence is complete;
- `EARLY_B2B_SIGNAL_REQUIRES_VERIFICATION` when important fields are missing.

## Lot size and decision authority

Lot size is descriptive only:

- `SMALL`
- `MEDIUM`
- `LARGE`
- `VERY_LARGE`
- `UNKNOWN`

There is no rejection threshold based on shop size, capital, or lot size.

`decision_owner = HUMAN_OPERATOR`

The operator inspects, calculates landed cost and resale scenarios, negotiates,
and decides whether to proceed.

## Output and trust boundary

The daily run writes `merkandi-b2b-liquidation-feed.json` and attaches a compact
section to the daily JSON and text bulletins.

The lane remains read-only: no contact, bidding, reservation, purchase, payment,
Top 5 promotion, financial-analysis promotion, or automatic opportunity promotion.
