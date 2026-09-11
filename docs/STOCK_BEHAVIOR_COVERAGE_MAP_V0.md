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
marketability_evidence: STRONG
buyer_family_evidence: MODERATE
current_level: E1 current buyer/operational evidence; exact concentrated-lot acceptance still unconfirmed
```

Evidence observed:
- Easy USA publicly sells wholesale footwear by case in single-size configurations, including cases where the buyer selects one size.
- Yneck currently operates an overstock trade desk that buys footwear/streetwear lots outright, including cancelled orders, end-of-run, returns and damaged-box stock.
- Yneck states that most of its retail listings are a single unit in a single size, demonstrating an operational resale model that can break acquired overstock into single-size units.
- Guinn's Shoes publicly buys footwear liquidations, overstock, store stock, returns, defects and samples in quantities from 1 to 10,000 pairs.
- Enviro Clear publicly buys footwear overstock/end-of-line/returns and states no minimum quantity for its stock-buying model.

Interpretation:
- single-size stock is demonstrably a tradable shape;
- direct buyers exist that can buy footwear in small or large quantities and downstream operations exist that retail single-size inventory;
- however, we still do **not** have a current European/Norwegian direct buyer explicitly stating that it will buy an arbitrary lot concentrated entirely in one size/model.

Development status: `MARKETABILITY_PROVEN / DIRECT_BUYER_FAMILY_EVIDENCED / EXACT_SINGLE-SIZE_ACCEPTANCE_GAP`

---

### 7. SINGLE-SKU / VERY LOW QUANTITY PER SKU

```text
marketability_evidence: MODERATE_TO_STRONG
buyer_family_evidence: MODERATE
current_level: E1 current low-minimum buyers + E4 historical footwear evidence
```

Evidence observed:
- adidas/Nafta `Hash Footwear` included SKUs containing fewer than 100 pairs.
- Guinn's Shoes publicly states it buys from 1 to 10,000 pairs.
- Enviro Clear publicly states there is no minimum quantity for its stock-buying model.

Interpretation:
- low quantity per SKU can be a recognized clearance-stock behavior;
- very low quantity is not automatically disqualifying;
- exact acceptance still depends on product category, buyer, geography and economics.

Development status: `BEHAVIOR_PROVEN / DEAL_SPECIFIC_FIT_REQUIRED`

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

## Norway / Scandinavia route evidence

Current Norway-specific evidence is now stronger at the **general restlager buyer** level:

- Miko Trading states it buys both small and large lots, including non-food, restlager, overproduction, damaged packaging and other irregular stock; its Havaristen channel actively sells clothing and footwear.
- Varekompaniet states it buys varepartier, restlager and konkursbo and resells to consumers and other physical/online stores.
- Partilageret states it buys unused surplus goods and restpartier and invites suppliers with restlager to submit stock.
- Verdioutlet states it buys goods from konkursbo and restlager and resells directly.
- Partihandel states it buys excess inventory/restpartier and currently sells apparel/footwear-related stock.

Interpretation:
- Norway has real direct-buyer/downstream routes for restlager and irregular inventory;
- these companies are `E1+ buyer-route evidence`, not yet deal-specific buyers for Case 001 or Case 002;
- none of the public evidence above explicitly proves acceptance of an arbitrary single-size footwear lot.

Development status: `NORWAY_GENERAL_ROUTE_PROVEN / AWKWARD-SHAPE_FIT_STILL_CASE_SPECIFIC`

---

## Current weakest gaps

Future buyer-side research should prioritize only these gaps unless a real case introduces a new stock behavior:

```text
GAP A — current Europe/Norway direct buyer explicitly accepting a FULL LOT concentrated in SINGLE_SIZE / SINGLE_MODEL
GAP B — Norway/Scandinavia-specific evidence for awkward stock shapes beyond generic restlager buying
GAP C — deal-specific absorbable quantity
GAP D — deal-specific price evidence, not just marketability
```

`BROKEN_SIZE_RUN` and `VERY_LOW_QUANTITY_PER_SKU` are no longer category-level marketability gaps.

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
