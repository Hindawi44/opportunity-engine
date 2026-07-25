# LARGE_LOT Knowledge Card v1.0

**Domain:** `CLOTHING_INVENTORY`  
**Scenario:** `LARGE_LOT`  
**Status:** READY FOR REVIEW  
**Purpose:** Define how the Discovery Engine identifies a commercially meaningful large apparel lot without confusing it with ordinary multi-item listings, liquidation events, warehouse surplus, or auctions.

---

## 1. Real-world event

A `LARGE_LOT` opportunity exists when a seller offers a substantial group of clothing, footwear, accessories, textiles, or closely related retail inventory as one transaction or tightly linked package.

The defining commercial fact is the size and bundled nature of the offering, not necessarily the reason for sale.

A large lot may come from:

- a retailer reducing stock;
- an online shop selling remaining inventory;
- a wholesaler clearing a category;
- a private reseller disposing of a business-sized collection;
- a company selling returned, seasonal, discontinued, or mixed goods;
- an estate, storage unit, warehouse, or importer offering a grouped apparel lot.

A `LARGE_LOT` is not automatically a liquidation, bankruptcy, store closing, warehouse surplus, or auction. Those scenarios may overlap, but the classification must be based on the strongest confirmed evidence.

---

## 2. Seller motivations

Common motivations include:

- freeing storage space;
- releasing working capital;
- ending one product category;
- changing business model;
- closing an online shop;
- disposing of old-season stock;
- selling returns, samples, or discontinued products;
- avoiding the time required to sell items individually;
- transferring stock after relocation or ownership change;
- exiting resale activity.

The seller motivation may be unknown. Unknown motivation must remain `null` and must not block preservation of a credible lot.

---

## 3. Opportunity forms

Possible forms include:

1. **Complete apparel lot** — one bundled sale containing a substantial number of items.
2. **Category lot** — for example jackets, dresses, workwear, children's clothing, footwear, or accessories.
3. **Mixed retail lot** — several apparel categories sold together.
4. **Pallet or box lot** — stock described by pallets, boxes, sacks, cages, racks, or cartons.
5. **Inventory by approximate quantity** — for example 300, 800, or 2,000 items.
6. **Inventory by retail value** — seller states original retail value, without complete quantity.
7. **Lot with incomplete details** — commercial size is credible, but brands, sizes, exact quantity, or condition remain unknown.
8. **Contact-required lot** — seller signals a major grouped sale but asks interested buyers to request an inventory list.
9. **Segmented lot** — seller offers the complete lot but may accept bids for major sub-lots.
10. **Recurring wholesale-style lot** — repeated commercial batches; preserve as a lead unless a specific available lot is confirmed.

---

## 4. Scenario boundaries

### 4.1 LARGE_LOT versus INVENTORY_LIQUIDATION

Use `INVENTORY_LIQUIDATION` when the source clearly states that inventory is being liquidated, cleared to release capital, discontinued, or sold as part of a wind-down.

Use `LARGE_LOT` when the strongest confirmed fact is simply that a substantial bundled quantity is for sale and no stronger liquidation event is established.

### 4.2 LARGE_LOT versus STORE_CLOSING

Use `STORE_CLOSING` when a physical store closure is explicitly confirmed.

Use `LARGE_LOT` when the store status is unknown or irrelevant and the commercial evidence is the bundled stock sale itself.

### 4.3 LARGE_LOT versus BANKRUPTCY

Use `BANKRUPTCY` when a bankruptcy event or estate sale is confirmed.

A bankruptcy notice without an asset sale is not a `LARGE_LOT` sale.

### 4.4 LARGE_LOT versus WAREHOUSE_SURPLUS

Use `WAREHOUSE_SURPLUS` when excess stock is explicitly linked to a warehouse, distributor, importer, or wholesaler surplus process.

Use `LARGE_LOT` when only the quantity and bundled sale are confirmed.

### 4.5 LARGE_LOT versus AUCTION

Use `AUCTION` when the transaction mechanism is a public auction or formal bidding process.

A large lot sold at auction may retain `AUCTION` as the primary scenario and `large_lot` as an attribute.

---

## 5. Norwegian language signals

Signals must be interpreted in context. No single weak phrase is sufficient.

### 5.1 Strong signals

Strong signals directly indicate a substantial bundled stock sale:

- `stort vareparti`
- `stort klesparti`
- `hele partiet selges samlet`
- `selges kun samlet`
- `komplett varelager selges samlet`
- `flere hundre plagg`
- `flere tusen plagg`
- `parti på [quantity] enheter`
- `pall med klær`
- `flere paller med klær`
- `engrosparti klær`
- `restparti klær`
- `samlet parti fra butikk/nettbutikk`
- `lager med klær selges i én handel`

### 5.2 Medium signals

Medium signals become meaningful when combined with quantity, business context, images, or bundled-sale language:

- `vareparti`
- `klesparti`
- `større parti`
- `samlet salg`
- `selges samlet`
- `hele lageret`
- `restlager`
- `butikkvarer`
- `nettbutikk-lager`
- `partivarer`
- `engros`
- `paller`
- `esker med klær`
- `mange nye klær`
- `stort utvalg størrelser`

### 5.3 Weak signals

Weak signals are insufficient without stronger commercial context:

- `mye klær`
- `stor samling`
- `ryddesalg`
- `billig`
- `pakkepris`
- `klespakke`
- `flere plagg`
- `må bort`
- `alt samlet`
- `stor rabatt`

A private household clothing bundle may use several weak signals and still be irrelevant.

---

## 6. Context combinations

The Discovery Engine should qualify the scenario when combinations support a business-sized lot.

### Combination A — explicit quantity plus bundled sale

```text
"ca. 1 200 plagg" + "selges samlet"
```

Expected result: strong `LARGE_LOT` candidate.

### Combination B — commercial origin plus packaging scale

```text
"lager fra nedlagt nettbutikk" + "12 paller" + "klær og sko"
```

Expected result: strong candidate; check whether `STORE_CLOSING`, `BUSINESS_CHANGE`, or `INVENTORY_LIQUIDATION` has stronger evidence.

### Combination C — grouped stock plus business categories

```text
"stort vareparti" + brands/categories/sizes + one total price
```

Expected result: likely confirmed sale.

### Combination D — images plus incomplete text

```text
short description + multiple racks/pallets/boxes visible + public sale terms
```

Expected result: preserve as candidate; image observations must be marked as observations, not exact facts.

### Combination E — contact-required inventory list

```text
"komplett lager" + "send melding for vareliste/pris"
```

Expected result: `CONTACT_REQUIRED` unless sale availability and commercial lot are sufficiently confirmed.

---

## 7. False positives and rejection rules

Reject or downgrade when the evidence indicates:

- an ordinary household clothing bundle;
- a children's clothing package by size;
- fewer ordinary used garments with no commercial context;
- a wardrobe clear-out;
- a reseller advertising individual items in one post;
- a generic wholesale supplier page without a specific available lot;
- a dropshipping catalogue;
- a job advertisement;
- a request to buy clothing rather than an offer to sell;
- a transport or storage service;
- a news article with no available sale;
- an expired, deleted, inaccessible, or already sold listing;
- an auction announcement without a defined lot;
- a list of links with no traceable seller or source.

### Minimum scale rule

No fixed quantity threshold should be hard-coded across all apparel categories.

The system should evaluate commercial significance using evidence such as:

- explicit quantity;
- pallets, cartons, racks, or storage volume;
- business origin;
- one bundled transaction;
- inventory list;
- total retail value;
- breadth of categories or size range;
- images showing business-scale stock.

Ten luxury gowns may be commercially meaningful, while fifty low-value used garments may not be. The Discovery Engine preserves the candidate; the Analysis Engine determines economics.

---

## 8. Likely publication channels

Channels are execution paths, not governing architecture:

- general web search;
- classified marketplaces;
- social-media marketplace posts;
- business and wholesale groups;
- company websites;
- online-shop closure pages;
- liquidation brokers;
- auction platforms;
- local newspapers;
- business-sale portals;
- warehouse and surplus sellers;
- estate administrators or asset managers;
- public posts by retailers, importers, and distributors.

The system must search for the scenario across channels rather than depend on one named site.

---

## 9. Minimum discovery data

Preserve a `LARGE_LOT` candidate when the following are available:

- source URL or public contact route;
- raw title or equivalent identifying text;
- what is being sold;
- evidence that the offering is commercially meaningful and bundled;
- location when available;
- seller or source identity when public;
- sale status when available;
- discovery timestamp;
- traceable supporting text, images, or attachments.

Useful but non-mandatory fields:

- exact quantity;
- category breakdown;
- size distribution;
- brands;
- condition;
- packaging method;
- asking price;
- VAT status;
- original retail value;
- inventory list;
- pickup or shipping terms.

Missing values must remain unknown.

---

## 10. Permitted unknowns

The following may remain `null` at discovery time:

- exact item count;
- price;
- VAT inclusion;
- brand list;
- sizes;
- gender/age segments;
- condition distribution;
- damaged or returned share;
- original retail value;
- seller motivation;
- storage requirements;
- transport costs;
- sale deadline;
- whether sub-lots are accepted.

A candidate must not be rejected solely because these analysis fields are unavailable.

---

## 11. Opportunity Dossier evidence targets

For a qualified candidate, the dossier should collect:

### 11.1 Listing evidence

- title;
- full description;
- URL;
- publication/update date;
- seller identity;
- location;
- price and VAT wording;
- quantity wording;
- sale terms;
- pickup/shipping information;
- availability status.

### 11.2 Inventory evidence

- inventory list;
- category counts;
- brands;
- size distribution;
- condition categories;
- new/used/returns/sample status;
- packaging units;
- claimed retail value;
- photos of labels, boxes, racks, pallets, or stock rooms.

### 11.3 Image observations

Images may support observations such as:

- multiple racks of apparel;
- stacked cartons;
- pallets;
- mixed categories;
- visible tags;
- visible retail packaging;
- apparent storage conditions;
- visible damage or disorder.

Image observations must be written as observations with confidence. They must not create exact quantity, brand, condition, or value claims unless clearly readable and traceable.

### 11.4 Seller and business evidence

- company name and organization number when public;
- business type;
- whether the seller is acting commercially;
- reason for sale if stated;
- ownership or authority to sell;
- invoice availability;
- VAT registration when relevant and publicly verifiable.

### 11.5 Missing-data register

The dossier must list every missing field and the consequence of that absence.

---

## 12. Qualification outcomes

### `SALE_CONFIRMED`

Use when:

- a specific lot is publicly offered;
- the subject matches the apparel/textile domain;
- the bundled commercial scale is credible;
- a public link or contact route exists.

Price and exact quantity may still be unknown.

### `CONTACT_REQUIRED`

Use when:

- a large lot is strongly indicated;
- availability, price, quantity, or sale authority requires confirmation;
- the source invites direct inquiry.

### `REJECTED`

Use when:

- the lot is ordinary household clothing;
- the listing lacks commercial scale;
- the source is irrelevant, inaccessible, or untraceable;
- there is no actual sale or lead.

### `EXPIRED`

Use when:

- the listing is sold, withdrawn, deleted, or outside the active sale period.

---

## 13. Seller questions

When contact is appropriate and approved by a human, ask:

1. Is the complete lot still available?
2. Is it sold only as one lot, or are major sub-lots possible?
3. What is the exact or approximate quantity?
4. Is there an inventory list by category, brand, size, and condition?
5. Are the goods new, used, returns, samples, damaged, or mixed?
6. Is the stated price including or excluding VAT?
7. Can the seller issue an invoice?
8. Where is the stock located?
9. How is it packed: pallets, cartons, racks, sacks, or loose items?
10. Are loading equipment and pickup assistance available?
11. Are any items subject to restrictions, liens, ownership disputes, or third-party claims?
12. What is the deadline for collection?
13. Are additional images or a video walkthrough available?
14. What portion is seasonal, obsolete, damaged, or unsellable?
15. Has the lot previously been offered or partially sold?

The Discovery Engine must never contact the seller automatically.

---

## 14. Controlled example fixtures

### Fixture A — positive confirmed sale

```text
Title: Stort klesparti selges samlet
Description: Ca. 1 500 nye plagg fra nettbutikk. Dameklær i flere størrelser. Selges kun samlet. Lager i Trondheim. Pris eks. mva.
```

Expected:

- scenario: `LARGE_LOT`
- status: `SALE_CONFIRMED`
- quantity: approximately 1,500
- location: Trondheim
- VAT wording: excluding VAT
- unsupported values generated: false

### Fixture B — ambiguous contact-required lead

```text
Title: Komplett lager med klær
Description: Større lager etter endring i driften. Ta kontakt for vareliste, antall og pris.
```

Expected:

- scenario: `LARGE_LOT` or `BUSINESS_CHANGE` depending on stronger evidence
- status: `CONTACT_REQUIRED`
- exact quantity: null
- price: null
- preserve lead: true

### Fixture C — negative household bundle

```text
Title: Stor klespakke dame str. M
Description: 25 brukte plagg fra eget skap. Selges samlet.
```

Expected:

- status: `REJECTED`
- reason: ordinary household bundle; not commercial inventory

### Fixture D — positive image-supported lot

```text
Title: Vareparti klær
Description: Selges samlet. Se bilder.
Images: multiple full clothing racks and stacked tagged cartons in a stock room.
```

Expected:

- preserve as candidate: true
- status: `SALE_CONFIRMED` or `CONTACT_REQUIRED` depending on sale clarity
- image observation: business-scale stock appears visible
- exact quantity: null

### Fixture E — duplicate

Two search results point to the same canonical listing URL with slightly different tracking parameters.

Expected:

- one canonical opportunity retained;
- duplicate removed;
- discovery provenance from both results may be preserved.

### Fixture F — wrong primary scenario

```text
Title: Konkursauksjon — 2 000 plagg
Description: Varelager fra konkursbo selges via nettauksjon.
```

Expected:

- primary scenario: `AUCTION` or `BANKRUPTCY` according to architecture rules;
- `large_lot` retained as size attribute;
- do not force primary classification to `LARGE_LOT`.

---

## 15. Acceptance tests

The future implementation must prove:

1. Explicit business-sized bundled stock can classify as `LARGE_LOT`.
2. A household clothing bundle is rejected.
3. Exact quantity is not mandatory when commercial scale is otherwise credible.
4. Weak phrases alone do not qualify a candidate.
5. Images may support scale observations but cannot invent exact values.
6. A stronger scenario such as auction, bankruptcy, store closing, or liquidation can take primary ownership.
7. Missing price, VAT, brands, or sizes remain `null`.
8. A contact-required lot remains outside financial analysis until eligibility is confirmed.
9. Duplicate URLs normalize to one opportunity.
10. No automatic purchase, bid, or contact decision is generated.
11. Every extracted or inferred field retains provenance.
12. The existing Analysis Engine receives only eligible confirmed opportunities.

---

## 16. Completion decision

`LARGE_LOT` is complete when:

- this card is approved and merged;
- controlled fixtures pass future contract tests;
- `docs/00_PROJECT_STATUS.md` marks it complete;
- `WAREHOUSE_SURPLUS` becomes the only next scenario.

No production code, market valuation, financial formula, or new source integration is authorized by this card.