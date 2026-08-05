# FASHION_STOCK_NETHERLANDS_FEED_V1

## Purpose

Monitor official Fashion Stock Netherlands domains for branded clothing stock,
leftovers, overproduction, wholesale lots, and catalogue signals.

The feed is decision-support intelligence. It shows large and small lots alike,
preserves incomplete serious signals, and leaves all commercial decisions to the
human operator.

## Approved official domains

- `fashion-stock.eu`
- `fashionstock.eu`
- `fashion-stock.nl`

The collector uses two bounded official-domain searches per daily run. The primary
stock archive and the legacy shop domain are both covered. The third domain is
accepted when it appears in results but does not consume an extra search request.

## Candidate handling

A specific offer may become `B2B_LEAD_REQUIRES_VERIFICATION`. A catalogue page or
an offer missing public commercial fields remains
`EARLY_B2B_SIGNAL_REQUIRES_VERIFICATION`.

The feed extracts when visible:

- quantity and unit;
- lot-size band;
- MOQ;
- price and currency;
- brands;
- condition;
- stock location;
- manifest or stock-list evidence;
- authenticity evidence;
- shipping information;
- missing information and verification blockers.

No result is rejected because the quantity is large. The operator reviews the
source, collects missing numbers, calculates freight/import VAT/landed cost,
negotiates, and decides.

## Output and trust boundary

The daily run writes `fashion-stock-netherlands-feed.json` and attaches
`fashion_stock_netherlands_feed` to the daily JSON and text bulletins.

The lane is read-only: no contact, reservation, purchase, payment, Top 5 promotion,
or automatic opportunity promotion.
