# Buyer Type Matrix V0

**Status:** MANUAL / COMMERCIAL-LEARNING / NO RUNTIME

## Purpose

Translate a verified `STOCK_SHAPE` into the **buyer families worth researching**.

This matrix does not decide BUY/REJECT and does not declare a company to be a buyer merely because its business looks related.

Core sequence:

```text
STOCK_IDENTITY
→ STOCK_BEHAVIOR
→ BUYER_FAMILY_HYPOTHESIS
→ EVIDENCED_BUYER_CANDIDATE
→ PRODUCT_FIT
→ QUANTITY_FIT
→ CONDITION_FIT
→ GEOGRAPHY_FIT
→ LOGISTICS_FIT
→ PRICE_EVIDENCE
```

## Buyer-family rule

`Stock shape` narrows the buyer search. It does not prove demand by itself.

A buyer family remains `HYPOTHESIS / E0` until at least one real buyer publishes or demonstrates that it accepts that type of stock.

A named company becomes a real buyer candidate only at `E1+`.

---

## Matrix

### 1. SINGLE_MODEL / SINGLE_SKU / SINGLE_SIZE / HIGHLY_CONCENTRATED

Possible buyer families to investigate:

- specialist bulk reseller;
- exporter;
- market trader / discount trader;
- promotional / uniform buyer when the product category supports that use;
- specialist outlet;
- geographic-demand buyer where the exact size/model has unusual local demand.

Rules:

- concentration is not an automatic rejection;
- normal retail buyers may have weak fit;
- do not invent demand for the exact size/model;
- the family stays `E0` until category-specific evidence exists.

### 2. MULTI_MODEL + BALANCED / FULL SIZE RUN + A_STOCK

Possible buyer families:

- retailer;
- outlet retailer;
- online reseller;
- wholesaler;
- off-price buyer;
- direct stocklot buyer.

This shape is often easier to place through normal retail/downstream channels, but the exit price still needs evidence.

### 3. MULTI_MODEL + BROKEN_SIZE_RUN / MIXED_SIZE_RUNS

Possible buyer families:

- stocklot liquidator;
- discount wholesaler;
- exporter;
- market trader;
- mixed-lot reseller;
- outlet / online reseller that accepts incomplete assortments.

Rules:

- incomplete sizes are a stock characteristic, not a failure;
- buyer evidence must show tolerance for mixed/broken assortments where material.

### 4. RETURNS / B_STOCK / MIXED_CONDITION

Possible buyer families:

- returns wholesaler;
- B-stock buyer;
- liquidator;
- discount reseller;
- market trader;
- exporter;
- recommerce/refurbishment buyer only where the product category supports it.

Evidence examples from current research:

- MD TRADE publicly states purchase of A-stock, B-stock and saleable returns, generally from one pallet upward.
- we-buy-stock.com publicly states purchase of B-grade/returns and clearance stock.
- XMBO publicly states purchase of returns and B-grade stock among other surplus categories.

Therefore this buyer family is `E1–E2 evidenced` in the general stocklot market, but each case still needs product/category fit.

### 5. OLD_SEASON / DISCONTINUED / SLOW_MOVING

Possible buyer families:

- off-price buyer;
- outlet;
- stocklot buyer;
- exporter;
- discount wholesaler;
- market trader.

Evidence examples:

- Antony Trade states it buys unsold/excess footwear including past seasons, subject to new/original/original-packaging requirements.
- XMBO states it buys end-of-life/discontinued models, seasonal stock and slow-moving inventory.
- we-buy-stock.com states it buys seasonal goods and discontinued models.

### 6. GENERIC_UNBRANDED / MIXED_BRANDED_AND_GENERIC

Possible buyer families:

- broad stocklot buyer;
- discount wholesaler;
- exporter;
- market trader;
- low-price online reseller;
- outlet/discounter where brand is not mandatory.

Rules:

- do not route automatically to brand specialists;
- buyer evidence must show that generic/unbranded goods are acceptable.

Current evidence:

- XMBO explicitly states that it deals in both branded and unbranded shoe stocklots.

### 7. BRANDED_A_STOCK + ORIGINAL_PACKAGING

Possible buyer families:

- brand-stock specialist;
- off-price footwear/fashion buyer;
- outlet retailer;
- premium stocklot wholesaler;
- international branded-stock trader.

Current evidence:

- Antony Trade states that it buys new, 100% original footwear in original packaging and accepts excess/unsold/past-season stock.

Brand/originality/packaging are material gates for this buyer family.

### 8. LARGE MIXED LOT / WAREHOUSE CLEARANCE

Possible buyer families:

- direct bulk liquidator;
- large stocklot wholesaler;
- warehouse-clearance buyer;
- exporter with consolidation capacity.

Evidence examples:

- XMBO states it can take entire excess inventories and operates warehouses in the Netherlands, Poland and Italy.
- we-buy-stock.com states it buys from single clearance lots up to full warehouse clearances and quantities from 100 pairs to several thousand pairs in footwear.
- Liquidato publishes completed acquisition cases ranging from pallets to full truck/warehouse-scale projects.

### 9. REGULATED / CERTIFICATION-SENSITIVE STOCK

Examples: PPE, protective garments, regulated workwear, some medical/safety products.

Possible buyer families:

- specialist industrial distributor;
- certified PPE/workwear buyer;
- stocklot buyer only if the goods can legally be resold;
- exporter only where destination-market compliance is evidenced.

Rules:

- stock shape and buyer fit are separate from regulatory fitness;
- missing required certification can block a route even when the quantity/shape fits;
- do not market a product as certified/protective beyond the evidence.

---

## Buyer candidate states

```text
FAMILY_HYPOTHESIS      = E0 only
EVIDENCED_BUYER        = buyer publicly claims or demonstrates relevant purchasing (E1+)
PRELIMINARY_FIT        = product/shape appears compatible, but deal data incomplete
DATA_READY             = material stock identity needed for buyer evaluation is available
DEAL_SPECIFIC_FIT      = exact lot matches the buyer's stated conditions
QUOTE_ELIGIBLE         = enough evidence exists to justify requesting a quote if project phase allows
QUOTE_OBTAINED         = our own price/quantity response exists (E5)
TRANSACTION_EVIDENCE   = our own completed/failed transaction evidence exists (E5)
```

Current project phase remains research-only. No outreach is authorized by this document.

---

## What NOT to do

Do not:

- search a generic buyer list before defining stock behavior;
- reject one-size, one-model, broken-size, returns or old-season stock automatically;
- call a retailer a buyer merely because it sells the same product;
- promote an E0 buyer-family hypothesis to a real buyer candidate without evidence;
- assume a brand specialist accepts generic stock;
- assume a returns buyer accepts A-stock at the same economics;
- assume regulatory fit from product wording;
- invent price, capacity, geography or logistics tolerance.

---

## Current validation cases

### Case 001 — ~3,600 pairs footwear

Known shape:

```text
MODEL_STRUCTURE: FEW_MODELS (10–12 stated)
SIZE_RANGE: 29–46 stated
PRODUCT_MIX: RELATED_MIX
INTERNAL_QUANTITY_DISTRIBUTION: UNKNOWN
SIZE_DISTRIBUTION: UNKNOWN
BRAND_STRUCTURE: UNKNOWN
CONDITION_STRUCTURE: seller claims NEW LOT; exact grade UNKNOWN
```

Buyer-family implication:

- broad footwear stocklot buyers can be researched now;
- brand specialists stay conditional;
- exact route cannot be promoted to deal-specific until internal distribution/brand/grade data are known.

### Case 002 — 50 Coverall PE-NW XL

Known shape:

```text
MODEL_STRUCTURE: SINGLE_MODEL
SIZE_STRUCTURE: SINGLE_SIZE (XL)
QUANTITY_DISTRIBUTION: HIGHLY_CONCENTRATED
PRODUCT_MIX: HOMOGENEOUS
CONDITION: stated NEW
REGULATORY_FIT: UNKNOWN
```

Buyer-family implication:

- single-model/single-size does not reject the lot;
- buyer research should target industrial/workwear/PPE-capable routes rather than generic retail;
- certification/conformity evidence is a separate material gate.

---

## Public evidence used to validate buyer-family behavior

- XMBO Trading — stocklots, returns/B-grade, discontinued/seasonal/slow-moving goods, branded and unbranded footwear, entire excess inventory.
- MD TRADE — A-stock, B-stock, returns; from one pallet upward; mixed and homogeneous footwear lots.
- we-buy-stock.com — footwear clearance, samples, B-grade/returns, warehouse clearance; 100 pairs to several thousand; Europe-wide.
- Antony Trade — new/original/original-packaged branded footwear, including past-season excess/unsold stock.
- Liquidato — published completed stock-acquisition cases demonstrating pallet/truck/large-lot capacity.

These sources prove buyer-family behavior only to the extent explicitly stated. Deal-specific fit remains case-by-case.
