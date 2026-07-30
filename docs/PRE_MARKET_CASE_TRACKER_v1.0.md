# Pre-Market Case Tracker v1.0

## Goal

Turn the pre-market bankruptcy pilot into a persistent lifecycle system. The
tracker remembers each clothing estate, consumes repeated sale-channel search
reports, detects material changes, and creates a bounded human action queue.

It does not perform network requests, open candidate pages, send email, contact an
estate manager, bid, purchase, reserve goods, make payments, or make an automatic
investment decision.

## Input

One or more reports produced by:

```bash
python scripts/run_pre_market_sale_channel_search.py \
  --estate-orgnr 938018014
```

The tracker can also receive the previous registry from an earlier run.

```bash
python scripts/run_pre_market_case_tracker.py \
  --previous-registry artifacts/previous/pre-market-cases.json \
  --sale-channel-report artifacts/sale-channel/menswear/sale-channel-search.json \
  --sale-channel-report artifacts/sale-channel/keepfit/sale-channel-search.json \
  --output-dir artifacts/pre-market-case-tracker
```

On the first run, omit `--previous-registry`.

## Lifecycle states

```text
PRE_MARKET_LEAD
  -> ESTATE_MANAGER_IDENTIFIED
  -> NO_PUBLIC_SALE_CHANNEL_FOUND
  -> LIQUIDATION_CHANNEL_CANDIDATE_REQUIRES_PAGE_VERIFICATION
  -> SALE_LISTING_CANDIDATE_REQUIRES_PAGE_VERIFICATION
  -> VERIFIED_ACTIVE_INVENTORY_SALE
```

The state is derived conservatively from the current observation. Search snippets
never verify a sale or a liquidation mandate. Only
`VERIFIED_ACTIVE_INVENTORY_SALE` is eligible for the commercial Top 5 and
Analysis Engine.

## Persistent identity

Each estate has a stable case key:

```text
estate:{nine-digit estate organisation number}
```

Example:

```text
estate:938018014
```

A partial run updates only the observed cases and preserves other existing cases
in the registry.

## Change detection

The tracker records:

- new case creation;
- lifecycle state changes;
- new sale-listing candidate URLs;
- new liquidation-channel candidate URLs;
- transition to a verified active inventory sale.

It does not emit an alert for an identical repeated observation. Alerts are
reserved for new sale or liquidation developments and verified sales.

## Human action queue

The state determines one recommended operator action:

| State | Recommended action |
|---|---|
| `PRE_MARKET_LEAD` | `IDENTIFY_ESTATE_MANAGER` |
| `ESTATE_MANAGER_IDENTIFIED` | `RUN_TARGETED_SALE_CHANNEL_SEARCH` |
| `NO_PUBLIC_SALE_CHANNEL_FOUND` | `ASK_ESTATE_MANAGER_FOR_SALE_CHANNEL` |
| liquidation candidate | `VERIFY_LIQUIDATION_CHANNEL_MANDATE` |
| sale candidate | `VERIFY_PUBLIC_SALE_PAGE` |
| verified sale | `REVIEW_FOR_COMMERCIAL_ANALYSIS` |

Every action remains human-reviewed. No message is sent by the tracker.

## Outputs

```text
pre-market-cases.json
pre-market-case-changes.json
sale-channel-alerts.json
operator-action-queue.json
live-clothing-top5.json
operator-summary.txt
```

`live-clothing-top5.json` contains only cases already marked as verified active
inventory sales. An estate-manager identity, web-search result, candidate listing,
or possible liquidator cannot enter that file.

## Safety boundaries

- no automatic page opening;
- no FINN scraping;
- no automatic email or contact;
- no personal contact database;
- no automatic bid, purchase, reservation, commitment, or payment;
- no commercial eligibility before current sale and inventory verification.
