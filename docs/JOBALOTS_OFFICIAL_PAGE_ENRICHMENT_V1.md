# JOBALOTS_OFFICIAL_PAGE_ENRICHMENT_V1

## Purpose

Convert official Jobalots product links into source-backed decision-support records by reading the public product page itself instead of relying only on a search snippet.

## Bounded retrieval

- One Brave discovery query.
- One `robots.txt` request.
- At most three current `https://jobalots.com/en/products/...` pages per run.
- Published crawl delay is respected up to ten seconds.
- Response size is capped at 2 MB.
- Public HTML only: no login and no browser scripting.

## Extracted fields

When visible, the lane records current bid, currency, reference retail value, reserve price, quantity, pallet/box/lot type, weight, condition, vendor, warehouse location, SKU, auction end text, manifest availability and manifest links.

Each record includes the official URL and a SHA-256 digest of the page used as evidence.

## Decision boundary

Lot size is descriptive and never causes rejection. Missing information remains visible. Active records stay `B2B_LEAD_REQUIRES_VERIFICATION`; incomplete or ended records remain early signals.

The operator remains the only decision maker. Automatic contact, bidding, reservation, purchase, payment, Top 5 promotion and financial-analysis promotion are disabled.
