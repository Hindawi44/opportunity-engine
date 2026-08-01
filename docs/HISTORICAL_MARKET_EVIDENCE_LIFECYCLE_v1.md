# Historical Market Evidence Lifecycle v1

## Decision

A publicly verified item listing that is ended, sold, or unavailable is not a current opportunity and must not remain in `STRONG_LEAD_REQUIRES_VERIFICATION`.

It is routed to the dedicated lifecycle path:

- discovery state: `HISTORICAL_MARKET_EVIDENCE`
- evaluation status: `HISTORICAL_ONLY`
- workflow status: `HISTORICAL_MARKET_EVIDENCE`
- current analysis eligibility: `false`
- Top 5 eligibility: `false`
- historical market evidence eligibility: `true`

## Entry gate

The discovery gate requires all of the following before routing an ended record:

1. `listing_status == ENDED`
2. `page_role == ITEM_LISTING`
3. stable item identity
4. at least one public verification marked verified
5. the verified page is the same ended item-listing class

Generic pages, unresolved pages, and unverified snippets are not promoted into the historical evidence path.

## Operator behavior

The record remains available for later market-price and lot-comparison work, but it is removed from:

- current opportunities
- verification queues for active availability
- financial analysis
- Discovery Top 5

No VAT, customs, logistics, FX, ROI, bid, purchase, contact, or payment logic is introduced by this lifecycle change.
