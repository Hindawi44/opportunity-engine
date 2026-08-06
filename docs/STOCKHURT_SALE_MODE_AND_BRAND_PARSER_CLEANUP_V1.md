# STOCKHURT_SALE_MODE_AND_BRAND_PARSER_CLEANUP_V1

## Problem

Live run #110 proved that Stock-Hurt catalogue discovery and redirect recovery worked, but global navigation text polluted two product-level fields:

- products discovered from the wholesale shop were labelled as auctions because the navigation contains links named `Auction` and `Auctions`;
- the generic brand parser captured text after `Brand:` through later fields such as `Category`, `Unit`, and `Grade`.

## Correction

The catalogue discovery scope is authoritative when available:

- `WHOLESALE_SHOP` becomes `FIXED_PRICE_OR_ENQUIRY` and `SPECIFIC_STOCK_OFFER`;
- `PALLET_AUCTIONS` becomes `AUCTION` and `PALLET_AUCTION_OFFER`.

When catalogue provenance is unavailable, only transaction fields such as a visible current bid or auction end time may classify the page as an auction. Navigation-only auction words are retained as ignored evidence and cannot change the sale mode.

Brands are extracted only from:

- the product title before inventory descriptors such as Grade, Clothing, Jackets, or unit suffixes;
- an explicit product-level `Brand:` field ending before Category, Unit, Grade, Condition, Price, SKU, or related field labels.

Footer, navigation, related-product names, descriptive sentences, and generic inventory words are excluded.

## Decision boundary

The correction does not change the commercial safety contract. The result remains read-only, quantity does not cause rejection, and `decision_owner` remains `HUMAN_OPERATOR`. Automatic contact, bidding, reservation, purchase, and payment remain disabled.
