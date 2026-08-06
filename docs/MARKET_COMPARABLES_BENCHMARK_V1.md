# MARKET_COMPARABLES_BENCHMARK_V1

## Purpose

Benchmark the first three `ACTIONABLE_NOW` items against public asking-price evidence before spending effort on shipping and landed-cost analysis.

The benchmark answers a narrow question:

> Does the current offer appear below, near, or above comparable public market asking prices?

It does not claim a completed-sale value or profit.

## Bounded search

For each of at most three actionable items:

- one wholesale query;
- one retail query;
- at most five results per query;
- at most ten accepted comparables per item.

The original source listing is excluded from its own benchmark.

## Comparable controls

A result is accepted only when:

- a public source URL is present;
- a visible price is present;
- the comparison unit matches the target (`PER_ITEM`, `PER_KG`, or `PER_METRE`);
- title, brand, or garment-type similarity passes the threshold.

Wholesale and retail ranges remain separate. Public prices are treated as asking prices, not completed transactions.

## Currency

NOK is normalized directly. Other currencies are converted only when an explicit environment rate is supplied, for example:

```text
MARKET_COMPARABLES_FX_EUR_NOK
MARKET_COMPARABLES_FX_GBP_NOK
MARKET_COMPARABLES_FX_SEK_NOK
```

No exchange rate is guessed. Missing rates remain visible as `FX_RATE_MISSING`.

## Classifications

- `CLEARLY_BELOW_MARKET`
- `BELOW_MARKET_REQUIRES_VERIFICATION`
- `NEAR_MARKET`
- `ABOVE_MARKET`
- `MARKET_RANGE_AVAILABLE_TARGET_PRICE_MISSING`
- `INSUFFICIENT_COMPARABLES`

At least three compatible comparables are required before a market-position classification is produced.

## Output

```text
market-comparables-benchmark.json
```

A compact summary is also attached to the unified daily decision brief and the existing domain bulletin.

## Safety and decision boundary

Shipping, auction fees, tax, condition risk, authenticity, and the final purchase price are outside this stage.

The benchmark never contacts, bids, reserves, purchases, or pays. The decision owner remains `HUMAN_OPERATOR`.
