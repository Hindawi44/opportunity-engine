# Blinto Sweden public-access audit v1

## Decision

Blinto is suitable as a bounded secondary Sweden Clothing Inventory source.
Public auction pages expose enough item-specific information for conservative
discovery and verification without login. Clothing inventory is less frequent
than vehicles and machinery, so the source must use strict bulk-apparel gates.

## Public URL contract

Accepted shape:

```text
https://www.blinto.se/auction/<slug>/
```

The canonical stored host is `blinto.se`. When a slug ends in two numeric tokens,
they are interpreted separately:

```text
<object_id>-<auction_occurrence_id>
```

The object ID is not sufficient for deduplication because the same object can be
listed again under a later auction-occurrence ID. Historical suppression is
therefore occurrence-specific.

## Public fields observed

Exact auction pages can publicly expose:

- title and category;
- item/object ID;
- Swedish city;
- item description, quantities, sizes and condition;
- active or ended status and end time;
- highest or winning bid in SEK;
- reserve-price status;
- market or retail reference value;
- VAT/fee wording;
- loading-assistance availability;
- buyer responsibility for pickup and transport.

The pilot preserves source-native SEK values in source-specific fields. It never
writes them to `price_nok` or `bid_price_nok`.

## Positive apparel examples used for policy design

- bulk work trousers with 34 pairs;
- bulk workwear with 42 pairs;
- mixed workwear with 53 garments;
- high-visibility workwear with 112 articles;
- workwear/shoes/gloves with explicit item counts;
- larger mixed protective-clothing and footwear lots.

## Required false-positive exclusions

The gate rejects clothing-related words that describe equipment rather than
sellable apparel inventory, including:

- `klädskåp` / lockers;
- clothing racks and carts;
- shop or garment alarms and tags;
- hangers and drying cabinets;
- ordinary single garments without bulk evidence.

A result must contain both clothing evidence and bulk-commercial evidence.

## Source-scoped event rules

Only the item title and item-specific description determine the commercial event:

- explicit `konkursbo` or `konkursförvaltare` -> `COMPANY_BANKRUPTCY`;
- `utförsäljning` or closure wording -> `INVENTORY_LIQUIDATION`;
- `överskott`, `restlager` or `restparti` -> `WAREHOUSE_SURPLUS`;
- `parti med`, `stort parti` or `varulager` -> `LARGE_LOT_SALE`;
- otherwise -> `AUCTION`.

Generic wording that an item is sold for a VAT-liable business does not prove
bankruptcy.

## Safety and operational limits

- eight registered queries;
- one Brave request per registered query;
- exact auction-page verification only;
- no login, bidding, contacting, purchase or payment;
- no CAPTCHA solving, proxying, TLS bypass or hidden API access;
- no VAT, customs, logistics cost, currency conversion, ROI or profitability
  calculation;
- unresolved and ended pages remain outside analysis and Top 5.
