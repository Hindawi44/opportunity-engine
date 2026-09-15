# Stock Behavior Rules V0

**Status:** MANUAL / COMMERCIAL-LEARNING FOUNDATION / NO RUNTIME

## Purpose

Define what a stock lot **is** before any buyer matching, price judgment, or commercial decision.

A stock lot is not required to be retail-ready, balanced, complete, fashionable, branded, or perfectly assorted.

A lot may be commercially awkward and still be a valid stock opportunity.

The job of this layer is:

```text
Find Stock
→ Describe Stock Shape / Behavior
→ Identify Buyer Type That Accepts That Shape
→ Check Quantity Fit
→ Gather Price Evidence
→ Measure Friction
→ Decide
```

This layer comes **before Buyer Matching**.

---

## Core rule

```text
TOTAL QUANTITY DOES NOT DEFINE THE STOCK.
```

Commercial behavior depends on the internal structure of the lot.

A lot of 10,000 items may be:

- one model / one size;
- one model / full size run;
- many models / broken size runs;
- many models / balanced size runs;
- branded A-stock;
- generic stock;
- returns;
- B-stock;
- old season;
- mixed condition;
- random assortment.

All of these can still be valid stock lots.

The system must **describe the shape first**, not reject it because it looks imperfect.

---

## Non-rejection rules

The following conditions are **not automatic rejection reasons**:

- one model only;
- one SKU only;
- one size only;
- one color only;
- incomplete size runs;
- broken assortments;
- old-season goods;
- discontinued models;
- overproduction;
- surplus inventory;
- restlager / leftovers;
- customer returns;
- B-stock;
- mixed brands;
- generic / unbranded goods;
- high concentration in one model or size;
- mixed condition;
- awkward quantities.

These characteristics change:

```text
buyer type
price
absorbable quantity
logistics
sorting effort
sell-through time
risk
```

They do **not** automatically mean `BAD STOCK`.

---

## Stock Shape dimensions

Every commercially studied lot should be described across the following dimensions when evidence exists.

### 1. MODEL_STRUCTURE

```text
SINGLE_MODEL
FEW_MODELS
MULTI_MODEL
UNKNOWN
```

### 2. SKU_STRUCTURE

```text
SINGLE_SKU
FEW_SKUS
MULTI_SKU
UNKNOWN
```

### 3. SIZE_STRUCTURE

```text
SINGLE_SIZE
LIMITED_SIZES
FULL_SIZE_RUN
BROKEN_SIZE_RUN
MIXED_SIZE_RUNS
UNKNOWN
NOT_APPLICABLE
```

### 4. COLOR_STRUCTURE

```text
SINGLE_COLOR
LIMITED_COLORS
MULTI_COLOR
UNKNOWN
NOT_APPLICABLE
```

### 5. QUANTITY_DISTRIBUTION

```text
BALANCED
CONCENTRATED
HIGHLY_CONCENTRATED
RANDOM
UNKNOWN
```

This describes whether the lot is evenly distributed or dominated by one/few models, SKUs, sizes, or colors.

### 6. PRODUCT_MIX

```text
HOMOGENEOUS
RELATED_MIX
MIXED
RANDOM_MIX
UNKNOWN
```

### 7. BRAND_STRUCTURE

```text
SINGLE_BRAND
MULTI_BRAND
GENERIC_UNBRANDED
MIXED_BRANDED_AND_GENERIC
UNKNOWN
```

### 8. CONDITION_STRUCTURE

```text
A_STOCK_NEW
B_STOCK
RETURNS
USED
DAMAGED
MIXED_CONDITION
UNKNOWN
```

### 9. SEASON / AGE STRUCTURE

```text
CURRENT_SEASON
OLD_SEASON
DISCONTINUED
MIXED_AGE
UNKNOWN
NOT_APPLICABLE
```

### 10. PACKAGING_STRUCTURE

```text
ORIGINAL_PACKAGING
PARTIAL_ORIGINAL_PACKAGING
REPACKED
NO_PACKAGING
MIXED_PACKAGING
UNKNOWN
```

### 11. LOT_ORIGIN

Record only when evidenced:

```text
OVERPRODUCTION
SURPLUS
CANCELLED_ORDER
RESTLAGER
STORE_CLOSURE
BANKRUPTCY
RETURNS
WAREHOUSE_CLEARANCE
SEASONAL_CLEARANCE
DISCONTINUED_STOCK
OTHER_VERIFIED
UNKNOWN
```

**Never infer the origin from lot size alone.**

Large quantity != bankruptcy.
Low price != liquidation.
Old stock != closure.

---

## Stock Behavior principle

The stock shape determines the likely buyer behavior.

Examples:

### Example A — one model, one size, high quantity

```text
MODEL_STRUCTURE: SINGLE_MODEL
SIZE_STRUCTURE: SINGLE_SIZE
QUANTITY_DISTRIBUTION: HIGHLY_CONCENTRATED
```

This is **not automatically rejected**.

Likely buyer families may differ from normal retail:

- exporters;
- promotional / uniform buyers;
- market traders;
- specialist outlets;
- bulk resellers;
- geographic markets where that size/product has demand.

### Example B — many models, balanced size runs

```text
MODEL_STRUCTURE: MULTI_MODEL
SIZE_STRUCTURE: FULL_SIZE_RUN / MIXED_SIZE_RUNS
QUANTITY_DISTRIBUTION: BALANCED
```

This may fit:

- retailers;
- outlets;
- online resellers;
- wholesalers;
- direct stocklot buyers.

### Example C — returns / mixed condition

```text
CONDITION_STRUCTURE: RETURNS / MIXED_CONDITION
```

Do not compare it with A-stock economics.

Its buyer family and price evidence must come from buyers who explicitly accept returns / mixed-grade goods.

---

## Buyer Matching rule

Buyer matching must start from stock behavior, not from a generic company list.

```text
STOCK_SHAPE
→ BUYER_TYPE
→ PRODUCT_FIT
→ QUANTITY_FIT
→ CONDITION_FIT
→ GEOGRAPHY_FIT
→ LOGISTICS_FIT
→ PRICE_EVIDENCE
```

A buyer that is excellent for balanced branded retail stock may be wrong for:

- one-size stock;
- B-stock;
- random mixed lots;
- generic goods;
- old-season goods.

A different buyer may value exactly those shapes.

---

## UNKNOWN rule

```text
UNKNOWN != BAD
UNKNOWN != REJECTED
```

Unknown means the evidence is missing.

The system must separate:

```text
KNOWN_UNFAVORABLE
```

from:

```text
UNKNOWN
```

Only verified facts can define the stock shape.

---

## Material-risk rule

A stock shape becomes a commercial blocker only when the shape creates a **verified buyer, legal, economic, or operational failure**.

Examples:

- no evidenced buyer route for the exact shape;
- goods cannot legally be sold in the intended market;
- certification required but absent;
- transport/storage friction destroys economics;
- verified condition makes the goods commercially unsellable;
- buyer-specific restrictions make the lot incompatible;
- realistic exit evidence is below total landed cost.

Imperfection alone is not a blocker.

---

## Minimum Stock Identity Record

Before buyer matching, record as much as evidence allows:

```text
category:
subcategory:
total_quantity:
unit_of_measure:
model_structure:
sku_structure:
size_structure:
color_structure:
quantity_distribution:
product_mix:
brand_structure:
condition_structure:
season_age_structure:
packaging_structure:
lot_origin:
location:
certification_or_regulatory_requirements:
material_unknowns:
source_evidence:
```

Unknown fields remain `UNKNOWN`.

---

## Decision boundary

This layer does **not** decide BUY / REJECT.

It only answers:

```text
WHAT KIND OF STOCK IS THIS?
```

The next layer answers:

```text
WHO BUYS THIS KIND OF STOCK?
```

Then commercial evidence answers:

```text
AT WHAT QUANTITY, PRICE, FRICTION, AND TIME-TO-CLEAR?
```

---

## Relationship to Commercial Foothold

This rule set belongs immediately before downstream buyer research in the Commercial Foothold Learning Loop.

Canonical sequence becomes:

```text
Find Deal
→ Define Stock Identity / Behavior
→ Identify Exit Routes
→ Identify Downstream Buyers
→ Estimate Absorbable Quantity
→ Gather Price Evidence
→ Measure Friction
→ CONTINUE / NEED_EVIDENCE / STOP
→ Record Commercial Lesson
→ Update Foothold Hypothesis
```

## Guardrails

- No Search Engine V1 changes.
- No new runtime.
- No automated BUY / REJECT score.
- No assumption that messy stock is bad stock.
- No assumption that clean stock is good stock.
- No buyer invented from product similarity alone.
- No price invented from asking prices alone.
- Unknown remains `UNKNOWN`.
- Commercial fit must be evidenced case by case.
