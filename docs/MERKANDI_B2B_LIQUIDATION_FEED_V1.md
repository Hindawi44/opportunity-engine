# MERKANDI_B2B_LIQUIDATION_FEED_V1

## Purpose

Add one bounded marketplace-intelligence lane for clothing stock and liquidation
lots listed on the official Merkandi domain.

This is the first source in the future `B2B_LIQUIDATION_MARKETPLACE_FEED_V1`
family. It does not replace the existing Norway, Sweden, Germany, bridal, fabric,
or early-signal pipelines.

## Approved source

- `merkandi.com`

No other marketplace is enabled in this change.

## Search budget

- one official-domain Brave Search request per daily run;
- at most 10 search results requested;
- at most 5 accepted leads;
- one-month freshness window;
- existing `BRAVE_SEARCH_API_KEY`; no new provider or secret.

## Strict acceptance gate

A result is accepted only when the public search result shows all of the following:

1. exact official Merkandi domain;
2. clothing inventory context;
3. wholesale, stocklot, liquidation, clearance, surplus, or equivalent B2B signal;
4. inventory quantity greater than one;
5. quantity within the small-operator limit;
6. minimum order or MOQ;
7. visible price and currency;
8. named seller, supplier, company, or wholesaler;
9. manifest, packing list, inventory list, or stock list;
10. authenticity evidence when named brands are present.

A listing is rejected when any required field is missing. Private sales, single-item
listings, generic marketplace pages, unknown sellers, and oversized lots are not
promoted.

## Small-operator quantity limit

- up to 5,000 units, pieces, pairs, or sets;
- up to 1,000 kg.

These limits are a safety gate for the current one-person tailoring business, not
a claim that every accepted quantity is affordable or commercially suitable.

## Candidate state

Every accepted row remains:

`B2B_LEAD_REQUIRES_VERIFICATION`

It is not a qualified opportunity until a human verifies:

- that the listing is still active;
- the seller's legal identity and company data;
- the complete manifest;
- authenticity and resale rights for brands;
- condition and defects;
- shipping to Norway;
- import VAT, customs, freight, and total landed cost;
- payment and return terms.

## Output

The daily run writes:

- `merkandi-b2b-liquidation-feed.json`;
- a compact `merkandi_b2b_liquidation_feed` section in
  `domain-market-intelligence-brief.json`;
- a readable section in `domain-market-intelligence-brief.txt`.

A zero-result run is valid and remains visible as `VALID_ZERO`.

## Trust boundary

- read-only marketplace intelligence;
- no seller contact;
- no bidding;
- no reservation;
- no purchase;
- no payment;
- no Top 5 eligibility;
- no financial-analysis eligibility;
- no automatic promotion to a canonical opportunity.
