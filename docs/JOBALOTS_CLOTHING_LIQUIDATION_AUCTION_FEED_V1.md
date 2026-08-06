# JOBALOTS_CLOTHING_LIQUIDATION_AUCTION_FEED_V1

## Purpose

Add one bounded, read-only Jobalots lane to the existing domain market-intelligence bulletin. The feed surfaces clothing, footwear, and textile job lots for operator review without rebuilding the established Norway, Sweden, Germany, bridal, fabric, persistence, OpenAI, or human-review paths.

## Official source boundary

Only `jobalots.com` and its subdomains are accepted. The feed does not accept lookalike domains.

## Bounded retrieval

- two Brave Search queries per run;
- English search language;
- United Kingdom search region;
- eight results per query by default, ten maximum;
- twelve accepted signals maximum;
- existing `BRAVE_SEARCH_API_KEY` only.

## Preserved signal types

- specific clothing auction or job-lot pages;
- clothing and footwear pallets, boxes, and mixed lots;
- customer returns, clearance, overstock, and liquidation lots;
- incomplete or unmanifested lots requiring verification;
- ended lots as historical market evidence.

Non-clothing lots, generic home pages, impostor domains, and ordinary single retail items are rejected.

## Extracted decision-support fields

When visible in the search result, the feed preserves:

- source reference and URL;
- quantity and quantity unit;
- pallet, box, or lot count;
- current or starting bid and currency;
- estimated retail value or RRP;
- manifest availability;
- condition terms;
- brands;
- warehouse location;
- auction end text;
- missing information;
- relevance score and recommended human action.

Lot size is descriptive only. Large and very large lots remain visible.

## States

- `B2B_LEAD_REQUIRES_VERIFICATION`
- `EARLY_B2B_SIGNAL_REQUIRES_VERIFICATION`

No Jobalots result is automatically promoted into the canonical opportunity Top 5 or financial-analysis path.

## Output

- `jobalots-clothing-auction-feed.json`;
- `jobalots_clothing_auction_feed` in the daily JSON bulletin;
- a readable Jobalots section in the daily text bulletin.

## Trust boundary

`decision_owner = HUMAN_OPERATOR`

The implementation cannot contact a seller, place a bid, reserve a lot, purchase, or pay. A source page, manifest, auction status, fees, shipping, import VAT, landed cost, authenticity, and resale rights must be verified before any commercial decision.
