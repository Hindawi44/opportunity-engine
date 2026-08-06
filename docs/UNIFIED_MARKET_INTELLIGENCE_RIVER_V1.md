# UNIFIED_MARKET_INTELLIGENCE_RIVER_V1

## Product boundary

This change does not rebuild any collector and does not add a country or source. It reads the artifacts already produced by the daily checkpoint and creates a unified, read-only decision projection.

The flow is:

```text
source artifact
→ source observation
→ deduplicated intelligence item
→ linked market case
→ decision card
```

Raw source artifacts remain unchanged and continue to be the evidence layer.

## Inputs

The bounded projection reads the existing daily artifacts for:

- the domain market-intelligence brief;
- Brave early signals;
- bridal liquidation signals;
- fabric procurement;
- Merkandi;
- Fashion Stock Netherlands;
- Stock-Hurt search and official-page enrichment;
- Jobalots search, official-page enrichment and official-catalog discovery.

Missing optional inputs are reported. Invalid JSON inputs produce an explicit partial or failed river status instead of being silently ignored.

## Unified record kinds

The river preserves the distinction between different kinds of information:

- `MARKET_SIGNAL`;
- `BUSINESS_EVENT_SIGNAL`;
- `B2B_STOCK_OFFER`;
- `AUCTION_LOT`;
- `BRIDAL_LIQUIDATION_SIGNAL`;
- `FABRIC_PROCUREMENT_ITEM`;
- `CANONICAL_OPPORTUNITY`;
- `HISTORICAL_EVIDENCE`.

A market signal is not promoted into an opportunity. Lot size is descriptive and never causes rejection.

## Identity and deduplication

Signals use their stable signal identity. Canonical opportunities use their opportunity identity. Source offers use their canonical official URL when available.

Repeated observations from several artifacts are merged into one intelligence item. The richer source-backed version wins, while source artifacts and evidence are preserved.

## Market cases

Items are linked into a market case using, in order:

1. organisation number;
2. company identity;
3. seller identity for B2B, auctions and fabric procurement;
4. the individual item when no safe relationship is available.

The first version emits relationships such as:

- `SUPPORTS`;
- `SAME_ORGANISATION_NUMBER`;
- `SAME_COMPANY`;
- `SAME_SELLER`;
- `SAME_MARKET_CASE`.

No speculative fuzzy company matching is used.

## Outputs

The daily checkpoint gains three artifacts:

```text
unified-intelligence-items.json
unified-market-cases.json
unified-daily-decision-brief.json
```

A compact summary is also attached to the existing domain brief.

## Decision boundary

The river is advisory and human-controlled:

```text
decision_owner: HUMAN_OPERATOR
quantity_size_rejection_enabled: false
promotion_to_opportunity_allowed: false
automatic_contact: false
automatic_bid: false
automatic_reservation: false
automatic_purchase: false
automatic_payment: false
```

Persistence and cross-run case history are intentionally deferred. V1 unifies the current checkpoint first without changing the established SQLite lifecycle path.
