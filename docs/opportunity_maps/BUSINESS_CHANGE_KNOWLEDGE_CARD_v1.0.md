# BUSINESS_CHANGE Knowledge Card v1.0

**Domain:** `CLOTHING_INVENTORY`  
**Scenario:** `BUSINESS_CHANGE`  
**Status:** READY FOR REVIEW  
**Purpose:** Define how a change in business model, product category, ownership structure, or operating format can create a clothing-inventory opportunity without requiring store closure or bankruptcy.

---

## 1. Real-world event

A business changes how it operates and releases apparel inventory that no longer fits the new model.

Typical real-world events include:

- moving from physical retail to online-only;
- removing clothing from the product assortment;
- changing target customer, brand mix, or price segment;
- converting a multi-category shop into a narrower concept;
- closing a department while keeping the company active;
- changing franchise, owner, or commercial concept;
- changing from retail sales to services, showroom, agency, or wholesale;
- consolidating operations and removing duplicated stock;
- ending a seasonal, temporary, or pilot clothing concept;
- ending one sales channel while the company continues elsewhere.

The governing signal is not business failure. It is an operational change that makes part or all of the clothing inventory commercially unnecessary.

---

## 2. Seller motivation

The seller may want to:

- release working capital;
- clear products that no longer match the new concept;
- reduce storage needs;
- avoid moving unwanted stock into a new location or channel;
- remove old brands before introducing a new assortment;
- simplify operations after a merger, ownership change, or restructuring;
- sell inventory before changing legal entity, franchise, or operator;
- reduce duplicated inventory after consolidation;
- exit one category while continuing the rest of the business;
- complete the transition quickly.

A seller can be financially healthy. Financial distress must not be assumed.

---

## 3. Opportunity forms

### 3.1 Confirmed sale forms

- complete clothing category sold as one lot;
- remaining inventory from a discontinued department;
- old brand assortment sold before relaunch;
- stock from a physical store sold after transition to online-only;
- duplicate stock sold after consolidation;
- inventory sold during ownership or franchise change;
- seasonal or concept-specific stock sold after the concept ends;
- mixed apparel and accessories sold together;
- stock offered by category, pallet, rack, box, or complete inventory list.

### 3.2 Contact-required lead forms

- announcement of concept change without confirmed asset sale;
- company states that clothing will leave the assortment but gives no sale terms;
- relocation or ownership change suggesting surplus inventory;
- article about restructuring without evidence that stock is available;
- social post inviting trade inquiries without defining quantity, price, or lot.

### 3.3 Non-qualifying forms

- ordinary rebranding with no inventory release;
- normal seasonal collection change;
- routine retail discount campaign;
- relocation where all stock moves to the new premises;
- change of company name only;
- ownership change with uninterrupted inventory operations;
- individual used garments sold privately.

---

## 4. Scenario boundaries

### BUSINESS_CHANGE vs STORE_CLOSING

- `BUSINESS_CHANGE`: the business continues, but its model, category, channel, ownership, or concept changes.
- `STORE_CLOSING`: the relevant store operation ends.

A company may close one sales channel while continuing elsewhere. Classify by the evidence describing the inventory release, not by a broad assumption.

### BUSINESS_CHANGE vs BRANCH_CLOSURE

- `BUSINESS_CHANGE`: inventory becomes unnecessary because of a broader operating or concept change.
- `BRANCH_CLOSURE`: one named branch closes and releases stock.

### BUSINESS_CHANGE vs INVENTORY_LIQUIDATION

- `BUSINESS_CHANGE`: the reason is an operational transition.
- `INVENTORY_LIQUIDATION`: the defining event is deliberate stock reduction or capital release, with or without a broader business change.

If both are present, preserve both signals and select the primary scenario from the clearest stated cause.

### BUSINESS_CHANGE vs IMPORTER_CLEARANCE

- `BUSINESS_CHANGE`: the seller changes its business model or assortment.
- `IMPORTER_CLEARANCE`: an importer or distributor clears imported stock because of product-line, order, season, or distribution conditions.

### BUSINESS_CHANGE vs BANKRUPTCY

- `BUSINESS_CHANGE`: the business continues or restructures voluntarily.
- `BANKRUPTCY`: insolvency proceedings or estate administration are central.

Do not infer bankruptcy from restructuring language.

---

## 5. Norwegian language signals

Signals are evidence inputs. No isolated word guarantees qualification.

### 5.1 Strong signals

Strong when connected to clothing inventory, stock, lot size, or sale terms:

- `endrer konsept og selger ut varelageret`
- `går over til nettbutikk og selger butikkens varelager`
- `avvikler klesavdelingen`
- `slutter med klær`
- `går ut av klesbransjen`
- `endrer sortiment og selger restlager`
- `nytt konsept – eksisterende varelager selges`
- `eierskifte – gammelt varelager selges`
- `franchiseendring – varer selges samlet`
- `omprofilering – tidligere kolleksjon selges`
- `legger ned avdeling for klær`
- `bytter forretningsmodell og tømmer lageret`
- `butikk blir showroom / nettbutikk – lager selges`
- `kategori utgår – hele partiet selges`

### 5.2 Medium signals

Need supporting evidence:

- `endrer konsept`
- `nytt konsept`
- `omprofilering`
- `endrer sortiment`
- `sortimentsendring`
- `eierskifte`
- `franchisebytte`
- `restrukturering`
- `omorganisering`
- `går over til netthandel`
- `flytter virksomheten`
- `samler driften`
- `slutter med fysisk butikk`
- `avvikler en avdeling`
- `utfasing av produktkategori`

### 5.3 Weak signals

Insufficient without context:

- `nyhet`
- `fornyelse`
- `ny profil`
- `nytt lokale`
- `ny eier`
- `ny kolleksjon`
- `salg`
- `rabatt`
- `kampanje`
- `lager`
- `restvarer`
- `utgående varer`

---

## 6. Context combinations

### 6.1 Confirmed-sale combinations

A candidate may qualify as `SALE_CONFIRMED` when the source establishes:

1. a real business change;
2. clothing inventory or a commercially meaningful apparel lot;
3. explicit availability for sale;
4. a public contact route, sale process, or purchase terms.

Examples:

- `går over til nettbutikk` + `hele butikkens varelager selges samlet`;
- `slutter med klær` + `ca. 900 plagg` + price/contact;
- `eierskifte` + `tidligere varebeholdning følger ikke med` + lot offered;
- `avvikler klesavdelingen` + inventory list or clear images + sale route;
- `nytt konsept` + `alle gamle merkevarer selges som parti`.

### 6.2 Contact-required combinations

Classify as `CONTACT_REQUIRED` when:

- business change is confirmed;
- clothing inventory is plausibly affected;
- sale availability is not confirmed.

Examples:

- `butikken går over til interiørvarer` with no stock-sale statement;
- `slutter med fysisk butikk` but no indication whether inventory moves online;
- ownership change where old inventory treatment is unknown;
- department closure announced without a sale or contact path.

### 6.3 Rejection combinations

Reject when:

- concept change has no inventory consequence;
- discounting is ordinary retail activity;
- the record concerns a single private garment;
- the text is a job, service, event, or course;
- the page only reports corporate strategy with no identifiable opportunity or follow-up lead;
- the clothing inventory is explicitly retained, transferred, or already sold;
- the page is expired or inaccessible and no evidence can be preserved.

---

## 7. False positives

### 7.1 Normal seasonal renewal

`Ny kolleksjon kommer – 30 % på utvalgte varer` is normal retail activity unless evidence shows a substantial commercial lot is being released because of a business change.

### 7.2 Marketing rebrand

A new logo, website, name, or visual identity is not an opportunity by itself.

### 7.3 Normal ownership change

`Butikken har fått ny eier` does not qualify unless inventory treatment or sale availability is stated or reasonably follow-up-worthy.

### 7.4 Relocation without released stock

Moving premises is not an opportunity when the inventory moves with the business.

### 7.5 Routine assortment rotation

Discontinued SKUs sold through normal retail channels are not automatically a commercial inventory opportunity.

### 7.6 Corporate restructuring news

A news article about reorganization is not enough unless it identifies affected clothing inventory or a concrete follow-up route.

### 7.7 Household bundle

Private wardrobe clear-outs and small mixed clothing bundles remain outside scope.

---

## 8. Likely publication channels

Channels describe where evidence may appear. They do not govern architecture.

- company websites and webshop notices;
- social media posts from stores, brands, and owners;
- public marketplaces and classified ads;
- wholesale, lot, and business-asset marketplaces;
- local news and trade press;
- shopping-centre announcements;
- franchise or chain communications;
- business-sale and ownership-transfer listings;
- commercial property or relocation announcements;
- newsletters and customer emails published publicly;
- auction or broker pages when the change leads to a formal sale;
- public business records when they support identity and operational change.

Discovery should search scenario combinations across channels rather than begin from a fixed website list.

---

## 9. Minimum discovery data

A candidate can be preserved with:

- source URL;
- raw title;
- available source text;
- seller or business name when available;
- Norway location when available;
- evidence of the business change;
- what clothing inventory is sold or potentially affected;
- opportunity form or record type;
- sale status: confirmed, contact required, rejected, or expired;
- public contact route or source link;
- opportunity-size description when available;
- discovery timestamp;
- source channel/domain;
- discovery query or signal combination;
- evidence excerpts supporting classification;
- explicit missing fields.

Price, exact quantity, VAT, brands, sizes, condition, and transport are not mandatory at discovery time.

---

## 10. Permitted unknowns

The following may remain `null` or explicitly unknown:

- exact quantity;
- complete inventory list;
- purchase price;
- VAT status;
- brand mix;
- size distribution;
- season and model year;
- product condition;
- original retail value;
- storage conditions;
- packing format;
- pickup deadline;
- whether fixtures are included;
- reason for the business change beyond the public statement;
- whether all or only part of the inventory is available;
- whether the seller accepts partial purchase;
- whether inventory has already been reserved.

Unknowns must not be invented and must not by themselves cause rejection.

---

## 11. Opportunity Dossier evidence targets

### 11.1 Source evidence

- full source text and title;
- publication and update dates when available;
- seller identity and public contact details;
- stated reason for the business change;
- sale terms, deadlines, and scope;
- inventory descriptions;
- attachments, inventory lists, PDFs, and linked pages;
- evidence that the business continues, changes model, or exits a category;
- evidence that stock is actually available.

### 11.2 Image evidence

Preserve all legally and technically accessible images and record only observable facts, such as:

- clothing racks, shelves, boxes, pallets, and cartons;
- apparent product categories;
- visible labels or brands;
- packaging state;
- price tags and hangtags;
- apparent mix of apparel and accessories;
- shop-floor versus warehouse storage;
- duplicated units or commercial-scale repetition;
- visible damage, dust, moisture, or disorder;
- signs that fixtures are included.

Do not infer exact quantity, authenticity, ownership, quality, or market value from images alone.

### 11.3 Business evidence

- company identity and organization number when publicly available;
- operating status;
- branch or location identity;
- ownership or franchise change evidence;
- historical assortment or business model;
- relationship between seller and inventory;
- authorization to sell when unclear.

### 11.4 Inventory evidence

- stock list;
- category breakdown;
- quantities;
- sizes;
- brands;
- seasons;
- condition;
- purchase invoices or provenance when relevant;
- retail and wholesale price references supplied by the seller;
- reserved, excluded, or already sold items.

### 11.5 Sale and logistics evidence

- price and VAT wording;
- whole-lot versus partial-sale terms;
- payment conditions;
- pickup location;
- access restrictions;
- packing and loading responsibility;
- storage deadline;
- transport constraints;
- transfer of fixtures, packaging, or digital assets;
- whether inspection is possible.

---

## 12. Qualification outcomes

### SALE_CONFIRMED

Use only when a public source confirms that a commercially meaningful clothing inventory or lot is available for sale because of a business change.

### CONTACT_REQUIRED

Use when the business change is real and clothing stock is plausibly affected, but availability or sale terms are not confirmed.

### REJECTED

Use for ordinary promotions, irrelevant business changes, single garments, services, jobs, unrelated news, or unsupported assumptions.

### EXPIRED

Use when the sale or lead is no longer active or accessible and evidence indicates it cannot be pursued.

---

## 13. Questions for the seller

1. What specific business change caused this inventory to become available?
2. Is the company continuing under a new concept, channel, owner, or category?
3. Is the complete inventory included or only selected products?
4. What is the exact quantity and category breakdown?
5. Which brands, sizes, seasons, and models are included?
6. Are the products new, returns, samples, seconds, or mixed condition?
7. Is there an inventory list, invoice history, or product export?
8. Is the stated price inclusive or exclusive of VAT?
9. Must the stock be purchased as one lot?
10. Are partial offers accepted?
11. Are fixtures, racks, packaging, or webshop assets included?
12. Where is the inventory stored?
13. What are the pickup and payment deadlines?
14. Can the inventory be inspected?
15. Are any items reserved, consigned, financed, or excluded?
16. Does the seller have authority and ownership rights to transfer the goods?
17. Has the inventory been offered elsewhere or partly sold?
18. Are there transport, loading, access, or storage constraints?

---

## 14. Controlled fixtures

### Fixture A — confirmed positive

**Text:**

> Vi går over til nettbutikk og selger hele varelageret fra den fysiske butikken. Omtrent 1 200 plagg og tilbehør selges samlet. Ta kontakt for lagerliste og pris.

**Expected classification:**

- scenario: `BUSINESS_CHANGE`
- status: `SALE_CONFIRMED`
- rationale: operational channel change + commercial apparel inventory + explicit sale route.

### Fixture B — confirmed positive

**Text:**

> Butikken endrer konsept og slutter med klær. Gjenstående merkevarer og kolleksjoner selges som ett parti.

**Expected classification:**

- scenario: `BUSINESS_CHANGE`
- status: `SALE_CONFIRMED`

### Fixture C — ambiguous lead

**Text:**

> Fra høsten blir vi en ren interiørbutikk. Takk til alle kleskundene våre gjennom årene.

**Expected classification:**

- scenario: `BUSINESS_CHANGE`
- status: `CONTACT_REQUIRED`
- rationale: category exit is confirmed, but stock availability is unknown.

### Fixture D — negative ordinary promotion

**Text:**

> Nytt konsept og ny kolleksjon. 20 % rabatt denne helgen.

**Expected classification:**

- status: `REJECTED`
- rationale: no released commercial inventory or lot.

### Fixture E — negative relocation

**Text:**

> Vi flytter til nye lokaler neste måned. Hele sortimentet blir med videre.

**Expected classification:**

- status: `REJECTED`
- rationale: no inventory is released.

### Fixture F — duplicate

Two sources publish the same seller, same inventory description, same location, and same contact route.

**Expected behavior:**

- preserve both source references when useful;
- create one canonical candidate;
- record duplicate provenance;
- do not double-count the opportunity.

---

## 15. Acceptance tests

The later implementation must prove that:

1. a confirmed business-change inventory sale becomes `SALE_CONFIRMED`;
2. a category-exit announcement without sale terms becomes `CONTACT_REQUIRED`;
3. ordinary rebranding or retail discounting is rejected;
4. relocation with retained inventory is rejected;
5. a single private garment is rejected;
6. missing price or quantity does not cause automatic rejection;
7. no price, quantity, VAT, profit, or condition value is invented;
8. the classifier distinguishes this scenario from store closing, branch closure, liquidation, bankruptcy, importer clearance, and warehouse surplus;
9. duplicate sources do not create duplicate opportunities;
10. source excerpts and URLs remain traceable;
11. only confirmed sales may proceed toward the Opportunity Dossier and Analysis Engine;
12. contact-required leads remain outside financial analysis until sale availability is confirmed;
13. no automatic purchase, bid, or contact action is generated.

---

## 16. Completion decision

This card is ready for review when it provides enough precision for later code and tests to distinguish a real business-change inventory opportunity from ordinary rebranding, relocation, ownership change, seasonal retail activity, and other Clothing Inventory scenarios.

After approval and merge:

1. mark `BUSINESS_CHANGE` complete;
2. set `AUCTION` as the only next scenario;
3. update `docs/00_PROJECT_STATUS.md`;
4. update `docs/opportunity_maps/CLOTHING_INVENTORY_WORKPLAN_v1.0.md`;
5. do not begin `BRANCH_CLOSURE` before the AUCTION checkpoint is merged.
