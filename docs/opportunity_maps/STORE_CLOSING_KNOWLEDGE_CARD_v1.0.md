# STORE_CLOSING Knowledge Card v1.0

**Domain:** `CLOTHING_INVENTORY`  
**Scenario:** `STORE_CLOSING`  
**Status:** READY FOR REVIEW  
**Purpose:** Define how a clothing-store closure appears in the real Norwegian market so Discovery can preserve valid opportunities without performing financial analysis.

## 1. Real-world event

A physical or online clothing retailer is ending all or part of its operation and may dispose of saleable inventory.

The scenario includes:

- permanent closure of the entire store;
- closure of one branch;
- shutdown of a physical shop while continuing online;
- shutdown of an online shop with remaining warehouse stock;
- exit from clothing retail while the company continues another activity;
- closure following retirement, lease loss, weak sales, relocation, ownership change, or strategic restructuring.

A store-closing signal is not automatically a confirmed inventory sale. It becomes a confirmed opportunity only when public evidence shows that stock, a lot, or store contents are available for purchase.

## 2. Seller motivation

Typical motivations include:

- release cash before closing;
- clear premises before lease termination;
- avoid storage, transport, or return costs;
- dispose of unsold seasonal goods;
- end a product category or retail activity;
- reduce assets before winding down the company;
- sell remaining stock after moving the business online;
- simplify a business after ownership or strategy changes.

The motivation is discovery context. It is not proof of profitability.

## 3. Opportunity forms

| Form | Description | Discovery outcome |
|---|---|---|
| Complete inventory sale | All remaining clothing stock is offered together | `SALE_CONFIRMED` when the sale is explicit |
| Partial inventory sale | Selected categories, seasons, brands, or sizes are offered | `SALE_CONFIRMED` when lot scope is commercially meaningful |
| Mixed stock and fixtures | Clothing plus racks, mannequins, furniture, lights, or décor | Preserve as a mixed opportunity; do not assume all value is clothing |
| Public closing sale to consumers | Goods are discounted item by item in the shop | Usually not a bulk acquisition opportunity; preserve only when wholesale or lot purchase is possible |
| Contact lead | Closure is confirmed but stock availability is not | `CONTACT_REQUIRED` |
| Branch closure | One location closes while the company continues | Classify as `BRANCH_CLOSURE` when branch-specific; avoid duplicate classification |
| Online-store shutdown | Remaining e-commerce stock or warehouse stock is offered | `SALE_CONFIRMED` or `CONTACT_REQUIRED`, depending on evidence |
| Auction or estate sale | Closing stock is sold through auction or an administrator | Use the governing scenario that best describes the sale channel while retaining store-closing evidence |

## 4. Norwegian language signals

Signals must be interpreted in context. A phrase alone does not always prove a bulk opportunity.

### 4.1 Strong closure signals

These strongly indicate that operations are ending:

- `opphørssalg`
- `butikken legges ned`
- `butikken stenger permanent`
- `avvikling av butikk`
- `virksomheten avvikles`
- `siste åpningsdag`
- `vi avslutter driften`
- `nettbutikken legges ned`
- `lageret selges etter nedleggelse`
- `sluttlager etter butikkstenging`

### 4.2 Strong inventory-availability signals

These strongly indicate that stock may be purchased:

- `hele varelageret selges`
- `komplett varelager til salgs`
- `restlager selges samlet`
- `samlet parti`
- `selges som ett parti`
- `lager tømmes`
- `alt lager skal bort`
- `butikkens varelager til salgs`
- `engrosparti klær`
- `vareparti klær`

### 4.3 Medium signals

These are useful only when combined with closure or lot context:

- `alt skal bort`
- `tømmesalg`
- `sluttsalg`
- `flyttesalg`
- `lagerutsalg`
- `siste sjanse`
- `oppryddingssalg`
- `varer selges billig`
- `butikkinnhold selges`
- `restparti`

### 4.4 Weak signals

These must never qualify a result alone:

- `salg`
- `rabatt`
- `kampanje`
- `outlet`
- `sesongsalg`
- `black week`
- `clearance`
- `50 %`
- `billig klær`

## 5. Context combinations

Discovery should look for combinations of evidence rather than one keyword.

### Confirmed store-closing inventory sale

At least one closure signal plus at least one inventory-availability signal, with a public sale route.

Examples:

- `butikken legges ned` + `hele varelageret selges` + price or contact route;
- `opphørssalg` + `selges samlet` + photos of stock;
- `nettbutikken avvikles` + stated quantity + lot price;
- company closure announcement + linked stock-sale listing.

### Contact-required lead

A credible closure signal exists, but the assets are not publicly confirmed for sale.

Examples:

- local news confirms the shop is closing, but no stock sale is mentioned;
- company social page announces final opening day, but only consumer discounts are shown;
- business registry or company post confirms shutdown without an acquisition route.

### Ambiguous commercial result

Inventory language exists, but closure is uncertain or the lot scope is unclear.

Examples:

- `lager tømmes` from a continuing retailer;
- `alt skal bort` during renovation;
- `restlager` with no evidence of clothing quantity or business context.

Preserve as a candidate only when there is enough evidence that it is more than an ordinary single-item listing.

## 6. False positives and rejection rules

Reject or route away from `STORE_CLOSING` when the result is:

- an ordinary seasonal sale by a continuing store;
- a single used garment or a small private wardrobe lot;
- a consumer coupon, campaign, or marketing page;
- a job advertisement related to closing shifts or store staff;
- an article discussing retail closures without identifying a relevant company or contact route;
- a sewing, alteration, styling, or consultancy service;
- a property listing where `butikk` refers only to premises;
- an expired or inaccessible page with no preservable evidence;
- a duplicate of the same sale discovered through another query;
- a branch closure that should be classified under `BRANCH_CLOSURE`;
- a bankruptcy notice without confirmed stock sale, which should be classified under `BANKRUPTCY` or retained as a lead.

A result must not be rejected solely because price, VAT, quantity, brands, sizes, transport cost, or market value are missing.

## 7. Likely publication channels

These are channels where the scenario can appear. They are not the governing product model.

- public marketplace listings;
- auction platforms;
- the retailer's own website or online shop;
- company Facebook, Instagram, or other public social pages;
- shopping-centre announcements;
- local newspaper business reports;
- landlord or commercial-premises announcements;
- bankruptcy-estate or administrator pages when closure follows insolvency;
- wholesale and business-sale portals;
- search-engine results that reveal a previously unknown source;
- public company or registry information used to verify closure context.

## 8. Minimum discovery data

Preserve a candidate when the following can be established:

- `domain`: `clothing_inventory`;
- `scenario`: `store_closing`;
- raw title;
- source URL;
- source channel or domain;
- what appears to be available;
- evidence of closure or shutdown;
- evidence that the result is commercially larger than an ordinary single-item listing;
- location, when available;
- public contact route, when available;
- discovered timestamp;
- relevant text excerpts or structured source facts;
- discovery status;
- missing fields list.

## 9. Possible missing data

The following may remain unknown without rejecting the opportunity:

- exact quantity;
- full inventory list;
- brands;
- size distribution;
- condition by item;
- original retail price;
- seller acquisition cost;
- whether VAT applies or is included;
- whether partial purchase is allowed;
- pickup deadline;
- loading conditions;
- transport, storage, sorting, or labour cost;
- whether fixtures are included;
- whether all stock shown in images is part of the sale;
- whether additional stock exists off-site.

Unknown values must remain `null` or explicitly marked `unknown`.

## 10. Opportunity Dossier evidence targets

When a candidate is selected for dossier creation, collect all publicly available evidence.

### Advertisement evidence

- full title and description;
- price and price qualifiers;
- publication and update dates;
- location;
- seller or administrator identity;
- sale terms;
- pickup or deadline information;
- stated quantity, categories, brands, or sizes;
- whether the sale is complete, partial, or negotiable.

### Image evidence

- all accessible listing images;
- visible clothing categories;
- visible brand names or labels;
- shelves, rails, pallets, boxes, or warehouse layout;
- apparent condition and packaging;
- evidence of mixed fixtures or non-clothing assets;
- text visible in signs, price sheets, labels, or posters;
- uncertainty notes where quantity or condition cannot be established reliably.

### External evidence

- company website or public closure announcement;
- public company status and business identity;
- local news confirming the closure reason or date;
- linked inventory lists, PDF attachments, spreadsheets, or sale catalogues;
- administrator or contact details;
- duplicate listings or archived source references that improve traceability.

### Evidence labeling

Every dossier statement must be labeled as one of:

- `CONFIRMED_FACT`;
- `SELLER_CLAIM`;
- `VISUAL_OBSERVATION`;
- `ESTIMATE` with confidence;
- `UNKNOWN`.

## 11. Qualification outcomes

### `SALE_CONFIRMED`

Use when:

- a real sale route exists;
- the subject clearly includes clothing inventory or a commercially meaningful clothing lot;
- public evidence connects the sale to closure or shutdown;
- the source is accessible and traceable.

### `CONTACT_REQUIRED`

Use when:

- closure is credible;
- inventory may exist;
- no confirmed public sale of the inventory is available.

Suggested next action: identify the seller, administrator, owner, or public contact and prepare factual questions. The system must not contact anyone automatically.

### `REJECTED`

Use when:

- the result is ordinary retail promotion, a single item, unrelated content, or outside the configured commercial scope.

### `EXPIRED`

Use when:

- the sale has ended or the source is inaccessible and no sufficient evidence can be preserved.

## 12. Seller questions generated from missing data

The dossier may prepare questions such as:

1. Gjelder salget hele varelageret eller bare deler av det?
2. Finnes det en komplett vareliste med antall, merker, størrelser og varegrupper?
3. Er varene nye, returvarer, utstillingsvarer eller brukte?
4. Er oppgitt pris inkludert eller ekskludert merverdiavgift?
5. Kan deler av lageret kjøpes separat, eller må alt kjøpes samlet?
6. Følger butikkinnredning, stativer, dukker eller annet utstyr med?
7. Finnes det innkjøpsfakturaer eller dokumentasjon på tidligere utsalgspriser?
8. Hvor befinner varene seg, og når må de hentes?
9. Er varene pakket og klare for transport?
10. Finnes det mer lager på et annet sted enn det som vises i annonsen?

These questions are generated output, not automatic communication.

## 13. Example fixtures

The fixtures below are controlled examples for later tests. They are not live market claims.

### Positive fixture A — confirmed complete stock sale

**Title:** `Klesbutikk legges ned – hele varelageret selges samlet`  
**Text:** Store closes permanently. Approximately 1,800 new garments are offered as one lot. Price and pickup location are stated.  
**Expected scenario:** `STORE_CLOSING`  
**Expected status:** `SALE_CONFIRMED`  
**Reason:** closure + complete inventory + public sale route.

### Positive fixture B — online-store shutdown

**Title:** `Nettbutikk avvikles – restlager med klær og tilbehør`  
**Text:** Remaining stock is sold as a lot; quantity is approximate and photos are provided.  
**Expected scenario:** `STORE_CLOSING`  
**Expected status:** `SALE_CONFIRMED`.

### Ambiguous fixture C — closure without stock confirmation

**Title:** `Etter 12 år stenger motebutikken`  
**Text:** Local article confirms the final opening date but contains no sale listing or inventory contact route.  
**Expected scenario:** `STORE_CLOSING`  
**Expected status:** `CONTACT_REQUIRED`.

### Ambiguous fixture D — consumer closing sale

**Title:** `Opphørssalg – 70 % på alle varer`  
**Text:** Goods are sold item by item to consumers. No lot purchase or wholesale contact is shown.  
**Expected outcome:** retain only as `CONTACT_REQUIRED` when there is credible potential for unsold closing stock; otherwise reject from the bulk-inventory objective.

### Negative fixture E — ordinary campaign

**Title:** `Sesongsalg på klær`  
**Text:** A continuing retailer advertises normal discounts.  
**Expected status:** `REJECTED`.

### Negative fixture F — private small lot

**Title:** `10 dameklær selges samlet`  
**Text:** Private used wardrobe sale with no business or closure context.  
**Expected status:** `REJECTED`.

### Duplicate fixture G

Two search queries return the same canonical URL with tracking parameters.  
**Expected behavior:** normalize the URL and retain one candidate with both discovery-query references.

## 14. Acceptance tests

The scenario card is implementable only when later code can satisfy these observable rules.

1. A result with a strong closure signal, a strong inventory-sale signal, and a public sale route is classified as `STORE_CLOSING` and `SALE_CONFIRMED`.
2. A credible closure announcement without confirmed inventory sale is classified as `STORE_CLOSING` and `CONTACT_REQUIRED`.
3. A weak discount signal alone never creates a confirmed opportunity.
4. Missing price, VAT, quantity, brands, sizes, or transport data does not cause automatic rejection.
5. Ordinary consumer discounts and small private used-clothing lots are rejected from the bulk-inventory objective.
6. Duplicate URLs are normalized and merged while retaining traceability to all discovery queries.
7. No ROI, market value, acquisition cost, transport estimate, or purchase decision is generated during scenario discovery.
8. All source-derived facts preserve source traceability.
9. All inferred statements are marked as estimates or observations rather than facts.
10. A branch-specific closure can be routed to `BRANCH_CLOSURE` without losing the store-closing evidence.
11. A bankruptcy notice without confirmed sale remains a lead and is not forced into financial analysis.
12. A selected candidate exposes evidence targets and missing-data questions required by the Opportunity Dossier.

## 15. Completion criteria

This card is complete when:

- the definition and boundaries are approved;
- strong, medium, and weak signals are accepted;
- false-positive rules are accepted;
- dossier evidence targets are accepted;
- controlled fixtures and acceptance tests are accepted;
- the card is merged into `main`;
- the project status is updated to make `BANKRUPTCY` the only next scenario.
