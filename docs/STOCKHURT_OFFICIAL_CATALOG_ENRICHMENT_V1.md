# STOCKHURT_OFFICIAL_CATALOG_ENRICHMENT_V1

## Purpose

Discover current Stock-Hurt offers directly from its public official shop and pallet-auction catalogues, then extract visible commercial fields from at most three official product pages.

## Fixed retrieval boundary

- one `robots.txt` request;
- `https://stockhurt.com/en/shop/`;
- `https://stockhurt.com/en/licytacje/`;
- at most three `https://stockhurt.com/en/product/...` pages;
- maximum six requests per run;
- maximum 2 MB per response;
- published crawl delay respected up to ten seconds;
- no search API key, login, browser automation or account access.

## Extracted decision-support fields

When visible, the lane preserves price or current bid, currency, total available quantity, minimum order, price basis, grade, condition, brands, weight, warehouse location, auction end text, manifest or packing-list links, shipping terms and official page evidence.

The output distinguishes active offers from out-of-stock historical signals. Source-protection challenge pages are reported explicitly and are not misclassified as valid zero results.

## Decision authority

Lot size is descriptive only. Missing information remains visible. The operator remains the sole decision maker.

Automatic contact, bidding, reservation, purchase, payment, Top 5 promotion, canonical-opportunity promotion and financial-analysis promotion are disabled.
