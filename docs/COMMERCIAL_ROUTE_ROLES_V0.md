# Commercial Route Roles V0

**Status:** MANUAL / COMMERCIAL-LEARNING / RESEARCH-ONLY

## Purpose

Separate **who buys the stock** from **who helps move the stock**.

The Commercial Foothold project must not treat every company in the chain as a `BUYER`.

A real stock route can contain different commercial roles:

```text
SELLER
→ DEAL ORIGINATOR / BROKER / STOCK DISTRIBUTOR
→ DIRECT BUYER / RESELLER / EXPORTER
→ DOWNSTREAM MARKET
```

The same stock may use a direct-buyer route or an intermediary route.

---

## Role 1 — DIRECT_BUYER

Definition:

A company that buys the stock for its own account and becomes the economic buyer of the lot.

Evidence expected:

```text
public statement that it buys relevant stock
or
published acquisition / transaction evidence
or
our own quote / transaction
```

Examples from current research:
- broad stocklot buyers;
- footwear stock buyers;
- B-stock / returns buyers;
- branded-stock specialists;
- PPE/workwear buyers where product and regulatory fit are evidenced.

A direct buyer may later resell the goods, but it first takes the purchasing position itself.

---

## Role 2 — CLEARANCE_BROKER / STOCK_DISTRIBUTOR

Definition:

An intermediary that receives a stock opportunity, presents it to an existing buyer network, matches the lot to a downstream buyer, and coordinates the transaction without necessarily becoming the final economic buyer before a downstream buyer is found.

This role is strategically important to our project because it resembles the intended commercial foothold:

```text
EARLY DISCOVERY
→ UNDERSTAND STOCK
→ FIND / KNOW BUYER DEMAND
→ MATCH SELLER TO BUYER
→ EARN COMMERCIAL POSITION WITHOUT NEEDING TO OWN EVERY LOT
```

### Current operational evidence — Stock Solutions Ltd

Stock Solutions publicly describes a process in which:

- a seller provides surplus stock;
- Stock Solutions markets the lot to its buyer network;
- once it finds a buyer, it asks the seller to hold the goods while it invoices and collects payment from its buyer;
- it then pays the seller, generally before collection;
- it coordinates logistics through a large transport network;
- its mainline channel is described as close to 10,000 subscribed buyers;
- it can also use targeted/restricted circulation and export-only routes;
- it works with brand-new, graded and raw-return goods.

This is strong operational evidence that a `CLEARANCE_BROKER / STOCK_DISTRIBUTOR` route is a real commercial model, not a theoretical role.

Important:

```text
BROKER != DIRECT_BUYER
```

Do not count buyer-network size as direct demand for a specific lot.

---

## Role 3 — B2B_MARKETPLACE / AUCTION_CHANNEL

Definition:

A platform that exposes lots to approved business buyers and allows market price discovery through listings or auctions.

Examples:
- B2B liquidation auction marketplaces;
- stocklot marketplaces;
- trade-only auction channels.

This proves access to a buyer pool, not guaranteed demand or a clearing price.

```text
MARKETPLACE_LISTING != BUYER
CURRENT_BID != FINAL_CLEARING_PRICE
ASKING_PRICE != TRANSACTION_PRICE
```

---

## Role 4 — WHOLESALER / RESELLER

Definition:

A company that buys or takes stock into its commercial inventory and redistributes it to smaller buyers, retailers, exporters or online sellers.

Typical fit:
- bulk quantities;
- mixed stock;
- clearance stock;
- broken assortments;
- old-season goods;
- category-specific stock.

A wholesaler may be both:

```text
DIRECT_BUYER + DOWNSTREAM_DISTRIBUTOR
```

when it actually purchases the lot itself.

---

## Role 5 — EXPORTER / GEOGRAPHIC ARBITRAGE BUYER

Definition:

A buyer or intermediary whose value comes from moving stock to a different market where the product, sizes, brand restrictions or price point have stronger demand.

This role can be important for:
- broken sizes;
- one-size concentration;
- restricted domestic circulation;
- old seasons;
- generic or price-led stock;
- goods that cannot be remarketed in the seller's normal channel.

Geographic demand must be evidenced; it must not be invented.

---

## Role 6 — END-USE / SPECIALIST BUYER

Definition:

A buyer that wants the stock for a specific operational use rather than generic resale.

Examples may include:
- uniforms;
- workwear;
- industrial consumables;
- hospitality/textile use;
- promotional use;
- specialist category demand.

This route is highly product-specific and must be supported by concrete evidence.

---

## Route selection rule

After Stock Identity / Behavior is known, research routes in parallel:

```text
A — DIRECT_BUYER
B — CLEARANCE_BROKER / STOCK_DISTRIBUTOR
C — B2B_MARKETPLACE / AUCTION
D — WHOLESALER / RESELLER
E — EXPORT / GEOGRAPHIC ROUTE
F — SPECIALIST END-USE ROUTE
```

Do not force every stock lot into the same route.

---

## Commercial foothold implication

The project does not need to become a large inventory owner in order to create value.

A possible foothold can be:

```text
DISCOVER STOCK EARLY
→ DEFINE STOCK SHAPE
→ KNOW WHICH BUYER FAMILY / ROUTE FITS
→ PACKAGE THE EVIDENCE BETTER THAN THE SELLER
→ INTRODUCE / MATCH TO A REAL BUYER
→ LEARN THE CLEARING ECONOMICS
```

This model reduces the need to carry inventory risk while commercial knowledge is still being built.

It is a hypothesis until our own buyer/seller interaction or transaction evidence reaches E5.

---

## Seller Source Roles — hunter-first rule

Before a discovered lot is promoted into a commercial case, classify the **seller/source role** separately from the buyer route.

```text
ORIGINAL_STOCK_OWNER
LIQUIDATION_INSOLVENCY_SOURCE
BROKER_AUCTION_MARKETPLACE
STOCK_TRADER_RESELLER
UNKNOWN
```

### ORIGINAL_STOCK_OWNER

The company or operator that owns the stock because it arose from its own normal business, production, retail, import, cancelled orders, overproduction, surplus, store closure, warehouse reduction or similar evidenced origin.

This is a **primary hunting target**.

### LIQUIDATION_INSOLVENCY_SOURCE

A liquidator, insolvency estate, bankruptcy administrator, closure sale or equivalent source disposing of stock from the original business.

This is also a **primary hunting target**, even when an auction platform is used as the sales channel.

### BROKER_AUCTION_MARKETPLACE

An intermediary or platform that exposes stock but does not itself prove original ownership of the goods.

This can be a useful discovery route, but the project should identify the underlying stock owner or liquidation context when possible.

### STOCK_TRADER_RESELLER

A stocklot/restposten trader that buys surplus, liquidation, returns, overstock or similar goods and resells them from its own inventory.

This is **not the preferred prey/source** for the project because another stock trader has already entered the chain and may already have added margin.

A stock trader may still be valuable as:

```text
DIRECT_BUYER
WHOLESALER / RESELLER
CLEARANCE_ROUTE
PRICE_REFERENCE
MARKET_BEHAVIOR_EVIDENCE
```

Do not automatically reject an exceptional arbitrage opportunity from a stock trader, but require stronger deal-specific economics before treating it as a hunting case.

### UNKNOWN

If the seller/source role cannot be evidenced, keep it `UNKNOWN`.

```text
UNKNOWN != ORIGINAL_STOCK_OWNER
UNKNOWN != REJECTED
```

Do not infer original ownership from stock size, low price, location, company name or listing language alone.

### Hunter-first operating rule

The preferred commercial chain is:

```text
ORIGINAL STOCK OWNER / LIQUIDATION SOURCE
→ OUR EARLY DISCOVERY + STOCK DEFINITION
→ QUALIFIED BUYER / ROUTE
→ COMMERCIAL MATCH
```

Avoid making this the default chain:

```text
ORIGINAL STOCK OWNER
→ STOCK TRADER RESELLER
→ US
→ NEXT BUYER
```

because it usually means we are buying from another hunter rather than discovering the prey/source earlier.

For every case record both fields independently:

```text
seller_source_role:
ORIGINAL_STOCK_OWNER | LIQUIDATION_INSOLVENCY_SOURCE | BROKER_AUCTION_MARKETPLACE | STOCK_TRADER_RESELLER | UNKNOWN

commercial_route_role:
DIRECT_BUYER | CLEARANCE_BROKER | MARKETPLACE | WHOLESALER | EXPORTER | SPECIALIST_BUYER
```

Example from current research:

```text
Salzmann Restwaren GmbH
seller_source_role: STOCK_TRADER_RESELLER
case-use: buyer/route/price-reference evidence, not preferred original-stock prey
```

This classification is descriptive and routing-oriented. It does not itself create an automated BUY/REJECT decision.

---

## Evidence discipline

For every named company record:

```text
company_name:
role:
DIRECT_BUYER | CLEARANCE_BROKER | MARKETPLACE | WHOLESALER | EXPORTER | SPECIALIST_BUYER
product_scope:
stock_shapes_accepted:
quantity_evidence:
geography:
logistics_role:
payment_role:
evidence_level:
source:
case_specific_fit:
```

Never use the generic word `buyer` when the actual evidence only proves intermediary or marketplace status.

---

## Guardrails

- No outreach is authorized by this document.
- No automated brokerage runtime.
- No commission assumption without evidence.
- No assumption that an intermediary will accept every lot.
- No assumption that access to buyers equals a guaranteed sale.
- No financial commitment.
- Search Engine V1 remains unchanged.
