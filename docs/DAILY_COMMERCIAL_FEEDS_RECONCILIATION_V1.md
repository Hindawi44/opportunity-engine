# DAILY_COMMERCIAL_FEEDS_RECONCILIATION_V1

## Problem

The production daily checkpoint already executed the NO/SE/DE bridal liquidation search, but the daily brief exposed only aggregate bridal counts. Useful sample/clearance signals could therefore be present in `bridal-liquidation-feed.json` without being visible as named commercial leads in the operator brief.

The repository also contained established B2B clothing-liquidation collectors, but the full optional side-feed bundle was intentionally removed from the default daily checkpoint to keep the production scope bounded and avoid restoring NL/PL/UK side lanes and their larger request budget.

## Change

The default daily builder now keeps the primary market scope at Norway, Sweden, and Germany while adding two bounded visibility lanes:

1. **Bridal clearance watch**
   - reuses the bridal feed that already runs in the core bulletin;
   - surfaces up to five current NO/SE/DE bridal clearance/sample-sale signals with title, country, confidence, verification state, and source URL;
   - remains outside the general opportunity Top 5 and requires human verification.

2. **Daily B2B clothing watch**
   - restores only the existing Merkandi B2B collector in its Germany search region;
   - adds at most one Brave search request per daily checkpoint;
   - surfaces up to five B2B leads with quantity, price, stock location, relevance score, and source URL when available;
   - explicitly records that the stock country must be verified and does not treat the Germany search region as proof of stock location;
   - remains outside the general opportunity Top 5 and cannot auto-contact, bid, reserve, purchase, or pay.

The larger optional bundle remains outside the automatic daily checkpoint, including Fabric Procurement, Fashion Stock Netherlands, Stock-Hurt, and Jobalots.

## Safety and scope invariants

- Primary production market scope remains `NO / SE / DE`.
- No new country is added to the checkpoint manifest.
- No automatic commercial action is enabled.
- Bridal and B2B visibility do not bypass evidence verification or lifecycle gates.
- The additional automatic search budget is bounded to the existing Merkandi one-query feed.
