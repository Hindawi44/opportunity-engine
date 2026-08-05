# FABRIC_DEADSTOCK_PROCUREMENT_FEED_V1

## Purpose

Add one bounded procurement-intelligence lane for the operator's tailoring shop.
This lane watches approved official supplier domains for premium deadstock and
bridal fabrics. It does not convert supplier products into clothing-liquidation
opportunities.

## Approved sources

- `evaresource.com` — Italian premium deadstock fabrics.
- `fabrichouse.com` — Italian premium deadstock fabrics and samples.
- `bridalfabrics.com` — specialist bridal lace, tulle, fabrics, trims, and samples.

Unverified names from brainstorming are not enabled.

## Daily budget

- 3 official-domain Brave queries.
- 1 query per approved source.
- 8 results requested per source by default.
- At most 5 accepted candidates per source.
- English search language.
- One-month freshness window.
- Existing `BRAVE_SEARCH_API_KEY`; no new secret or provider.

## Candidate gate

Every result must:

1. use HTTPS;
2. belong to the exact approved supplier domain or its subdomain;
3. contain a recognized fabric term;
4. for deadstock suppliers, contain a stock, deadstock, sale, clearance, deal,
   sample, or new-arrival term;
5. for Bridal Fabrics, contain bridal or wedding context.

The watch extracts visible price and currency when present, records fabric and
bridal terms, and assigns a bounded procurement relevance score.

## Output

The daily run writes:

- `fabric-procurement-watch.json`
- a compact `fabric_procurement_watch` section in
  `domain-market-intelligence-brief.json`
- a readable section in `domain-market-intelligence-brief.txt`

The compact bulletin includes up to five highest-scoring candidates with source,
title, URL, visible price, material terms, score, and the required operator action.

## Operator rule

`COMPARE_PRICE_SAMPLE_COMPOSITION_AND_SHIPPING_BEFORE_ORDER`

A result is useful for supplier comparison and sample selection only. Before any
order, the operator must verify:

- exact composition;
- width and weight;
- color and sample;
- available metres;
- price and VAT basis;
- shipping, customs, and import cost to Norway;
- return conditions.

## Trust and safety boundary

- no opportunity promotion;
- no Top 5 or financial-analysis eligibility;
- no OpenAI-generated supplier identity;
- no automatic contact;
- no automatic reservation;
- no automatic purchase;
- no automatic payment.

A zero-candidate result is valid and must remain visible as `VALID_ZERO`.
