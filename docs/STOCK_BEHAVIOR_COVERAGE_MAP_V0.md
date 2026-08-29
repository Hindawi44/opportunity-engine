# Stock Behavior Coverage Map V0

**Status:** MANUAL / RESEARCH-ONLY / NO RUNTIME

## Purpose

Track which stock behaviors already have real market evidence and which remain weak hypotheses.

This prevents endless buyer searching and keeps future work focused only on evidence gaps.

Evidence levels follow the Commercial Foothold rules:

```text
E0 — hypothesis only
E1 — buyer/channel claim
E2 — quantified buyer / stated buying conditions
E3 — operational evidence
E4 — published transaction / contractual market evidence
E5 — our own quote / transaction evidence
```

Important distinction:

```text
MARKETABILITY_EVIDENCE != DIRECT_BUYER_EVIDENCE
```

A stock shape may be demonstrably tradable without yet having a named direct buyer for our exact lot.

---

## Coverage matrix

### 1. RETURNS / B-STOCK / MIXED CONDITION

```text
marketability_evidence: STRONG
buyer_family_evidence: STRONG
current_level: E2–E3 external
```

Evidence observed:
- Pinterol publicly buys apparel and footwear returns, B-stock, overstock and end-of-line inventory across UK/EU and coordinates collection/logistics.
- MD TRADE publicly buys A-stock, B-stock and saleable returns.
- we-buy-stock.com and XMBO publicly accept returns/B-grade stock in relevant categories.
- B-Stock Supply Europe operates B2B liquidation marketplaces for customer returns, overstock and other secondary inventory.

Development status: `COVERED_FOR_RESEARCH`

---

### 2. OLD-SEASON / DISCONTINUED / SLOW-MOVING

```text
marketability_evidence: STRONG
buyer_family_evidence: MODERATE_TO_STRONG
current_level: E1–E2 external
```

Evidence observed:
- Antony Trade publicly accepts unsold/excess and past-season footwear subject to originality/packaging requirements.
- XMBO publicly states it buys discontinued/end-of-life, seasonal and slow-moving footwear stock.
- Pinterol publicly buys end-of-line/aged fashion stock.

Development status: `COVERED_FOR_RESEARCH`

---

### 3. GENERIC / UNBRANDED / MIXED-BRAND

```text
marketability_evidence: STRONG
buyer_family_evidence: MODERATE
current_level: E1–E2 external
```

Evidence observed:
- XMBO explicitly deals in branded and unbranded footwear stocklots.
- Pinterol explicitly evaluates both single-brand and mixed-brand apparel/footwear lots.

Development status: `COVERED_FOR_RESEARCH`

---

### 4. LARGE MIXED LOT / PALLET / WAREHOUSE CLEARANCE

```text
marketability_evidence: STRONG
buyer_family_evidence: STRONG
capacity_evidence: STRONG
current_level: E2–E4 external
```

Evidence observed:
- XMBO states it can take complete excess inventories.
- we-buy-stock.com states footwear scale from 100 pairs to several thousand and warehouse-clearance buying.
- Liquidato publishes large stock acquisition cases.
- B-Stock operates pallet, LTL, truckload and multi-truckload B2B liquidation channels.

Development status: `COVERED_FOR_RESEARCH`

---

### 5. BROKEN SIZE RUN / INCOMPLETE SIZE RUN

```text
marketability_evidence: STRONG
buyer_family_evidence: STRONG
current_level: E1 current direct-buyer evidence + E4 historical contract evidence
```

Evidence observed:
- Pay For Clearance currently states that it buys footwear in bulk and explicitly accepts both full size runs and broken size stock.
- In Nafta Traders Inc. v. adidas America Inc., the court described the adidas/Nafta clearance agreement as including `Hash Footwear`, defined as SKUs containing fewer than 100 pairs or incomplete size runs of specified footwear.
- The adidas/Nafta agreement involved a merchandise liquidator/reseller purchasing clearance footwear categories.

Interpretation:
- incomplete size runs are a documented commercial clearance category, not inherently unsaleable stock;
- a current direct buyer explicitly accepts broken-size footwear;
- the remaining uncertainty is now deal-specific: product, quantity, geography, condition, price and logistics.

Development status: `COVERED_FOR_RESEARCH / DEAL_SPECIFIC_BUYER_FIT_REQUIRED`

---

### 6. SINGLE-SIZE / SINGLE-MODEL STOCK

```text
marketability_evidence: MODERATE_TO_STRONG
buyer_family_evidence: WEAK_TO_MODERATE
current_level: E1 sales-channel evidence; direct-buyer evidence still weak
```

Evidence observed:
- Easy USA publicly sells wholesale footwear by case in single-size configurations, including a 36-pair case where buyers can select a single size.

Interpretation:
- single-size stock is demonstrably a tradable wholesale shape;
- this proves `SINGLE_SIZE != UNSALEABLE`;
- it does **not** yet prove a strong current direct-liquidator buying route for arbitrary single-size stock.

Development status: `MARKETABILITY_PROVEN / DIRECT_BUYER_GAP`

---

### 7. SINGLE-SKU / VERY LOW QUANTITY PER SKU

```text
marketability_evidence: MODERATE
buyer_family_evidence: MODERATE historical footwear evidence
current_level: E4 external historical for <100-pair SKU clearance
```

Evidence observed:
- adidas/Nafta `Hash Footwear` included SKUs containing fewer than 100 pairs.

Interpretation:
- low quantity per SKU can be a recognized clearance-stock behavior;
- exact acceptance depends on product category, buyer, geography and economics.

Development status: `BEHAVIOR_PROVEN / CURRENT_DIRECT_BUYER_GAP`

---

### 8. REGULATED / PPE / CERTIFICATION-SENSITIVE STOCK

```text
marketability_evidence: MODERATE
buyer_family_evidence: MODERATE
regulatory_gate: MATERIAL
current_level: E1–E2 external buyer/category evidence
```

Evidence observed:
- specialist PPE/workwear buyers exist and may buy coveralls/workwear stock.
- stock shape such as one model/one size is not itself the blocker.

Critical rule:
- legal/conformity evidence must be separated from stock shape;
- missing certification can block resale even when quantity/shape has a buyer route.

Development status: `BUYER_FAMILY_EXISTS / REGULATORY_DATA_REQUIRED`

---

### 9. FULL SIZE RUN / BALANCED A-STOCK

```text
marketability_evidence: STRONG
buyer_family_evidence: STRONG
current_level: E1–E3 external
```

Normal retail, outlet, online reseller, wholesaler, off-price and stocklot routes are widely evidenced for useful retail assortments.

Development status: `COVERED_FOR_RESEARCH`

---

## Current weakest gaps

Future buyer-side research should prioritize only these gaps unless a real case introduces a new stock behavior:

```text
GAP A — current direct buyers that explicitly buy SINGLE_SIZE / SINGLE_MODEL lots
GAP B — current direct buyers that explicitly buy VERY LOW QUANTITY PER SKU where this matters
GAP C — Norway/Scandinavia-specific buyers for awkward stock shapes
GAP D — deal-specific price evidence, not just marketability
```

`BROKEN_SIZE_RUN` is no longer a category-level buyer-evidence gap because a current direct buyer explicitly accepts broken-size footwear.

Do not spend time repeatedly proving already-covered behaviors such as returns, B-stock, generic stock, old-season stock, large mixed lots or broken-size footwear unless new evidence contradicts current understanding.

---

## Stop rule

A stock behavior is considered sufficiently covered for manual buyer research when:

```text
1. marketability is evidenced; AND
2. at least one buyer family is evidenced at E1+; AND
3. the remaining uncertainty is deal-specific, not category-level.
```

Once covered, move to the real case question:

```text
WHO BUYS THIS EXACT LOT?
AT WHAT QUANTITY?
AT WHAT PRICE?
WITH WHAT FRICTION?
```

Do not keep adding buyer names merely to make the list longer.
