# INVENTORY_LIQUIDATION Knowledge Card v1.0

**Domain:** `CLOTHING_INVENTORY`  
**Scenario:** `INVENTORY_LIQUIDATION`  
**Status:** READY FOR REVIEW  
**Purpose:** Define how inventory-liquidation opportunities appear in the Norwegian apparel market and how Discovery should distinguish a real commercial stock-disposal opportunity from ordinary retail discounts, isolated listings, or unrelated business news.

---

## 1. Real-world event

An inventory liquidation occurs when a company deliberately disposes of a material quantity of apparel or related stock in order to release capital, reduce storage, exit a product line, resolve overstock, simplify operations, or prepare for a broader business change.

The company may still be operating. Inventory liquidation is therefore not equivalent to bankruptcy or store closure.

A valid scenario can involve:

- complete stock;
- a defined product category;
- seasonal leftovers;
- discontinued lines;
- excess imported goods;
- customer returns or B-grade stock where clearly disclosed;
- mixed apparel lots;
- stock from an online store, warehouse, importer, wholesaler, or physical retailer.

The scenario becomes commercially relevant when the stock is offered as a meaningful business lot or when a credible liquidation lead identifies stock that may become available.

---

## 2. Seller motivations

Common seller motivations include:

- freeing working capital;
- reducing warehouse cost;
- ending a product line;
- clearing old-season goods;
- simplifying the assortment;
- changing suppliers or brands;
- closing an online shop while continuing another activity;
- disposing of returns, samples, or discontinued stock;
- reducing stock before relocation;
- preparing for a merger, restructuring, ownership change, or business-model change;
- handling inventory that is slow-moving but still saleable.

Discovery must preserve the stated motivation exactly when available. It must not infer bankruptcy, closure, or distress unless the source provides evidence.

---

## 3. Opportunity forms

### 3.1 Confirmed public sale

A public listing clearly offers a defined stock or lot for sale.

Examples:

- complete remaining inventory from an online clothing shop;
- 1,200 garments sold as one lot;
- assorted branded apparel sold wholesale;
- discontinued collection sold together;
- rest stock offered by importer or retailer.

Possible status: `SALE_CONFIRMED`.

### 3.2 Partial inventory liquidation

A company sells one category or collection while continuing business.

Examples:

- all winter jackets;
- complete children’s clothing category;
- discontinued bridal-accessory line;
- returned goods or samples sold as a lot.

Possible status: `SALE_CONFIRMED` if the lot and sale route are explicit.

### 3.3 Liquidation lead requiring contact

The source indicates that stock is being cleared, but no direct sale terms, asset list, or purchase route are published.

Examples:

- company announces that it is winding down an online store;
- wholesaler states that excess stock must be cleared;
- business post says remaining inventory is available to interested buyers without details.

Status: `CONTACT_REQUIRED`.

### 3.4 Auction or broker-managed liquidation

The inventory is sold through an auctioneer, asset manager, broker, or liquidation company.

The opportunity remains `INVENTORY_LIQUIDATION` when liquidation is the commercial event. The sales mechanism may separately be `AUCTION`.

### 3.5 Retail clearance to consumers

A normal consumer sale, even with large discounts, is not automatically an acquisition opportunity.

It qualifies only if evidence shows that a meaningful stock lot is available for commercial purchase or transfer.

---

## 4. Scenario boundaries

### Use `INVENTORY_LIQUIDATION` when

- the company is disposing of a material stock quantity;
- the reason is stock reduction, line exit, capital release, or operational change;
- there is a direct lot sale or a credible stock-availability lead;
- the company may still be operating;
- liquidation is the main commercial event.

### Use another scenario when

- the entire store is closing: `STORE_CLOSING`;
- the company or estate is in bankruptcy: `BANKRUPTCY`;
- the central evidence is simply that a large lot is sold, without liquidation context: `LARGE_LOT`;
- the stock is explicitly importer excess: `IMPORTER_CLEARANCE` may be more specific;
- the stock is warehouse surplus without a broader liquidation process: `WAREHOUSE_SURPLUS` may be more specific;
- the source is only an auction listing and no liquidation context is known: `AUCTION` may be primary.

When multiple scenarios are supported, preserve one primary scenario and record secondary scenario evidence without inventing hierarchy.

---

## 5. Norwegian language signals

A phrase is not enough by itself. Classification depends on the combination of language, stock scale, seller context, and sale route.

### 5.1 Strong signals

Strong signals directly describe stock liquidation or a business-lot disposal:

- `hele varelageret selges`
- `komplett varelager til salgs`
- `varelager avvikles`
- `restlager selges samlet`
- `lagerbeholdning selges`
- `partisalg av klær`
- `engrosparti klær`
- `overskuddslager selges`
- `lageret tømmes`
- `restparti fra nettbutikk`
- `nedlagt nettbutikk – varelager til salgs`
- `avvikling av varebeholdning`
- `sluttlager selges`
- `varer selges samlet til forhandler`
- `lagerparti for videresalg`

Strong signals still require evidence that the goods match the Clothing Inventory domain and that the source is active or traceable.

### 5.2 Medium signals

Medium signals suggest stock reduction but require context:

- `oppryddingssalg`
- `lagerutsalg`
- `lagertømming`
- `restesalg`
- `overskuddsvarer`
- `utgående kolleksjon`
- `siste parti`
- `partivarer`
- `grossistparti`
- `selges i parti`
- `må bort raskt`
- `frigjøre lagerplass`
- `redusere varelager`
- `avslutter produktlinje`
- `selger restbeholdning`

A medium signal becomes meaningful when combined with quantity, commercial seller identity, lot language, multiple units, wholesale context, or evidence that the stock is sold collectively.

### 5.3 Weak signals

Weak signals do not establish inventory liquidation alone:

- `salg`
- `rabatt`
- `kampanje`
- `outlet`
- `billig`
- `alt må bort`
- `ryddesalg`
- `sesongsalg`
- `black week`
- `final sale`
- `siste sjanse`

These may describe ordinary consumer marketing.

---

## 6. Context combinations

Discovery should identify combinations rather than isolated terms.

### Combination A — direct confirmed lot

- commercial seller;
- apparel stock;
- `hele varelageret`, `restlager`, or similar;
- quantity, category, images, or lot description;
- explicit sale route or contact.

Outcome: likely `SALE_CONFIRMED`.

### Combination B — online-store stock exit

- online shop is closing or changing category;
- remaining clothing inventory is mentioned;
- stock may be bought collectively;
- contact route exists.

Outcome: `SALE_CONFIRMED` if the lot is explicitly for sale; otherwise `CONTACT_REQUIRED`.

### Combination C — warehouse reduction

- seller is a retailer, importer, distributor, or wholesaler;
- reason is warehouse reduction or capital release;
- stock is apparel-related;
- lot scale is meaningful;
- sale terms or buyer contact exist.

Outcome: usually `SALE_CONFIRMED` or `CONTACT_REQUIRED`.

### Combination D — ordinary consumer clearance

- only discount percentages;
- products sold individually;
- no commercial lot or stock transfer;
- no quantity or wholesale route.

Outcome: `REJECTED` for the acquisition objective.

### Combination E — vague social-media post

- seller says `lager må bort`;
- no quantity, no category breakdown, and no direct purchase terms;
- commercial identity is plausible;
- contact route exists.

Outcome: `CONTACT_REQUIRED`, not rejection.

---

## 7. False positives and rejection rules

Reject or downgrade results when they are:

- ordinary end-of-season retail sales;
- discount campaigns for consumers;
- single garments or small household bundles;
- resale listings from private individuals without commercial scale;
- outlet advertisements without stock-lot availability;
- fashion jobs, courses, repair services, or sewing services;
- articles about inventory management without a sale opportunity;
- business news that discusses overstock but offers no contact or acquisition route;
- expired, removed, or inaccessible pages with insufficient preserved evidence;
- duplicate copies of the same opportunity;
- listings for non-apparel goods outside the active domain;
- generic statements such as `alt må bort` with no stock, seller, or commercial context.

Do not reject solely because price, exact quantity, VAT status, brand list, transport, or comparables are missing.

---

## 8. Likely publication channels

Channels are discovery routes, not the governing architecture.

Possible channels include:

- public classified listings;
- wholesale and business-to-business marketplaces;
- auction platforms;
- liquidation and asset-sale companies;
- company websites;
- online-store closure pages;
- social-media business pages and groups;
- local newspapers;
- commercial-property or relocation announcements;
- importer, distributor, and wholesaler pages;
- insolvency or restructuring notices where stock disposal is separately indicated;
- search-engine results that lead to public sale or contact evidence.

Discovery must retain the final source URL and source-domain provenance.

---

## 9. Minimum discovery data

Preserve a candidate when the following minimum evidence exists:

- `domain`: `clothing_inventory`;
- primary scenario: `inventory_liquidation`;
- what is sold or potentially available;
- evidence that the opportunity concerns a meaningful stock or lot;
- public source URL or public contact route;
- seller or business identity when available;
- location when available;
- source title or original text;
- discovery date;
- discovery query or channel;
- preliminary status: `SALE_CONFIRMED`, `CONTACT_REQUIRED`, `REJECTED`, or `EXPIRED`;
- evidence references supporting the classification.

Price and exact quantity are helpful but not mandatory at discovery time.

---

## 10. Permitted unknowns

The following fields may remain `null` or explicitly unknown:

- exact quantity;
- brand list;
- size distribution;
- condition breakdown;
- original retail value;
- asking price;
- VAT treatment;
- whether price includes VAT;
- storage location details;
- pallet, rack, or box count;
- transport and loading requirements;
- buyer restrictions;
- sales deadline;
- exclusivity;
- return-stock percentage;
- damaged or B-grade percentage;
- ownership and authorization evidence;
- whether fixtures are included;
- whether the lot can be split.

Unknown values must not be converted into estimates during Discovery.

---

## 11. Opportunity Dossier evidence targets

For a qualified candidate, collect all legally and publicly accessible evidence.

### 11.1 Listing and seller evidence

- title;
- full description;
- seller name;
- business identity;
- organization number if publicly available;
- contact route;
- publication date;
- update date;
- status or expiry;
- location;
- stated reason for liquidation;
- stated sale terms.

### 11.2 Inventory evidence

- stated quantity;
- product categories;
- brands;
- sizes;
- season or collection;
- new, returned, sample, used, damaged, or mixed condition;
- packaging state;
- pallet, rack, box, or hanging-garment evidence;
- whether tags are attached;
- inventory list or spreadsheet;
- images showing scale and storage;
- fixtures or equipment included.

### 11.3 Commercial evidence

- asking price;
- auction terms;
- VAT wording;
- minimum purchase;
- whether the lot is divisible;
- buyer eligibility;
- pickup deadline;
- payment conditions;
- loading responsibility;
- storage deadline;
- reservation or deposit requirements.

### 11.4 Provenance rules

Every dossier field must be marked as one of:

- `CONFIRMED_SOURCE_FACT`;
- `SELLER_CLAIM`;
- `IMAGE_OBSERVATION`;
- `INFERRED_WITH_CONFIDENCE`;
- `UNKNOWN`.

Any inference must include a confidence level and supporting evidence. Discovery and Dossier must not manufacture an exact fact from an image.

---

## 12. Image observations

Images may support observations such as:

- visible clothing categories;
- approximate storage form;
- racks, pallets, boxes, shelves, or bags;
- visible brand labels;
- visible retail tags;
- apparent new or mixed condition;
- signs of shop, warehouse, or home storage;
- approximate lot scale as a broad range only;
- presence of fixtures.

Images must not be used to assert:

- exact quantity without countable evidence;
- authenticity of brands;
- exact condition of unseen goods;
- original purchase price;
- market value;
- VAT status;
- ownership;
- completeness of the stock.

---

## 13. Seller questions

When public evidence is incomplete, prepare questions such as:

1. Is the stock still available?
2. Is the sale for the complete inventory or only selected categories?
3. What is the approximate unit count?
4. Is an inventory list available?
5. Which brands and categories are included?
6. What is the size distribution?
7. Are the goods new, returned, samples, B-grade, damaged, or mixed?
8. Are original tags and packaging included?
9. What is the asking price, and does it include VAT?
10. Can the lot be divided?
11. Where is the stock stored?
12. What are the pickup, loading, and deadline requirements?
13. Are racks, boxes, pallets, or fixtures included?
14. Why is the inventory being liquidated?
15. Does the seller have authority to sell the goods?
16. Are there restrictions on resale, brands, territories, or online marketplaces?

No question is sent automatically.

---

## 14. Qualification outcomes

### `SALE_CONFIRMED`

Use when:

- a real apparel stock or lot is explicitly offered for sale;
- seller or sales agent is identifiable;
- source URL or contact route exists;
- evidence shows more than ordinary individual-product retailing.

Missing price or quantity does not automatically prevent this status if the sale itself is explicit.

### `CONTACT_REQUIRED`

Use when:

- inventory liquidation is credible;
- stock availability is plausible;
- direct sale terms or asset details are missing;
- public contact exists or can be researched lawfully.

### `REJECTED`

Use when:

- the result is ordinary consumer retailing;
- no meaningful stock-lot opportunity exists;
- the goods are outside the Clothing Inventory domain;
- the source is irrelevant noise.

### `EXPIRED`

Use when:

- the page is explicitly expired, removed, sold, or inaccessible;
- preserved evidence is insufficient for an active candidate.

Expired evidence may remain as a test fixture but must not be presented as a current opportunity.

---

## 15. Controlled example fixtures

These fixtures are synthetic and exist only for acceptance testing. They are not live opportunities.

### Fixture A — confirmed complete inventory sale

**Title:** `Komplett varelager fra nettbutikk selges samlet`  
**Text:** A Norwegian online clothing shop is ending its apparel category and offers approximately 1,400 new garments as one lot. Contact and warehouse location are provided.  
**Expected:** `SALE_CONFIRMED`  
**Primary scenario:** `INVENTORY_LIQUIDATION`  
**Reason:** Defined commercial lot, explicit sale, material scale, and contact route.

### Fixture B — contact-required liquidation lead

**Title:** `Vi reduserer lageret kraftig`  
**Text:** A wholesaler announces that excess clothing stock must be cleared and invites business buyers to make contact, but publishes no inventory list or price.  
**Expected:** `CONTACT_REQUIRED`  
**Reason:** Credible stock-disposal signal, but sale details remain incomplete.

### Fixture C — ordinary discount campaign

**Title:** `50 % rabatt på alle jakker denne helgen`  
**Text:** Products remain individually available to retail customers. No lot sale or stock transfer is offered.  
**Expected:** `REJECTED`  
**Reason:** Consumer promotion, not an acquisition opportunity.

### Fixture D — single private bundle

**Title:** `Klespakke dame størrelse M`  
**Text:** A private seller offers ten used garments.  
**Expected:** `REJECTED`  
**Reason:** Insufficient commercial scale and not a business inventory liquidation.

### Fixture E — duplicate publication

Two pages contain the same seller, title, location, images, and lot details, but different tracking parameters.  
**Expected:** one canonical candidate; duplicate removed.

### Fixture F — missing price but explicit sale

**Title:** `Restlager med merkeklær selges samlet`  
**Text:** Commercial seller, clear lot, images, contact route, but price is `etter avtale`.  
**Expected:** `SALE_CONFIRMED` with `price = null`.

### Fixture G — mixed scenarios

**Title:** `Butikk fortsetter, men hele barneavdelingen avvikles`  
**Text:** Store remains open but sells the complete children’s clothing inventory.  
**Expected:** primary `INVENTORY_LIQUIDATION`; secondary business-change evidence may be preserved.  
**Reason:** The commercial event is disposal of a defined inventory category, not total store closure.

### Fixture H — inaccessible expired listing

A historical search result references a complete stock sale, but the page is removed and no description, contact, images, or archived evidence remain.  
**Expected:** `EXPIRED`, not current `SALE_CONFIRMED`.

---

## 16. Acceptance tests

The later implementation must demonstrate all of the following.

### Classification

- A clear complete-stock sale is classified as `INVENTORY_LIQUIDATION` and `SALE_CONFIRMED`.
- A credible liquidation announcement without sale terms becomes `CONTACT_REQUIRED`.
- A normal retail discount is rejected.
- A small private clothing bundle is rejected.
- A store that remains open while disposing of one department is not automatically classified as `STORE_CLOSING`.

### Missing data

- Missing price remains `null`.
- Missing quantity remains `null`.
- Missing VAT treatment remains `null`.
- Missing brands or sizes do not cause automatic rejection.
- No financial estimate is generated during Discovery.

### Evidence

- Source URL is retained.
- Raw title and text are retained.
- Discovery query or channel is retained.
- Image observations are separated from source facts.
- Seller claims are not silently converted into verified facts.

### Deduplication

- Tracking-parameter variants normalize to one candidate.
- Reposts of the same opportunity do not create duplicate dossiers.
- Distinct lots from the same seller remain distinct when evidence differs.

### Engine boundary

- `SALE_CONFIRMED` may enter the Opportunity Dossier and downstream Analysis eligibility checks.
- `CONTACT_REQUIRED` remains outside financial analysis until sale availability is confirmed.
- No buy, bid, or contact action is automated.

---

## 17. Completion criteria

This card is complete when:

- scenario boundaries are approved;
- signals and context combinations are accepted;
- false positives are explicit;
- minimum data and permitted unknowns are defined;
- Dossier evidence targets are clear;
- fixtures cover positive, ambiguous, negative, duplicate, and expired cases;
- acceptance tests can be translated into code without adding financial logic;
- `INVENTORY_LIQUIDATION` is marked complete in the work plan after review and merge.

---

## 18. Next checkpoint

After this card is approved and merged:

1. mark `INVENTORY_LIQUIDATION` complete;
2. set `LARGE_LOT` as the only next scenario;
3. do not begin any other scenario before that repository checkpoint is merged.
