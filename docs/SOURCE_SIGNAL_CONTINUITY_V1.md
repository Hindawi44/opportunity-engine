# SOURCE_SIGNAL_CONTINUITY_V1

## Product boundary

This change does not turn the project into a FINN-only collector. The product remains the three-market clothing-inventory intelligence bulletin for Norway, Sweden, and Germany.

The change closes one missing persistence path inside the existing multi-source checkpoint:

- sources that already emit canonical reports keep their current behavior;
- a source that emits discovery candidates but no canonical report is adapted into the existing `OpportunityRecord` report and SQLite repository;
- FINN saved-search email also emits a durable `MarketSignalRecord` because email is an observation channel and not verified sale evidence.

No collector, score, lifecycle rule, human-review boundary, database technology, UI, country coverage, automatic contact, bid, purchase, reservation, or payment behavior is replaced.

## FINN behavior

Stable identity is the numeric FINN listing ID:

```text
finn-listing:<listing_id>
```

The persisted signal state contains only market-relevant email claims:

- title;
- canonical FINN URL;
- advertised price when present;
- advertised location when present;
- symbolic-price flag;
- listing status remains unknown until public-page verification.

Mailbox message fingerprints and repeated delivery timestamps are deliberately excluded from the state hash. Re-reading the same alert therefore does not create a false market change. A changed advertised title, price, location, or symbolic-price state creates one append-only signal observation.

Absence from a later email query does not prove that a listing ended. Closure still requires the existing verification path.

## Cross-run continuity

The checkpoint artifact restore allowlist includes:

```text
no-finn-email/opportunity_engine.db
```

This preserves both canonical lifecycle history and market-signal observations across successful checkpoint runs.
