# BRIDAL_LIQUIDATION_FEED_V1

## Product purpose

Add one narrow bridal-inventory tributary to the existing Norway, Sweden, and Germany market-intelligence river.

The feed searches for commercial signals involving:

- bridal-store closure or liquidation;
- insolvency affecting a bridal shop or bridal collection;
- bridal inventory, rest stock, sample dresses, or collection clearance;
- a commercial batch or stock sale.

It does not add another country, rebuild the engine, or replace existing collectors.

## Search budget

The default live run is strictly bounded:

- Norway: one Brave query;
- Sweden: one Brave query;
- Germany: one Brave query;
- eight results requested per query;
- three Brave requests total;
- one-year Brave freshness window.

The existing `BRAVE_SEARCH_API_KEY` is reused. No additional secret or provider is required.

## Commercial gate

A result is accepted only when the returned title or snippet contains all three groups:

1. a bridal term;
2. a commercial batch/store/inventory term;
3. a closure, insolvency, surplus, or auction event term.

A private person selling one used wedding dress therefore does not enter the market-signal river.

## Output and continuity

Accepted links are written as ordinary `MarketSignalRecord` rows into the existing market signal report for their country. They therefore use the current:

- SQLite persistence;
- cross-run continuity;
- market-intelligence bulletin;
- OpenAI hunt-case grouping;
- targeted Brave follow-up path.

The daily checkpoint also writes:

- `bridal-liquidation-feed.json`
- a compact `bridal_liquidation_feed` section inside the domain market-intelligence brief.

## Trust boundary

A Brave title, snippet, and URL are not proof that stock is still available.

Every accepted result remains:

- `signal_only = true`;
- `not_an_opportunity = true`;
- `WATCH` status;
- unverified public-web evidence;
- ineligible for promotion, Top 5, or financial analysis.

The feed cannot contact a seller, bid, purchase, reserve, or pay.

## First live validation

After merge, run one manual `Multi-Market Daily Operator Checkpoint` and inspect:

- `bridal-liquidation-feed.json`;
- bridal signals inside `domain-market-intelligence-brief.json`;
- whether OpenAI grouped any bridal signals into a hunt case.

A `VALID_ZERO` result is valid when no commercial bridal liquidation signal is found.
