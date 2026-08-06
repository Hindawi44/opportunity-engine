# MARKET_COMPARABLES_TARGET_HYDRATION_AND_QUERY_QUALITY_V1

## Purpose

Improve the existing public market-comparables benchmark without adding new network sources or estimating shipping.

The layer reads already-produced local checkpoint artifacts named by `input-manifest.json`, then enriches benchmark targets with source-backed fields that were not present in the unified projection.

## Hydrated fields

When visible in a local source artifact, the layer preserves:

- current bid or visible price;
- currency;
- explicit quantity and unit;
- auction end time;
- conservative brand tokens from the product title.

An explicit title quantity such as `10 stk` may be used as source-backed quantity evidence. No quantity is invented for a general lot title. Every hydrated field retains the local artifact path and matched-record count in the benchmark output.

## Price discipline

A total bid is converted to a unit price only when an explicit compatible quantity is available.

When quantity is missing, the total bid remains visible as `visible_total_amount`, while the unit target price remains unknown. This prevents a total auction bid from being compared directly with one retail item.

## Target quality

Generic seller-only titles such as a company name and location are skipped. The selector continues down the existing `ACTIONABLE_NOW` list until it finds at most three product-specific targets.

Collection, category, and generic shop pages are not treated as specific product targets.

## Query quality

Search queries keep the brand and a short product description while removing:

- quantities;
- sizes;
- generic lot words;
- duplicated brand tokens;
- source-domain self matches.

Example:

```text
10 stk GSA multinorm arbeidsplagg ... Str. 62 (2XL)
```

becomes a product-focused core similar to:

```text
"GSA" multinorm arbeidsplagg kjeledresser jakke
```

## Boundaries

The existing limit remains unchanged:

- at most three targets;
- one wholesale and one retail query per target;
- at most six search requests per daily run.

No contact, bid, reservation, purchase, payment, shipping estimate, tax estimate, or automatic decision is introduced. `decision_owner` remains `HUMAN_OPERATOR`.
