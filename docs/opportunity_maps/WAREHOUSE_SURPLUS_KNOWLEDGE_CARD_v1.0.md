# WAREHOUSE_SURPLUS Knowledge Card v1.0

**Domain:** `CLOTHING_INVENTORY`  
**Scenario:** `WAREHOUSE_SURPLUS`  
**Status:** `READY_FOR_REVIEW`  
**Purpose:** Define how the Discovery Engine should recognize commercially meaningful clothing inventory that becomes available because a warehouse, distributor, wholesaler, retailer, or logistics operator is carrying excess, obsolete, returned, seasonal, cancelled, or slow-moving stock.

---

## 1. Real-world event

A company has apparel inventory stored in a warehouse or distribution environment that it no longer wants to keep in normal stock rotation. The business may continue operating normally. The opportunity exists because the inventory has become operationally inconvenient, commercially slow, obsolete, seasonal, returned, overbought, or disconnected from current demand.

The defining event is not bankruptcy, store closure, or a one-off household sale. It is the release of commercially meaningful apparel stock from storage because the holder wants to reduce warehouse load, free working capital, simplify assortment, clear older seasons, remove returns, or eliminate discontinued goods.

A warehouse-surplus event may concern:

- complete warehouse sections;
- palletized apparel stock;
- cartons or cases of garments;
- seasonal leftovers;
- slow-moving stock;
- cancelled customer orders;
- customer returns;
- discontinued product lines;
- packaging-damaged but usable stock;
- overstock from a wholesaler or distributor;
- goods from a terminated retail agreement;
- mixed commercial inventory that includes clothing as a substantial component.

---

## 2. Seller motivation

Typical seller motivations include:

- reducing warehouse occupancy;
- lowering storage and handling costs;
- freeing working capital;
- removing old seasons before new deliveries arrive;
- clearing discontinued products;
- resolving cancelled orders;
- disposing of customer returns;
- reducing slow-moving stock;
- ending a distribution agreement;
- consolidating warehouses;
- relocating operations;
- simplifying assortment;
- correcting over-ordering or demand forecasting errors;
- preparing for inventory count or system migration;
- avoiding future disposal costs.

The Discovery Engine may preserve a stated motivation, but must not infer one without source evidence.

---

## 3. Opportunity forms

Valid opportunity forms include:

### 3.1 Confirmed warehouse stock sale

The seller explicitly offers a commercial apparel stock for sale from a warehouse or storage environment.

Examples:

- pallets of clothing sold together;
- cartons of garments sold as one lot;
- warehouse remainder with quantity or category description;
- returned apparel stock sold in bulk;
- discontinued seasonal stock sold to resellers.

### 3.2 Partial warehouse clearance

Only part of the warehouse inventory is offered, such as one category, one season, one brand group, or one customer-return segment.

### 3.3 Contact-required surplus lead

A source confirms excess or obsolete warehouse stock, but no sale terms or public offer are available.

### 3.4 Mixed commercial lot

The lot contains clothing plus footwear, accessories, textiles, fixtures, or packaging. Clothing must be a meaningful component of the commercial opportunity.

### 3.5 Returns or B-grade stock

The stock may include returns, damaged packaging, seconds, incomplete sets, or items requiring sorting. This remains a discovery candidate if the source makes the commercial stock available and the condition is not invented.

### 3.6 Pallet, carton, or case sale

The inventory is sold in logistics units rather than item-by-item. Exact piece count may remain unknown if the source confirms the commercial scale.

---

## 4. Scenario boundaries

### WAREHOUSE_SURPLUS versus STORE_CLOSING

- `WAREHOUSE_SURPLUS`: the business may continue operating; the trigger is excess or unwanted warehouse stock.
- `STORE_CLOSING`: a store or retail operation is closing or permanently stopping.

### WAREHOUSE_SURPLUS versus BANKRUPTCY

- `WAREHOUSE_SURPLUS`: the stock is released as an operational or commercial inventory decision.
- `BANKRUPTCY`: the company or estate is under formal insolvency proceedings.

### WAREHOUSE_SURPLUS versus INVENTORY_LIQUIDATION

- `WAREHOUSE_SURPLUS`: the storage context and excess-stock condition are central.
- `INVENTORY_LIQUIDATION`: the seller is intentionally converting inventory to cash, potentially without a warehouse-specific context.

A record may contain both signals. The primary scenario should reflect the strongest documented cause. Secondary scenario tags may be preserved.

### WAREHOUSE_SURPLUS versus LARGE_LOT

- `WAREHOUSE_SURPLUS`: explains why the stock became available.
- `LARGE_LOT`: describes the commercial scale or bundled sale form.

A single opportunity may legitimately carry both labels.

### WAREHOUSE_SURPLUS versus IMPORTER_CLEARANCE

- `WAREHOUSE_SURPLUS`: the decisive signal is excess stock in storage.
- `IMPORTER_CLEARANCE`: the decisive signal is that an importer or distributor is clearing imported goods, discontinued lines, or unsold inbound stock.

### WAREHOUSE_SURPLUS versus AUCTION

- `WAREHOUSE_SURPLUS`: the scenario explains the inventory condition.
- `AUCTION`: the sale mechanism is bidding.

Auction is not the cause of surplus.

---

## 5. Norwegian language signals

Signals must be evaluated in context. A single weak phrase is never sufficient.

### 5.1 Strong signals

Strong signals directly connect warehouse or storage stock with excess, clearance, or commercial disposal.

- `overskuddslager`
- `lageroverskudd`
- `overskuddsvarer`
- `restlager fra lager`
- `varelager selges samlet`
- `lagerparti klær`
- `pall med klær`
- `paller med klær`
- `engrosparti fra lager`
- `restparti fra lager`
- `utgående lagerbeholdning`
- `overskuddspartier`
- `lagerbeholdning må bort`
- `lager tømmes`
- `lageret ryddes`
- `partivarer fra lager`
- `returvarer klær parti`
- `sesongvarer fra lager selges`
- `utgåtte varer fra lager`
- `hele lagerpartiet selges`
- `partisalg direkte fra lager`

### 5.2 Medium signals

Medium signals become meaningful when combined with clothing terms, logistics units, quantity, business context, or sale intent.

- `restlager`
- `overlager`
- `for mye på lager`
- `utgående varer`
- `gamle kolleksjoner`
- `sesongrest`
- `returvarer`
- `B-varer`
- `emballasjeskade`
- `overskudd`
- `partisalg`
- `engros`
- `pall`
- `kartonger`
- `esker`
- `lagerbeholdning`
- `lageropprydding`
- `rydder lager`
- `må frigjøre lagerplass`
- `plassmangel på lager`
- `avsluttet produktlinje`
- `kansellert ordre`
- `feilbestilling`
- `overbestilling`
- `utgått sortiment`

### 5.3 Weak signals

Weak signals cannot qualify the scenario without stronger commercial context.

- `salg`
- `tilbud`
- `rabatt`
- `billig`
- `parti`
- `lager`
- `klær`
- `mye varer`
- `ryddesalg`
- `rest`
- `outlet`
- `kampanje`
- `engrospris`

### 5.4 Apparel and commercial context terms

Useful clothing and business terms include:

- `klær`
- `bekledning`
- `tekstil`
- `motevarer`
- `dameklær`
- `herreklær`
- `barneklær`
- `arbeidsklær`
- `sportsklær`
- `undertøy`
- `sko`
- `tilbehør`
- `vareparti`
- `partivarer`
- `engros`
- `forhandler`
- `butikk`
- `grossist`
- `distributør`
- `lagerhotell`
- `logistikk`
- `videresalg`

---

## 6. Context combinations

The Discovery Engine should prefer combinations rather than isolated keywords.

### Combination A — explicit warehouse surplus sale

```text
overskuddslager
+ klær or bekledning
+ sale language
+ source URL or contact route
```

Likely outcome: `SALE_CONFIRMED`.

### Combination B — palletized apparel stock

```text
pall or paller
+ klær
+ sold together / part sale
+ business or warehouse context
```

Likely outcome: `SALE_CONFIRMED` when the sale is explicit.

### Combination C — old seasonal warehouse stock

```text
gamle kolleksjoner or sesongrest
+ warehouse / stock context
+ meaningful commercial quantity
+ sale or contact route
```

Likely outcome: `SALE_CONFIRMED` or `CONTACT_REQUIRED`.

### Combination D — returns stock

```text
returvarer
+ clothing category
+ bulk / pallet / lot language
+ commercial seller context
```

Likely outcome: `SALE_CONFIRMED`, with condition and sorting unknown unless documented.

### Combination E — warehouse consolidation

```text
lagerflytting or sammenslåing av lager
+ apparel stock
+ clearance or disposal language
+ contact route
```

Likely outcome: `CONTACT_REQUIRED` unless the inventory is explicitly offered.

### Combination F — storage pressure

```text
må frigjøre lagerplass
+ clothing stock
+ meaningful lot evidence
+ sale intent
```

Likely outcome: `SALE_CONFIRMED` or `CONTACT_REQUIRED`.

### Combination G — weak retail sale only

```text
salg
+ klær
+ discount language
```

Likely outcome: `REJECTED` unless commercial inventory scale and warehouse-surplus evidence appear elsewhere.

---

## 7. Positive evidence

A record becomes stronger when one or more of the following are documented:

- seller is a company, wholesaler, distributor, importer, retailer, logistics operator, or warehouse holder;
- stock is described as warehouse inventory, surplus, remainder, returns, obsolete stock, or slow-moving stock;
- goods are offered in pallets, cartons, cases, racks, or a complete stock group;
- inventory is explicitly offered for resale;
- quantity, pallet count, carton count, weight, volume, or stock-value reference is available;
- images show commercial storage, pallets, racks, cartons, labels, packaging, or repeated units;
- pickup is from a warehouse or commercial facility;
- sale terms refer to business buyers, bulk buyers, resellers, or wholesale purchase;
- a list, spreadsheet, PDF, inventory export, manifest, or attachment exists;
- multiple sizes, colors, styles, or SKUs indicate commercial inventory rather than household goods.

---

## 8. False positives and rejection rules

Reject or downgrade the result when the available evidence shows only:

- ordinary retail discounting;
- a normal outlet promotion;
- one garment or a small household bundle;
- a private wardrobe clean-out;
- generic warehouse services;
- warehouse jobs or recruitment;
- storage-unit rental;
- logistics news without stock availability;
- an expired sale with no current contact route;
- an inaccessible page with no preserved evidence;
- a product page saying only `på lager`;
- normal stock availability;
- an auction with no clothing or meaningful apparel component;
- pallets mentioned only as delivery units for ordinary retail orders;
- a single return item;
- a business directory entry without evidence of excess stock;
- a news article about retail overstock with no identifiable opportunity;
- a seller claiming `engros` but offering only a few unrelated pieces.

A candidate must not be rejected solely because exact price, quantity, brand list, size distribution, VAT treatment, transport cost, or condition breakdown is missing.

---

## 9. Likely publication channels

Channels describe where the event may appear. They are not mandatory sources and do not govern the architecture.

Likely channels include:

- general classified marketplaces;
- business-to-business marketplaces;
- auction platforms;
- company websites;
- wholesaler or distributor pages;
- importer clearance pages;
- warehouse and logistics partner pages;
- social-media business pages;
- Facebook groups for wholesale, retail closure, surplus, or liquidation;
- local newspapers and business publications;
- insolvency and asset-disposal notices;
- direct PDF catalogues or inventory lists;
- email newsletters from wholesalers;
- estate or broker sale pages;
- search-engine indexed landing pages;
- public posts from warehouse operators or resellers.

The system must search by commercial scenario and signals, not by a fixed website list.

---

## 10. Minimum discovery data

A warehouse-surplus candidate may be preserved when the following minimum evidence exists:

| Field | Requirement |
|---|---|
| Domain | `clothing_inventory` |
| Scenario | `warehouse_surplus` |
| What is sold | Apparel, footwear, accessories, textiles, or a mixed lot with meaningful clothing content |
| Commercial scale evidence | Warehouse, pallet, carton, lot, repeated units, stock language, or equivalent evidence |
| Source route | Public URL or public contact route |
| Sale status | Explicit sale or contact-required lead |
| Location | Preserve when available; otherwise `null` |
| Seller identity | Preserve when public; otherwise `null` |
| Raw source text | Preserve available title and description |
| Discovery evidence | Preserve signals, snippets, images, or attachments used for classification |

The following are not mandatory at discovery time:

- exact quantity;
- exact pallet count;
- complete SKU list;
- complete brand list;
- size distribution;
- condition grading;
- sorting quality;
- return reason;
- packaging condition;
- purchase price;
- VAT treatment;
- transport cost;
- storage cost;
- expected resale value;
- profit or ROI.

Missing values must remain `null`, unknown, or explicitly unverified.

---

## 11. Permitted unknowns

The Discovery Engine may preserve a valid candidate even when these fields are unknown:

- exact number of pieces;
- exact number of pallets or cartons;
- exact weight or cubic volume;
- brands;
- sizes;
- colors;
- style mix;
- product season;
- original retail value;
- wholesale cost;
- VAT basis;
- minimum purchase quantity;
- whether splitting is allowed;
- return rate or defect rate;
- packaging completeness;
- whether goods are new, returned, B-grade, samples, or mixed;
- pickup equipment requirements;
- loading conditions;
- deadline;
- seller authority;
- whether the offer remains active.

Unknown information becomes a Dossier requirement or seller question. It is not automatically a rejection reason.

---

## 12. Opportunity Dossier evidence targets

The Dossier should collect and separate confirmed facts, seller claims, visual observations, estimates, and unknowns.

### 12.1 Source metadata

- source URL;
- source domain;
- publication date;
- update date;
- seller name;
- company number when public;
- contact details when public;
- location;
- warehouse or pickup address when public;
- deadline or availability period;
- source-provider and discovery-query provenance.

### 12.2 Sale terms

- asking price;
- whether price includes or excludes VAT;
- whole-lot versus partial purchase;
- minimum order;
- bidding or fixed price;
- reservation rules;
- payment terms;
- pickup deadline;
- loading responsibility;
- transport inclusion or exclusion;
- inspection availability;
- return rights or `as-is` terms.

### 12.3 Inventory evidence

- quantity claims;
- pallet count;
- carton count;
- weight or volume;
- categories;
- brands;
- size ranges;
- SKU list;
- season or collection;
- new versus returned versus B-grade status;
- packaging condition;
- repeated units;
- inventory sheets;
- manifests;
- spreadsheets;
- PDFs;
- photographs of pallets, cartons, racks, labels, or product groups.

### 12.4 Visual observations

Visual observations must be phrased cautiously.

Permitted observations:

- `Images show multiple cartons stored on pallets.`
- `Several racks contain repeated apparel items.`
- `Commercial labels are visible on some boxes.`
- `The stock appears mixed across categories.`
- `Packaging condition varies in the available images.`

Not permitted without evidence:

- exact quantity from a partial image;
- guaranteed brand authenticity;
- guaranteed new condition;
- guaranteed sell-through quality;
- exact size distribution;
- exact defect percentage;
- exact pallet dimensions;
- exact stock value.

### 12.5 Company and authority evidence

Where publicly accessible, preserve:

- company identity;
- business status;
- warehouse operator identity;
- seller authority;
- ownership or consignment relationship;
- relevant public company records;
- source attachments or sale mandates.

The Discovery Engine must not claim legal authority that is not documented.

---

## 13. Qualification outcomes

### 13.1 `SALE_CONFIRMED`

Use when:

- a meaningful clothing stock is explicitly offered for sale;
- the warehouse-surplus context is documented or strongly evidenced;
- a public URL or contact route exists;
- the record is not an ordinary retail promotion or household bundle.

Price and exact quantity may still be unknown.

### 13.2 `CONTACT_REQUIRED`

Use when:

- excess apparel stock is credibly indicated;
- sale availability, seller authority, quantity, or terms are not confirmed;
- a public contact route exists or can be identified.

This status must remain outside financial analysis until sale availability is confirmed.

### 13.3 `REJECTED`

Use when:

- there is no meaningful apparel inventory;
- the result is a normal retail sale;
- the result is a private wardrobe bundle;
- there is no commercial-scale evidence;
- the page concerns warehouse services, jobs, rental, or unrelated logistics;
- the source contains no actionable public route or preserved evidence.

### 13.4 `EXPIRED`

Use when:

- the offer is clearly no longer active;
- the deadline passed and no current route remains;
- the source was removed and no sufficient evidence was preserved.

Expired records may remain for historical learning but must not be treated as live opportunities.

---

## 14. Seller questions

Questions should be generated only for missing decision-relevant facts.

### Inventory

- How many pieces are included?
- How many pallets, cartons, or racks are included?
- Is an inventory list available?
- Which brands and product categories are included?
- What is the size distribution?
- Are all goods new, or are returns and B-grade items mixed in?
- Are the items individually packaged and labelled?
- Are there known defects, missing parts, stains, odors, or packaging damage?
- What seasons or collections are represented?
- Is the stock sorted by SKU, size, category, or condition?

### Sale structure

- Is the stock sold only as one lot?
- Can the stock be split?
- What is the minimum purchase quantity?
- Is the stated price fixed, negotiable, or subject to bidding?
- Is VAT included?
- Is there a deposit or reservation requirement?
- Is inspection possible before purchase?

### Logistics

- Where is the stock located?
- What are the pallet dimensions and total weight?
- Is loading equipment available?
- Must the buyer provide pallets, cages, or containers?
- Is transport available, and at what documented price?
- What is the pickup deadline?
- Are there access restrictions for trucks or loading times?

### Authority and status

- Who owns the goods?
- Is the seller authorized to dispose of the stock?
- Is the offer still active?
- Are any goods subject to third-party claims, consignment, retention of title, or unpaid supplier rights?

No answer may be invented or assumed.

---

## 15. Controlled fixtures

These fixtures are synthetic test examples. They are not live opportunities.

### Fixture A — confirmed pallet sale

**Title:** `6 paller med dameklær selges samlet fra lager`  
**Text:** `Overskuddslager etter feilbestilling. Nye varer i kartonger. Selges kun samlet. Henting i Drammen.`

Expected classification:

```yaml
scenario: warehouse_surplus
status: sale_confirmed
reason: explicit apparel stock, palletized commercial scale, warehouse-surplus cause, and sale route
```

### Fixture B — returns stock with incomplete details

**Title:** `Returvarer klær fra nettbutikk`  
**Text:** `Flere esker med kunde-returer. Antall og tilstand må avklares. Kontakt for informasjon.`

Expected classification:

```yaml
scenario: warehouse_surplus
status: contact_required
reason: credible commercial returns stock, but quantity, condition, and sale terms are incomplete
```

### Fixture C — ordinary retail discount

**Title:** `Lagersalg 30 % på alle jakker`  
**Text:** `Tilbud i butikk denne helgen.`

Expected classification:

```yaml
status: rejected
reason: ordinary retail promotion with no commercial inventory lot
```

### Fixture D — warehouse-service false positive

**Title:** `Lagerplass for klær og tekstiler`  
**Text:** `Vi tilbyr oppbevaring og logistikk for nettbutikker.`

Expected classification:

```yaml
status: rejected
reason: warehouse service, not stock availability
```

### Fixture E — duplicate listing

Two pages contain the same seller, same six-pallet inventory, same location, and same images, but slightly different titles.

Expected behavior:

```yaml
duplicates_removed: 1
canonical_record: one
```

### Fixture F — mixed commercial lot

**Title:** `Restlager med klær, sko og tilbehør`  
**Text:** `Ca. 20 kartonger fra avsluttet distribusjonsavtale. Selges samlet.`

Expected classification:

```yaml
scenario: warehouse_surplus
secondary_scenario: large_lot
status: sale_confirmed
reason: clothing is a meaningful part of a commercial warehouse remainder
```

### Fixture G — vague stock claim

**Title:** `Mye klær på lager`  
**Text:** `Ta kontakt hvis interessert.`

Expected classification:

```yaml
status: contact_required
reason: possible commercial stock, but seller identity, scale, cause, and sale structure require confirmation
```

### Fixture H — household bundle

**Title:** `Stor klespakke fra loftet`  
**Text:** `Omtrent 25 brukte plagg fra familien.`

Expected classification:

```yaml
status: rejected
reason: household wardrobe bundle, not warehouse surplus
```

---

## 16. Acceptance tests

The card is implementable only when future code can satisfy the following observable tests.

### Test 1 — explicit surplus sale qualifies

Given a source that explicitly offers palletized apparel from warehouse overstock, the result must be classified as `warehouse_surplus` and `sale_confirmed`.

### Test 2 — returns stock may remain incomplete

Given credible bulk clothing returns with missing quantity and condition, the result must be preserved as `contact_required` rather than rejected.

### Test 3 — ordinary retail promotion is rejected

Given only a consumer discount or store campaign, the result must not qualify as warehouse surplus.

### Test 4 — warehouse services are rejected

Given a page offering storage or logistics services, the result must be rejected.

### Test 5 — missing price does not cause rejection

Given a valid warehouse-surplus sale without a public price, the system must preserve `price: null` and continue classification.

### Test 6 — missing exact quantity does not cause rejection

Given strong commercial-scale evidence such as pallets or cartons, the exact piece count may remain unknown.

### Test 7 — household bundles are rejected

Given a private clothing bundle without commercial stock evidence, the result must be rejected even when the word `parti` is present.

### Test 8 — source traceability is preserved

Every extracted title, description, location, quantity claim, price, image observation, and attachment reference must retain source provenance.

### Test 9 — no financial analysis occurs in Discovery

The Discovery Engine must not calculate market value, total acquisition cost, expected profit, ROI, bid ceiling, or purchase recommendation.

### Test 10 — duplicates collapse safely

Listings representing the same seller and stock should collapse into one canonical candidate while preserving all source URLs.

### Test 11 — scenario boundaries are respected

A bankruptcy estate sale should not be relabeled as warehouse surplus merely because goods are physically stored in a warehouse. The documented commercial cause governs the primary scenario.

### Test 12 — image claims remain bounded

Images may support commercial-scale and storage observations, but must not generate unsupported exact quantities, values, brands, or condition guarantees.

---

## 17. Discovery output example

```yaml
schema_version: opportunity-contract-1.0
opportunity_id: stable-id
record_type: sale_listing
domain: clothing_inventory
scenario: warehouse_surplus
secondary_scenarios:
  - large_lot
status: sale_confirmed
what_is_sold: clothing inventory stored in pallets and cartons
opportunity_type: warehouse overstock sale
location: null
source_url: https://example.invalid/warehouse-stock
contact: null
opportunity_size:
  quantity: null
  unit: pallets
  description: multiple pallets and cartons; exact piece count unknown
raw_title: "Paller med klær selges fra lager"
raw_description: null
discovery_evidence:
  - type: text_signal
    value: "overskuddslager"
  - type: scale_signal
    value: "paller"
missing_discovery_fields:
  - exact_quantity
  - price
  - brands
  - size_distribution
  - condition_breakdown
automatic_purchase_decision: false
```

This record may proceed to Opportunity Dossier collection. It must not receive a financial decision until the Analysis Engine has verified sufficient evidence.

---

## 18. Completion decision

`WAREHOUSE_SURPLUS` is complete when:

- the scenario is distinguishable from adjacent scenarios;
- strong, medium, and weak signals are documented;
- context combinations are testable;
- false positives are explicit;
- missing analysis data is permitted;
- Dossier evidence targets are defined;
- controlled fixtures cover positive, ambiguous, negative, mixed, and duplicate cases;
- acceptance tests prohibit invented facts and financial decisions inside Discovery.

After approval and merge, `IMPORTER_CLEARANCE` becomes the only next scenario.
