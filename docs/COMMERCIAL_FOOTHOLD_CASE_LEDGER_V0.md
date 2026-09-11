# Commercial Foothold Case Ledger V0

This ledger is the human case history for `COMMERCIAL_FOOTHOLD_LEARNING_LOOP_V0`.

It is not an automated score table.

Each case exists to improve commercial understanding and test whether a repeatable market foothold is emerging.

---

## Case 001 — 3,600-pair footwear stock

### Status

`NEED_EVIDENCE`

### Why it attracted attention

- approximately 3,600 pairs;
- fixed seller price: 150,000 NOK before VAT;
- entry basis: approximately 41.7 NOK per pair before buyer fees, transport and other friction;
- the live listing states 10–12 footwear models for women, men and children;
- stated size span is EU 29–46;
- the listing describes the stock as a new lot of leisure / casual footwear.

### Verified live listing facts — 2026-08-28

```text
listing_channel: Auksjonen.no
listing_id: 572303
mirror_channel: Mascus
mascus_id: 798F63C6
seller: FAMILY MARKET AS
seller_org_no: 821703972
seller_company_status: ACTIVE
seller_registered_for_vat: YES
seller_business_address: Ringvålvegen 4, 7080 Heimdal, Norway
stock_location: Heimdal, Norway
listing_type: FIXED_PRICE
listing_price_ex_vat_nok: 150000
quantity_pairs: ~3600
stated_model_count: 10-12
customer_segments: WOMEN + MEN + CHILDREN
stated_size_range_eu: 29-46
condition_claim: NEW LOT
product_description: leisure / casual footwear
public_listing_photos: 13
visual_styles_observed: sneakers + high-top/casual boots + mixed casual footwear
brand_mix: UNKNOWN
exact_models: UNKNOWN
quantity_per_model: UNKNOWN
size_distribution_inside_29_46: UNKNOWN
packing_list: UNKNOWN
box / packaging condition: UNKNOWN
grade_A_B_returns: UNKNOWN
buyer_fees: UNKNOWN
transport_cost: UNKNOWN
reason_for_sale: UNKNOWN
bankruptcy_or_closure_evidence: NONE FOUND
```

### Evidence correction from seller verification

The seller is currently an active Norwegian company and is registered for VAT.

No current evidence was found that this stock is being sold because of bankruptcy or business closure.

Therefore:

```text
reason_for_sale: UNKNOWN
liquidation_assumption: NOT ALLOWED
```

A large lot alone is not evidence of insolvency or closure.

### Image evidence boundary

The public listing images confirm a mixed set of casual footwear styles and visible product packaging / boxes in some photos.

The public thumbnails do **not** provide reliable enough evidence to identify the full brand mix, exact model names, exact size distribution, or quantities per model.

Those fields remain `UNKNOWN` until a seller inventory list, packing list, EAN/SKU list, or higher-quality product documentation is obtained.

### Missing facts that can materially change the case

- brands and authenticity evidence;
- exact model / SKU / EAN list;
- quantity per model;
- exact size distribution within the stated 29–46 range;
- women / men / children quantity split;
- confirmation whether all stock is first-quality new A-stock, or whether any B-grade / returns are included;
- original-box percentage and packaging condition;
- packing list / pallet count;
- buyer fees;
- transport / loading details;
- reason for sale.

### Exit routes currently evidenced

#### Route A — Direct European bulk buyer

Observed market evidence shows direct buyers in Germany / Netherlands that buy footwear stock, including mixed lots and large quantities.

Current evidence state: `E2–E4 external evidence`

Commercial use:

- fastest risk-transfer route;
- likely lower unit exit price;
- strongest fallback route if the lot is commercially acceptable.

Missing:

- direct quote for this exact lot;
- Norway pickup / freight economics for each buyer;
- exact product fit.

#### Route B — European B2B lot resale

Observed market evidence shows real footwear lots in quantities from tens/hundreds to thousands of pairs.

Current evidence state: `E2–E4 external market evidence`

Commercial use:

- split the stock into 100–500 pair lots where assortment supports it;
- potentially higher unit exit price than a full-lot direct buyer;
- slower time-to-clear and higher unsold-tail risk.

Missing:

- realistic price corridor for the exact grade / brand / size curve;
- time-to-clear evidence for comparable lots.

#### Route C — Nordic downstream micro-lots

Potential buyer segment:

- online resellers;
- small outlets;
- market traders;
- independent stores.

Potential lot shape:

- roughly 20–150 pairs depending on buyer;
- useful size curve;
- clear product photos and inventory data.

Current evidence state: `E0–E2`, depending on buyer/channel.

This route is strategically important because it tests whether we can occupy the layer below large liquidators instead of competing directly with them.

### Price evidence currently known

External B2B footwear asking prices observed during market study varied materially by condition, brand and quantity.

This case does **not** yet have an evidenced exit price.

```text
DIRECT_BUYER_OFFER: UNKNOWN
COMPLETED_TRANSACTION_COMPARABLE: PARTIAL / external only
ACTIVE_B2B_ASK_COMPARABLE: YES
REALISTIC_EXIT_PRICE_FOR_THIS_LOT: UNKNOWN
```

### Friction currently known

```text
VAT cash requirement: YES / exact treatment to verify for transaction path
buyer premium: UNKNOWN
transport: UNKNOWN
sorting: likely
size-range existence: VERIFIED (29-46)
size-distribution quality: UNKNOWN
model_count: VERIFIED (10-12)
model concentration risk: UNKNOWN until quantity/model is known
authenticity risk: UNKNOWN
storage: likely
capital lock: potentially material
unsold-tail risk: potentially material
```

### Foothold signal from this case

The case strengthens this hypothesis:

`Nordic branded/generic footwear micro-lots sold to smaller downstream resellers may be a viable market layer.`

Current state for that hypothesis: `WEAK`

Reason:

The downstream buyer layer exists in the market, but we do not yet have our own buyer confirmations, quantity requests or price quotes.

### What changed our view

The first live-facts pass materially improved the stock definition:

```text
BEFORE:
~3600 mixed shoes / composition largely unknown

NOW VERIFIED:
~3600 pairs
10-12 models
women + men + children
EU sizes 29-46
new leisure/casual footwear claim
Heimdal, Norway
seller = active Family Market AS
```

It also removed an unsafe assumption:

```text
large stock != bankruptcy / closure
```

However, a wide size range does not prove a commercially healthy size curve, and 10–12 models does not reveal concentration per model.

### Current decision

`NEED_EVIDENCE`

Reason:

The case has enough evidence to remain commercially interesting, but the missing brand / SKU / per-model quantity / exact size-curve data can materially change both exit-market fit and realistic exit price.

### Next unresolved commercial question

Obtain the seller's exact inventory composition before moving to buyer matching.

Minimum requested dataset:

```text
brand
model / SKU / EAN
women / men / children
size
quantity by size
quantity by model
new A-stock / B-grade / return status
original box yes/no
pallet / carton count
```

Until that dataset is available, downstream buyer matching remains preliminary rather than deal-specific.

---

## Case template

Copy this section for every future opportunity.

### Case XXX — [short title]

**Status:** `CONTINUE | NEED_EVIDENCE | STOP`

#### Why it attracted attention

- 

#### Known facts

```text
category:
subcategory:
quantity:
location:
condition:
brands:
model_mix:
size_curve:
packing_list:
entry_price:
vat_basis:
fees:
transport:
```

#### Missing material facts

- 

#### Exit routes

**Route A**

```text
route_type:
buyer_segment:
buyer_examples:
evidence_level:
absorbable_quantity:
price_evidence_type:
price_evidence:
friction:
```

**Route B**

```text
route_type:
buyer_segment:
buyer_examples:
evidence_level:
absorbable_quantity:
price_evidence_type:
price_evidence:
friction:
```

#### Foothold signal

```text
hypothesis:
state: NONE | WEAK | EMERGING | REPEATED | PROVEN
what_strengthened_it:
what_weakened_it:
```

#### What changed our view

- 

#### Current decision

`CONTINUE | NEED_EVIDENCE | STOP`

Reason:

- 

#### Commercial lesson

- 

#### Next unresolved commercial question

- 
