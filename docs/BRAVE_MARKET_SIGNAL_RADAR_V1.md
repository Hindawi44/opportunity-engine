# BRAVE_MARKET_SIGNAL_RADAR_V1

## Product position

This is a bounded extension of the existing three-market daily intelligence checkpoint.
It does not rebuild the engine, add a fourth country, create a second database path, or turn search results directly into opportunities.

The product remains:

> One daily clothing-inventory market-intelligence bulletin for Norway, Sweden, and Germany.

## Why this exists

The direct collectors find active listings and auctions. Official registers find verified legal events when machine-readable access exists. The missing layer was broad public-web recall for early signals such as:

- clothing-store closure or wind-down;
- liquidation or insolvency involving a clothing business;
- warehouse surplus, rest stock, or inventory-release language;
- auction announcements that may later produce a direct clothing lot.

Brave Search is used only as discovery transport. A Brave result is not verification and is not an opportunity.

## Execution order

The existing daily checkpoint remains the single operator workflow.

1. Run the six existing bounded source paths.
2. Build the three-market checkpoint.
3. Extract and sanitize explicit Blinto seller identity evidence.
4. Resolve Swedish company identities when explicit evidence exists.
5. Run the Brave market-signal radar for NO, SE, and DE.
6. Run the direct official-source adapters.
7. Merge all standalone signals into the existing market signal reports.
8. Persist through the existing SQLite signal repository.
9. Produce one Arabic market-intelligence bulletin and one human action.

## Bounds

- Markets: NO, SE, DE only.
- Queries: maximum 2 per market.
- Total Brave requests: maximum 6 per run.
- Results: maximum 10 per query.
- Freshness: previous month (`pm`) by default.
- Accepted result requires both:
  - clothing-domain evidence; and
  - closure, liquidation, insolvency, surplus, or auction-event evidence.
- Duplicate URLs are canonicalized and merged.
- Missing Brave credentials produce `BLOCKED_CONFIGURATION`; no result is fabricated.
- Partial provider failures produce `PARTIAL_RETRIEVAL` or `BLOCKED_RETRIEVAL`.

## Signal contract

Accepted results are stored as `MarketSignalRecord` with:

- stable identity based on market plus canonical URL;
- actual public source URL;
- market signal type;
- title and snippet evidence;
- unverified public-web evidence status;
- `related_opportunity_id = null`;
- `status = WATCH`;
- explicit `signal_only` and `not_an_opportunity` metadata.

The existing SQLite persistence decides whether a signal is new, unchanged, or meaningfully changed across runs.

## Safety lock

Always false:

- automatic contact;
- automatic bid;
- automatic purchase;
- automatic payment.

No search result may bypass the current human verification and commercial-analysis paths.

## What is intentionally unchanged

- Norway, Sweden, and Germany collectors;
- canonical opportunity records;
- lifecycle classifier;
- SQLite, SQLAlchemy, and Alembic persistence;
- cross-run continuity;
- FINN Gmail intake;
- human review;
- one-opportunity commercial analysis;
- the six-source checkpoint accounting.

## Next validation gate

After merge, run `Multi-Market Daily Operator Checkpoint` from `main` twice.

The first run confirms live Brave retrieval and signal persistence. The second run confirms stable replay: unchanged Brave URLs must not appear as new signals again, while meaningful title, evidence, or state changes may create a changed observation.
