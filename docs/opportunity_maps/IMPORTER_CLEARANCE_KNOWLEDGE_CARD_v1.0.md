# IMPORTER_CLEARANCE Knowledge Card v1.0

**Domain:** `CLOTHING_INVENTORY`  
**Scenario:** `IMPORTER_CLEARANCE`  
**Status:** READY FOR REVIEW  
**Purpose:** Define how importer- or distributor-led stock clearance appears in the Norwegian market and how Discovery should preserve, classify, and hand it off without inventing financial facts.

---

## 1. Real-world event

An importer, distributor, wholesaler, or brand representative releases clothing or textile inventory because the stock is no longer strategically suitable for normal distribution.

Typical commercial situations include:

- excess imported stock after lower-than-expected demand;
- cancelled retailer orders;
- unsold seasonal collections;
- discontinued brands or product lines;
- packaging or labeling changes;
- customs-released stock that must be sold quickly;
- returns or mixed wholesale batches suitable for resale;
- a distributor ending a supplier relationship;
- cash-flow pressure requiring rapid stock reduction.

The scenario is about **the seller's role and origin of the goods**, not merely the size of the lot.

---

## 2. Seller motivations

Likely motivations include:

- free warehouse capacity;
- recover working capital;
- prepare for a new season;
- exit a brand or supplier agreement;
- resolve cancelled wholesale orders;
- reduce long-storage costs;
- sell discontinued or slow-moving goods;
- move stock after a change in import strategy;
- clear goods before relabeling, repackaging, or contract expiry.

A motivation may be unknown at discovery time. It must remain `null` or `unknown` unless stated by the source or verified through contact.

---

## 3. Opportunity forms

Possible forms include:

- complete importer stock;
- one brand or collection sold as a lot;
- pallets or cartons of clothing;
- mixed sizes and styles;
- cancelled-order inventory;
- end-of-season wholesale stock;
- customer returns or B-grade stock;
- samples and showroom stock;
- discontinued models;
- contact-required importer lead;
- confirmed public sale listing;
- auctioned importer inventory.

`IMPORTER_CLEARANCE` may coexist with `LARGE_LOT`, `WAREHOUSE_SURPLUS`, or `AUCTION`, but the primary classification is chosen from the evidence about why and by whom the stock is offered.

---

## 4. Scenario boundaries

### Importer clearance versus warehouse surplus

Use `IMPORTER_CLEARANCE` when the source identifies an importer, distributor, wholesaler, brand agent, or imported-goods context.

Use `WAREHOUSE_SURPLUS` when the evidence only shows excess warehouse stock and does not establish importer or distributor origin.

### Importer clearance versus inventory liquidation

Use `IMPORTER_CLEARANCE` when the main event is an importer or distributor clearing imported stock.

Use `INVENTORY_LIQUIDATION` when the broader event is business-level inventory disposal without a clear importer-origin signal.

### Importer clearance versus large lot

`LARGE_LOT` describes commercial scale and sale form. `IMPORTER_CLEARANCE` describes seller role and stock origin.

A record can contain both attributes, but only one primary scenario is assigned. Prefer `IMPORTER_CLEARANCE` when importer-origin evidence is explicit.

### Importer clearance versus bankruptcy

A bankrupt importer remains `BANKRUPTCY` until a confirmed sale is established. Once the estate offers imported inventory for sale, the record may retain bankruptcy provenance while the sale form is captured in the dossier.

### Importer clearance versus ordinary wholesale

Routine wholesale catalogs, ordinary reseller pricing, and ongoing B2B sales are not clearance opportunities unless there is evidence of exceptional stock release, discontinuation, cancellation, overstock, or urgency.

---

## 5. Norwegian language signals

### Strong signals

Strong signals usually identify both the seller role and the clearance event:

- `importør selger restlager`
- `restlager fra importør`
- `importør avvikler lager`
- `parti fra importør`
- `engrosparti fra importør`
- `distributør selger restlager`
- `overskuddslager fra grossist`
- `avbestilt vareparti`
- `kansellert ordreparti`
- `utgående merke fra distributør`
- `importlager tømmes`
- `vareparti direkte fra importør`
- `sesongvarer fra importør selges samlet`

### Medium signals

Medium signals require supporting context:

- `restlager`
- `engrosparti`
- `grossistparti`
- `overskuddslager`
- `vareparti`
- `utgående kolleksjon`
- `partisalg`
- `selges samlet`
- `paller med klær`
- `kartonger med klær`
- `returvarer`
- `B-varer`
- `showroomprøver`
- `lager ryddes`

A medium signal becomes meaningful when combined with importer/distributor identity, commercial quantity, packaging, brand representation, or wholesale context.

### Weak signals

Weak signals are insufficient alone:

- `salg`
- `rabatt`
- `outlet`
- `billig`
- `parti`
- `lager`
- `engros`
- `rest`
- `import`

Weak signals may support classification only when other evidence establishes commercial stock clearance.

---

## 6. Context combinations

The following combinations strongly support `IMPORTER_CLEARANCE`:

1. importer/distributor identity + restlager/partisalg;
2. cancelled-order language + commercial clothing quantity;
3. pallets/cartons + wholesale seller + sell-together language;
4. discontinued brand/collection + distributor statement;
5. imported goods + warehouse release + public sale terms;
6. showroom/sample stock + brand agent/importer identity;
7. returns or B-grade stock + importer/distributor provenance;
8. stock list or invoice + importer/company details + sale availability.

The following combinations require follow-up:

- company described as importer, but sale availability is unclear;
- stock is visible in images, but quantity and ownership are unknown;
- an article mentions excess imported goods without a public sale route;
- distributor change is announced, but inventory disposal is only inferred.

---

## 7. False positives and rejection rules

Reject or keep outside this scenario when the result is:

- an ordinary retail discount;
- a standard wholesale catalog;
- one used garment;
- a private household bundle;
- a dropshipping or import-service advertisement;
- a logistics or customs service;
- a job advertisement for an importer;
- an article about imports without stock availability;
- a product page with normal B2B ordering;
- a supplier directory entry;
- an expired or inaccessible listing without preserved evidence;
- a vague `parti` listing with no clothing relevance or commercial scale;
- a counterfeit or rights-infringing goods offer.

Do not upgrade an importer company profile to an opportunity unless the evidence shows or reasonably supports a specific stock release or contact-required lead.

---

## 8. Likely publication channels

Publication channels are discovery channels, not governing sources:

- importer or distributor websites;
- company clearance pages;
- marketplace listings;
- B2B liquidation platforms;
- auction platforms;
- social-media business pages;
- trade groups and local business groups;
- insolvency or restructuring notices;
- local press and trade press;
- newsletters and customer emails;
- warehouse-sale announcements;
- search-engine results leading to public pages.

The system must remain source-agnostic.

---

## 9. Minimum discovery data

A candidate may be preserved when there is enough evidence for:

- what is sold or potentially available;
- clothing/textile relevance;
- importer, distributor, wholesaler, or imported-stock context;
- public source URL or contact route;
- sale status: confirmed or contact required;
- location when available;
- evidence of commercial scale or wholesale form;
- raw title and source text;
- discovery query and source provider;
- discovery timestamp.

The following are useful but not mandatory at discovery time:

- exact quantity;
- full brand list;
- size distribution;
- condition grading;
- VAT treatment;
- customs status;
- original cost;
- resale value;
- transport cost;
- storage requirements;
- seller motivation;
- exclusivity or territory rights.

Missing fields must remain unknown.

---

## 10. Permitted unknowns

The candidate must not be rejected only because these are unavailable:

- exact number of items;
- exact pallet/carton count;
- wholesale price;
- brand authorization;
- labeling language;
- EAN or SKU list;
- customs and duty status;
- returns rate;
- defect rate;
- season or model year;
- storage history;
- sale deadline;
- whether partial purchase is allowed;
- whether VAT is included;
- whether transport is available.

Unknowns become dossier tasks or seller questions.

---

## 11. Opportunity Dossier evidence targets

The dossier should seek:

### Source and seller evidence

- seller legal name;
- organization number when public;
- role: importer, distributor, wholesaler, agent, estate, or intermediary;
- public contact details;
- source URL and publication date;
- sale terms and deadline;
- reason for stock release, when stated.

### Inventory evidence

- stock lists, invoices, packing lists, or SKU exports;
- quantity by carton, pallet, item, or category;
- brand and product categories;
- size distribution;
- season and model year;
- packaging condition;
- new, return, sample, B-grade, or mixed condition;
- labeling and language requirements;
- visible EAN/SKU information;
- ownership and right-to-sell evidence when relevant.

### Image observations

Images may support observations about:

- cartons, pallets, racks, and warehouse scale;
- sealed versus opened packaging;
- repeated identical items;
- visible brands or categories;
- moisture, damage, dust, or poor storage;
- mixed versus uniform stock;
- apparent commercial quantity.

Image-derived statements must be labeled `observed`, not `confirmed`, unless the source explicitly verifies them.

### Sale and logistics evidence

- asking price or auction terms;
- VAT statement;
- minimum purchase quantity;
- partial-lot availability;
- pickup location;
- loading access;
- pallet dimensions and weight;
- transport options;
- deadline and payment conditions.

### Compliance and rights evidence

Where relevant, seek:

- brand authorization or lawful resale rights;
- labeling compliance;
- product-safety or textile-information requirements;
- customs release status;
- restrictions on territory, channels, or online resale.

The Discovery Engine does not decide legal compliance. It preserves evidence and flags missing verification.

---

## 12. Qualification outcomes

### `SALE_CONFIRMED`

Use when:

- a specific imported or importer-held clothing stock is publicly offered;
- a valid link or contact route exists;
- commercial scale is evidenced;
- the sale is current enough to proceed to evidence collection.

### `CONTACT_REQUIRED`

Use when:

- importer/distributor clearance is credible;
- stock likely exists;
- public sale terms or availability are not confirmed;
- contact is needed before financial analysis.

### `REJECTED`

Use when:

- no clothing-inventory relevance exists;
- the result is routine wholesale or ordinary retail;
- the quantity is personal/household scale;
- the page is only a service, directory, job, or article;
- evidence is too weak to preserve as a lead.

### `EXPIRED`

Use when:

- the listing or deadline is clearly expired;
- the stock is marked sold;
- the source is inaccessible and no preserved evidence supports a live lead.

---

## 13. Seller questions

Questions should target missing facts, not negotiate automatically:

1. Are you the importer, distributor, owner, or agent for this stock?
2. Is the stock currently available for sale?
3. What is the total quantity and packaging unit?
4. Can you provide a stock list with brands, models, sizes, and quantities?
5. Are the goods new, returns, samples, B-grade, or mixed?
6. Why is the stock being cleared?
7. Is the price for the full lot or per item/carton/pallet?
8. Is VAT included or added?
9. Can the lot be split?
10. Are there any resale, territory, or brand restrictions?
11. Are the goods customs-cleared and legally available for resale in Norway?
12. Where are the goods stored?
13. What are the pickup, loading, weight, and transport conditions?
14. What is the sale deadline?
15. Can additional photos, invoices, packing lists, or ownership documents be provided?

No message is sent automatically.

---

## 14. Controlled fixtures

### Positive fixture — confirmed importer sale

```yaml
raw_title: "Restlager fra klesimportør selges samlet"
raw_description: "Importør avslutter to merker og selger 2 400 nye plagg i kartonger. Lagerliste tilgjengelig."
seller_context: "registered clothing importer"
source_url: "https://example.no/importer-restlager"
expected_scenario: IMPORTER_CLEARANCE
expected_status: SALE_CONFIRMED
```

Reason: importer identity, clear stock release, commercial quantity, and sale availability are explicit.

### Positive fixture — cancelled order

```yaml
raw_title: "Avbestilt ordreparti med jakker"
raw_description: "Grossist selger 18 paller etter kansellert kjedeordre."
expected_scenario: IMPORTER_CLEARANCE
expected_status: SALE_CONFIRMED
```

Reason: wholesale seller, cancelled-order provenance, and pallet-scale inventory.

### Ambiguous fixture — distributor change

```yaml
raw_title: "Distributør avslutter samarbeid med merke"
raw_description: "Selskapet opplyser at sortimentet fases ut. Eventuelt restlager er ikke annonsert."
expected_scenario: IMPORTER_CLEARANCE
expected_status: CONTACT_REQUIRED
```

Reason: relevant commercial signal, but stock availability is unconfirmed.

### Negative fixture — normal wholesale catalog

```yaml
raw_title: "Engros klær til forhandlere"
raw_description: "Bestill nye kolleksjoner fra vår ordinære B2B-nettbutikk."
expected_status: REJECTED
```

Reason: routine wholesale operation, not clearance.

### Negative fixture — private bundle

```yaml
raw_title: "Stor pose med dameklær"
raw_description: "Ca. 30 brukte plagg fra privat garderobe."
expected_status: REJECTED
```

Reason: household-scale used clothing with no importer context.

### Duplicate fixture

Two URLs with normalized identical title, seller, quantity, and sale description should produce one canonical candidate while preserving both source references.

---

## 15. Acceptance tests

The card is implementable when the following observable rules pass:

1. Explicit importer/distributor identity plus clearance language classifies as `IMPORTER_CLEARANCE`.
2. Cancelled wholesale-order stock with commercial quantity qualifies as `SALE_CONFIRMED` when sale terms exist.
3. Importer or distributor change without confirmed stock availability remains `CONTACT_REQUIRED`.
4. Routine wholesale catalogs are rejected.
5. Ordinary retail discounts are rejected.
6. Private household bundles are rejected.
7. `restlager` alone does not prove importer clearance.
8. Missing price, VAT, quantity, brand list, or transport does not cause automatic rejection.
9. Unknown values remain `null` or explicitly unknown.
10. Image observations are stored as observations, not confirmed facts.
11. No ROI, resale value, customs assumption, or purchase decision is created during discovery.
12. Duplicate records collapse to one canonical candidate while retaining provenance.
13. Records with credible importer-origin evidence retain traceability to the source text and seller identity.
14. Importer clearance is distinguished from warehouse surplus when importer/distributor provenance is explicit.
15. Only confirmed sales may proceed to the Analysis Engine; contact-required leads remain outside financial analysis.

---

## 16. Completion decision

`IMPORTER_CLEARANCE` is ready for approval when:

- the scenario boundaries are accepted;
- strong, medium, and weak signals are accepted;
- fixtures and acceptance tests are accepted;
- no production code or financial formulas are changed;
- `FACTORY_SURPLUS` remains the only next scenario after merge.
