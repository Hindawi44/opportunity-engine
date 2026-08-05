# STOCK_HURT_B2B_FEED_V1

## Purpose

Add one bounded official-source intelligence lane for Stock-Hurt wholesale
clothing, packages, pallets, products sold by weight, and pallet-auction signals.

This lane supports human research and calculation. It does not decide whether a
lot is suitable and does not reject a serious lot because it is large.

## Approved source

- `stockhurt.com`

The feed retains relevant pages under the official English product, shop,
category, and pallet-auction paths. Other domains are rejected.

## Search budget

- two official-domain Brave Search queries per daily run;
- at most 10 results per query;
- at most 12 retained signals;
- one-month freshness window;
- existing `BRAVE_SEARCH_API_KEY`; no new secret or provider.

## Preserved signal types

- specific wholesale product or stock offer;
- product sold by kilogram, package, box, or pallet;
- pallet-auction signal;
- relevant catalogue signal;
- out-of-stock product retained as historical market evidence.

The collector extracts visible quantity, minimum order, price, currency, unit,
grade, brands, stock location, shipping language, stock-list or manifest evidence,
authenticity language, and availability status. Missing values remain in
`missing_information`.

## Decision authority

- `decision_owner = HUMAN_OPERATOR`;
- `quantity_size_rejection_enabled = false`;
- lot size is descriptive only: `SMALL`, `MEDIUM`, `LARGE`, `VERY_LARGE`, or
  `UNKNOWN`;
- complete specific records remain `B2B_LEAD_REQUIRES_VERIFICATION`;
- incomplete, catalogue, auction, and unavailable records may remain
  `EARLY_B2B_SIGNAL_REQUIRES_VERIFICATION`.

The operator opens the source, gathers missing numbers, calculates landed cost,
checks authenticity and condition, negotiates, and makes the final decision.

## Output

The daily run writes:

- `stockhurt-b2b-feed.json`;
- `stockhurt_b2b_feed` in `domain-market-intelligence-brief.json`;
- a readable Stock-Hurt section in `domain-market-intelligence-brief.txt`.

A zero-result run is valid and remains visible as `VALID_ZERO`.

## Trust boundary

- read-only intelligence;
- no seller contact;
- no bidding;
- no reservation;
- no purchase;
- no payment;
- no Top 5 promotion;
- no financial-analysis promotion;
- no automatic promotion to a canonical opportunity.
