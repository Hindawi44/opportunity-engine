# FACTORY_SURPLUS Knowledge Card v1.0

**Domain:** `CLOTHING_INVENTORY`  
**Scenario:** `FACTORY_SURPLUS`  
**Status:** READY FOR REVIEW  
**Purpose:** Define how the Discovery Engine recognizes apparel and textile inventory opportunities created by manufacturer overproduction, cancelled production, discontinued lines, factory seconds, or other factory-origin surplus.

---

## 1. Real-world event

A manufacturer, production partner, factory, workshop, brand owner, or contract producer has apparel or textile goods that are no longer required for the original commercial plan and offers them for sale.

Typical events include:

- overproduction beyond confirmed orders;
- cancelled customer orders;
- discontinued styles or production lines;
- rejected export orders that are still commercially usable;
- packaging, labeling, colour, or specification mismatches;
- sample, showroom, pre-production, or development stock;
- factory seconds with disclosed cosmetic or quality deviations;
- end-of-season or end-of-contract production residue;
- raw materials or finished garments left after production completion.

The factory does not need to be closing or insolvent. The defining feature is that the goods originate from production-side surplus rather than ordinary retail stock.

---

## 2. Seller motivations

Common motivations include:

- recover cash from unsold production;
- release factory or warehouse capacity;
- clear cancelled-order inventory;
- avoid storage, disposal, or destruction costs;
- liquidate discontinued models or obsolete packaging;
- sell production overruns;
- clear imperfect but usable goods;
- end a customer, export, licensing, or private-label contract;
- remove samples and pilot-production units;
- sell excess fabric, trims, labels, or finished garments.

Motivation may be explicit or inferred from evidence. Inference must be marked as such.

---

## 3. Opportunity forms

A factory-surplus opportunity may appear as:

- complete finished-garment production run;
- partial production overrun;
- cancelled-order stock;
- mixed apparel lot;
- single-SKU commercial quantity;
- factory seconds or B-grade inventory;
- unbranded or private-label goods;
- samples or showroom stock;
- fabric, trims, packaging, and finished goods combined;
- export residue or goods no longer eligible for the original market;
- contact-required lead where goods are mentioned but no sale terms are public.

A single sample or a few personal items are not enough unless the context clearly indicates a broader commercial stock opportunity.

---

## 4. Scenario boundary

Use `FACTORY_SURPLUS` when the primary cause and source of availability are production-side surplus.

Prefer another scenario when:

- the seller is primarily an importer or distributor clearing imported inventory: `IMPORTER_CLEARANCE`;
- the goods are simply stored excess without evidence of factory origin: `WAREHOUSE_SURPLUS`;
- the business is broadly liquidating stock to release capital: `INVENTORY_LIQUIDATION`;
- the key feature is a large commercial bundle with no production-origin evidence: `LARGE_LOT`;
- the sale is caused by bankruptcy: `BANKRUPTCY`;
- the factory or shop is closing: `STORE_CLOSING` or `BUSINESS_CHANGE`, depending on evidence;
- the opportunity exists only through a bidding process: classify the sale mechanism as `AUCTION` while preserving factory-surplus origin as supporting context where the model permits.

When multiple scenarios apply, preserve all evidence but select the scenario that best explains why the inventory became available.

---

## 5. Norwegian language signals

### 5.1 Strong signals

Strong signals directly connect production origin with surplus or abnormal sale:

- `fabrikkoverskudd`
- `produksjonsoverskudd`
- `overproduksjon`
- `overskuddsproduksjon`
- `restparti fra produksjon`
- `restlager fra fabrikk`
- `kansellert ordre`
- `avbestilt ordre`
- `ubrukt produksjonsparti`
- `feilproduksjon selges`
- `andre sortering`
- `B-varer fra produksjon`
- `utgående produksjonsserie`
- `prøvekolleksjon selges samlet`
- `produksjonsparti selges samlet`

English signals that may appear in Norwegian listings or company pages:

- `factory surplus`
- `production overrun`
- `overstock from factory`
- `cancelled order stock`
- `factory seconds`
- `excess production`
- `production leftovers`

### 5.2 Medium signals

Medium signals require commercial and production context:

- `restparti`
- `partivare`
- `overskuddsvarer`
- `utgående modell`
- `utgått kolleksjon`
- `prøvevarer`
- `vareprøver`
- `showroomprøver`
- `sekundavare`
- `feilvare`
- `sorteringsvare`
- `ubrukt parti`
- `selges samlet`
- `engrosparti`
- `direkte fra produsent`
- `fra produksjon`

### 5.3 Weak signals

Weak signals do not establish this scenario alone:

- `salg`
- `lagerutsalg`
- `restlager`
- `parti`
- `engros`
- `billig`
- `rabatt`
- `utgående`
- `samples`
- `overskudd`

Weak signals need production-origin evidence, commercial scale, or seller identity.

---

## 6. Context combinations

The system should look for combinations rather than one keyword.

### Confirmed-style combinations

- manufacturer identity + production-overrun language + goods offered for sale;
- cancelled order + commercial quantity + public sale or contact route;
- factory seconds + disclosed condition + lot sale;
- discontinued production line + finished stock + sale terms;
- private-label manufacturer + unsold production + quantity or pallet/carton evidence;
- factory or workshop images + repeated identical new goods + sale language;
- sample collection + many units or complete range + collective sale.

### Contact-required combinations

- factory announces cancelled order but no public sale terms;
- company mentions surplus goods and invites business enquiries;
- production residue appears in a company update without price or quantity;
- manufacturer closure/change produces likely stock but availability is not confirmed.

### Insufficient combinations

- ordinary retail sale + no producer evidence;
- one defective garment;
- custom-sewing service advertisement;
- general manufacturer catalogue;
- news about overproduction without identifiable goods or contact path;
- recycling or disposal story with no sale opportunity.

---

## 7. False positives and rejection rules

Reject or route away:

- normal wholesale catalogues with regular ordering terms;
- ordinary retail discounts;
- one used garment or personal bundle;
- job advertisements from factories;
- sewing, manufacturing, or design services;
- factory news without an available asset or contact route;
- recycling-only or destruction-only announcements;
- raw-material listings outside the active Clothing Inventory scope unless finished apparel inventory is also included;
- expired, inaccessible, or clearly completed sales;
- counterfeit or unauthorized branded goods;
- goods whose sale is legally restricted or whose ownership cannot be established;
- isolated samples lacking evidence of commercial scale.

Do not reject solely because price, exact quantity, brand authorization, defects, VAT, logistics, or market value are missing. Preserve the lead and mark the missing data.

---

## 8. Likely publication channels

Channels are discovery paths, not governing sources:

- manufacturer or factory websites;
- brand-owner websites;
- B2B marketplaces;
- wholesale and surplus marketplaces;
- auction platforms;
- liquidation intermediaries;
- company social-media pages;
- local and industry news;
- trade associations;
- export/import business listings;
- public marketplace listings;
- bankruptcy or closure channels where production stock is mentioned;
- direct business contact pages.

The Discovery Engine must remain source-agnostic.

---

## 9. Minimum discovery data

Preserve a candidate when the available evidence identifies:

- what is being sold or may be available;
- source URL or public contact route;
- factory, manufacturer, brand owner, or seller identity when available;
- scenario evidence connecting the goods to production surplus;
- location when available;
- evidence of commercial scale or repeated inventory;
- current status: confirmed sale, contact required, rejected, or expired.

Recommended fields:

```yaml
scenario: FACTORY_SURPLUS
record_type: SALE_LISTING | LIQUIDATION_LEAD | OTHER_LEAD | REJECTED_RESULT
status: SALE_CONFIRMED | CONTACT_REQUIRED | REJECTED | EXPIRED
seller_name: text | null
seller_role: manufacturer | factory | brand_owner | intermediary | unknown
location: text | null
what_is_sold: text
quantity: number | null
quantity_unit: text | null
lot_description: text | null
condition: new | seconds | samples | mixed | unknown
production_origin_evidence: list
source_url: https URL
contact: text | null
price: number | null
currency: text | null
vat_status: text | null
missing_fields: list
```

---

## 10. Permitted unknowns

The following may remain unknown during discovery:

- exact quantity;
- exact product list;
- size and colour distribution;
- brand ownership or authorization;
- defect rate;
- grading method;
- original customer or cancelled order;
- packaging condition;
- labeling status;
- country of production;
- VAT treatment;
- transport and storage costs;
- minimum purchase quantity;
- market value;
- resale restrictions;
- compliance documents;
- whether goods can legally be sold under existing branding.

Unknown values must never be invented.

---

## 11. Opportunity Dossier evidence targets

The Dossier should seek:

### Listing and seller evidence

- full public text;
- seller identity and business role;
- company registration details where publicly accessible;
- manufacturer or factory relationship;
- reason for availability;
- sale terms, deadlines, and minimum quantities;
- ownership and authorization statements;
- contact route.

### Inventory evidence

- item categories;
- approximate quantity;
- SKU count;
- sizes and colours;
- brand or private-label status;
- labels and packaging;
- production dates or seasons;
- cartons, pallets, racks, or container counts;
- sample, A-grade, B-grade, or mixed condition;
- defect description and rate;
- raw materials included with finished goods.

### Image observations

Images may support observations such as:

- repeated identical new goods;
- factory cartons or production packaging;
- palletized or racked commercial quantities;
- unfinished or unlabelled goods;
- mixed grading or visible defects;
- factory, workshop, warehouse, or showroom setting;
- labels, barcodes, tags, and cartons;
- fabric rolls or trims accompanying finished goods.

Image observations must be written as observations, not confirmed facts unless the image clearly proves the claim.

### Compliance and rights evidence

Seek evidence about:

- ownership of the goods;
- right to sell branded inventory;
- trademark or private-label restrictions;
- required relabeling or de-branding;
- product-safety or textile-labeling compliance;
- country-of-origin labeling;
- documentation for imports into Norway, if relevant;
- restrictions from the cancelled customer or original contract.

No legal or compliance conclusion should be invented.

---

## 12. Qualification outcomes

### `SALE_CONFIRMED`

Use when public evidence confirms:

- identifiable apparel or textile inventory;
- production-side surplus origin;
- active sale or auction terms;
- public link or contact route;
- commercial relevance.

### `CONTACT_REQUIRED`

Use when:

- production surplus is credible;
- goods may be available;
- sale status, ownership, quantity, or terms require confirmation.

### `REJECTED`

Use for ordinary retail/wholesale offers, personal items, services, unrelated news, non-commercial samples, or legally problematic goods without a legitimate sale path.

### `EXPIRED`

Use when the sale is completed, withdrawn, inaccessible, or clearly outdated.

---

## 13. Seller questions

Priority questions include:

1. Are the goods currently available for sale?
2. Are you the manufacturer, brand owner, or authorized seller?
3. Why did the goods become surplus?
4. Is this overproduction, a cancelled order, seconds, samples, or discontinued production?
5. What is the exact quantity and SKU breakdown?
6. Are the goods new and unused?
7. What defects or grading differences exist?
8. What percentage is A-grade, B-grade, samples, or damaged?
9. Are brands, labels, and packaging authorized for resale?
10. Are de-branding or relabeling requirements applicable?
11. Are size, colour, and product lists available?
12. What is the minimum purchase quantity?
13. Is the price including or excluding VAT?
14. Where are the goods stored?
15. Are pallet, carton, weight, and volume figures available?
16. Is loading assistance available?
17. Are inspection and sample checks possible?
18. Are compliance and origin documents available?
19. Are there restrictions on market, country, channel, or resale price?
20. What is the deadline for collection or completion?

---

## 14. Controlled fixtures

### Positive fixture A — confirmed sale

> Norsk klesprodusent selger 2,400 nye gensere fra kansellert kundeordre. Varene ligger pakket på paller, og hele eller større deler av partiet kan kjøpes.

Expected:

```yaml
scenario: FACTORY_SURPLUS
status: SALE_CONFIRMED
reason: cancelled production order and active commercial sale
```

### Positive fixture B — factory seconds

> Produksjonsparti med B-sortering selges samlet. Mindre søm- og fargeavvik. Cirka 1,100 plagg.

Expected:

```yaml
scenario: FACTORY_SURPLUS
status: SALE_CONFIRMED
condition: seconds
```

### Ambiguous fixture — contact required

> Vi har fått overskudd etter avsluttet produksjonsserie og vurderer salg til forhandler.

Expected:

```yaml
scenario: FACTORY_SURPLUS
status: CONTACT_REQUIRED
reason: credible production surplus but no confirmed terms
```

### Negative fixture — ordinary wholesale

> Ny kolleksjon tilgjengelig for forhandlere. Bestill fra vår ordinære engroskatalog.

Expected:

```yaml
status: REJECTED
reason: routine wholesale offer, not abnormal surplus
```

### Negative fixture — one sample

> Én prototypejakke selges.

Expected:

```yaml
status: REJECTED
reason: no evidence of commercial inventory scale
```

### Duplicate fixture

The same cancelled-order lot appears on a marketplace and the manufacturer's website with matching seller, quantity, title, and images.

Expected:

```yaml
duplicates_removed: 1
canonical_record_count: 1
```

---

## 15. Acceptance tests

The card is implementable when tests can verify:

1. Production origin plus active commercial sale classifies as `FACTORY_SURPLUS`.
2. A cancelled order alone does not become `SALE_CONFIRMED` without sale or contact evidence.
3. Factory seconds remain eligible when defects are disclosed or unknown.
4. Ordinary wholesale catalogues are rejected.
5. A single prototype without broader commercial evidence is rejected.
6. Missing price, quantity, defect rate, VAT, or logistics do not cause automatic rejection.
7. Missing fields remain `null` or explicitly unknown.
8. Image-derived observations remain separate from confirmed facts.
9. Rights, branding, and compliance uncertainties are preserved for the Dossier.
10. Duplicate listings collapse into one canonical opportunity.
11. No ROI, market value, or purchase decision is produced by Discovery.
12. Confirmed opportunities can be passed to the Opportunity Dossier.
13. Contact-required leads remain outside financial analysis until confirmed.

---

## 16. Completion decision

This card is complete when:

- scenario boundaries are approved;
- signals and false positives are accepted;
- controlled fixtures pass review;
- acceptance tests are considered implementable;
- `docs/00_PROJECT_STATUS.md` and the Clothing Inventory work plan identify `FACTORY_SURPLUS` as ready for review;
- no production or financial code is changed.

The next scenario after approval and merge is `BUSINESS_CHANGE`.
