# Buyer Requirement Cards V0

**Status:** MANUAL / RESEARCH-ONLY / NO OUTREACH AUTHORIZATION

## Purpose

Define the minimum information needed to move from a buyer-family hypothesis to a serious buyer match.

These cards are not contact templates and do not authorize outreach.

---

## Card A — Broad Stocklot / Liquidation Buyer

Typical stock shapes:

- mixed lots;
- broken assortments;
- generic or branded stock;
- old season / discontinued;
- B-stock / returns where accepted;
- pallet / multi-pallet / warehouse quantities.

Minimum useful data:

```text
product_category
approx_quantity
unit_of_measure
stock_location
condition / grade
brand status (branded / generic / mixed / unknown)
model / SKU list if available
size / variant distribution if relevant
photos
packaging status
pallet/carton count if available
seller asking price if relevant
```

Strong-value additions:

```text
EAN / SKU list
quantity by SKU/model
quantity by size/variant
loading details
weight / dimensions
```

Evidence basis from current research:
- MD TRADE publicly requests complete data such as EAN/article list, quantity, warehouse location and price expectation and accepts A-stock, B-stock and saleable returns from one pallet upward.
- we-buy-stock.com publicly asks for photos or a short list and quantity, and buys footwear clearance/B-grade/returns/warehouse stock from 100 pairs to several thousand.
- XMBO publicly asks for stock details and buys broad surplus categories including branded/unbranded goods, returns/B-grade and discontinued/seasonal stock.

---

## Card B — Branded A-Stock / Off-Price Specialist

Typical stock shapes:

- branded A-stock;
- excess/unsold inventory;
- past-season stock;
- cancelled orders;
- samples, where accepted.

Material gates:

```text
brand
proof_of_originality / provenance
new / unused condition
original packaging percentage
resale restrictions
model/SKU/EAN
quantity by model
size / variant distribution
stock location
```

Do not route generic/unbranded stock here unless the buyer explicitly accepts it.

Evidence basis from current research:
- Antony Trade publicly states that it buys footwear stock only when it is new, 100% original, in original packaging and free to resell; it also accepts unsold/excess/past-season stock.

---

## Card C — Single-Model / Single-Size / Highly Concentrated Stock

Typical stock shape:

```text
SINGLE_MODEL
SINGLE_SKU or FEW_SKUS
SINGLE_SIZE or LIMITED_SIZES
HIGHLY_CONCENTRATED
```

This shape is not rejected automatically.

Minimum useful data:

```text
exact product/model
exact size/variant
exact quantity
category/use case
condition
brand/generic status
packaging
stock location
regulatory constraints if any
```

Buyer-family search may include specialist bulk resellers, exporters, market/discount traders, specialist outlets, or category-specific institutional/promotional buyers where evidence supports that use.

Important:

`buyer family = E0 hypothesis` until a real buyer demonstrates acceptance of that exact category/shape.

---

## Card D — Returns / B-Stock / Mixed Condition Buyer

Minimum useful data:

```text
total_quantity
grade definition
A/B/returns split
sample defect descriptions
functional/saleable status
packaging status
photos
quantity by SKU/category if available
stock location
```

Do not price this stock using A-stock comparables without adjustment/evidence.

---

## Card E — Regulated / Certification-Sensitive Buyer

Examples include PPE and other products where legal/conformity requirements materially affect resale.

Minimum useful data:

```text
manufacturer / importer identity if relevant
model/product identifier
intended use
certification / conformity evidence
required marks / declarations where applicable
batch / lot information if relevant
condition
packaging
quantity
stock location
```

Rules:

- stock shape does not prove regulatory fitness;
- a concentrated one-size lot can still be commercially valid;
- missing legally material conformity evidence can block a buyer route;
- do not describe protection/performance beyond verified evidence.

---

## Card F — Normal Retail / Outlet / Online Reseller

More likely to fit stock with useful retail assortment.

Useful data:

```text
brand/product identity
model assortment
size/variant curve
quantity by SKU/model/size
condition
packaging
photos
wholesale acquisition basis
recommended/observed retail context if evidenced
```

Do not treat a shop as a buyer merely because it sells similar products.

---

## Readiness states

```text
INSUFFICIENT_DATA
RESEARCHABLE
PRELIMINARY_MATCH
DATA_READY
DEAL_SPECIFIC_FIT
QUOTE_ELIGIBLE
```

Definitions:

- `INSUFFICIENT_DATA`: stock cannot yet be described enough to identify a meaningful buyer family.
- `RESEARCHABLE`: stock shape is sufficiently known to research buyer families.
- `PRELIMINARY_MATCH`: at least one E1+ buyer appears compatible with the known shape.
- `DATA_READY`: the material information that buyer family normally needs is available.
- `DEAL_SPECIFIC_FIT`: exact lot conditions match a buyer's evidenced buying conditions.
- `QUOTE_ELIGIBLE`: enough evidence exists to justify a quote request only if the project phase later authorizes outreach.

---

## Current cases

### Case 001 — footwear

Current state:

```text
RESEARCHABLE: YES
PRELIMINARY_MATCH: YES
DATA_READY: NO
```

Main missing fields:

```text
brand/SKU/EAN
quantity by model
exact size distribution
exact grade
packaging percentage/condition
pallet/carton count
```

### Case 002 — coverall

Current state:

```text
RESEARCHABLE: YES
PRELIMINARY_MATCH: PARTIAL
DATA_READY: NO
```

Main missing fields:

```text
regulatory/conformity evidence
manufacturer/product identity detail
exact permitted use/claims
```

The single-model/single-size shape is not the blocker.
