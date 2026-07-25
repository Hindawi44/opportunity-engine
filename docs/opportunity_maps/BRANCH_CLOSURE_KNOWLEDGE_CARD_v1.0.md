# BRANCH_CLOSURE Knowledge Card v1.0

**Domain:** `CLOTHING_INVENTORY`  
**Scenario:** `BRANCH_CLOSURE`  
**Status:** READY_FOR_REVIEW

## 1. Real-world event

A clothing, footwear, accessories, bridal, textile, or related retail company closes one physical branch while the legal entity or other branches may continue operating.

The opportunity exists when the branch closure releases commercial inventory, fixtures, or mixed business assets for sale, transfer, auction, liquidation, or direct negotiation.

A branch closure announcement alone is not automatically a confirmed sale.

## 2. Seller motivation

Typical motivations include:

- reducing fixed costs;
- consolidating operations into fewer stores;
- moving sales online;
- leaving an unprofitable location;
- ending a lease;
- relocating to another city or shopping centre;
- changing concept or product category;
- transferring stock to another branch when only part of the inventory is sold;
- clearing stock before a final closing date.

## 3. Opportunity forms

A branch closure may appear as:

- complete branch inventory sold as one lot;
- selected categories sold in bulk;
- remaining stock after internal transfer;
- branch fixtures and clothing stock sold together;
- public clearance sale where a commercial lot may be negotiated;
- direct B2B sale to another retailer;
- auction of branch assets;
- contact-required lead with no confirmed sale terms yet.

## 4. Scenario boundaries

### BRANCH_CLOSURE versus STORE_CLOSING

- `BRANCH_CLOSURE`: one branch closes while the business may continue elsewhere.
- `STORE_CLOSING`: the specific store operation closes; the wider company status may be unknown or irrelevant.

Use `BRANCH_CLOSURE` when the source explicitly indicates that one location, branch, department, or shop unit is closing while other operations continue or may continue.

### BRANCH_CLOSURE versus BUSINESS_CHANGE

- `BRANCH_CLOSURE`: a physical location closes.
- `BUSINESS_CHANGE`: the company changes model, category, ownership structure, or sales channel without necessarily closing a specific branch.

### BRANCH_CLOSURE versus INVENTORY_LIQUIDATION

- `BRANCH_CLOSURE`: the commercial event is the closure of one location.
- `INVENTORY_LIQUIDATION`: the commercial event is the deliberate conversion of stock into cash, regardless of branch status.

### BRANCH_CLOSURE versus BANKRUPTCY

A branch may close without insolvency. Bankruptcy classification requires explicit insolvency, estate, trustee, or court evidence.

## 5. Norwegian language signals

### Strong signals

These strongly indicate a branch closure when connected to a named retail location:

- `filialen legges ned`
- `avdelingen legges ned`
- `butikken i [sted] stenger`
- `denne filialen stenger`
- `siste åpningsdag`
- `stenger permanent`
- `lokasjonen avvikles`
- `butikken på [senter] opphører`
- `lageret i filialen selges`
- `alt i denne butikken skal bort`

### Medium signals

These require supporting context:

- `flytter ut`
- `leiekontrakten avsluttes`
- `samlokalisering`
- `butikknettverket reduseres`
- `færre butikker`
- `flytter salget på nett`
- `slutter i [sted]`
- `tømmer lokalet`
- `opphørssalg i avdelingen`

### Weak signals

These are insufficient alone:

- `salg`
- `rabatt`
- `alt skal bort`
- `lagersalg`
- `flyttesalg`
- `siste sjanse`
- `butikknytt`
- `ny lokasjon`

## 6. Context combinations

A result becomes materially stronger when several elements appear together:

1. a named branch or location;
2. an explicit permanent closing date or closure statement;
3. evidence of commercial stock or fixtures;
4. a sale, auction, clearance, or contact route;
5. signs that the wider company continues elsewhere;
6. inventory-scale language such as `hele lageret`, `parti`, `butikkinnredning`, or `selges samlet`.

Strong example combination:

> `Filialen i Trondheim legges ned. Hele restlageret av klær og sko selges samlet før siste åpningsdag.`

## 7. False positives and rejection rules

Reject or downgrade when the page is only:

- a temporary renovation closure;
- a holiday or seasonal closure;
- ordinary opening-hours information;
- a relocation where all stock moves to the new location;
- a branch closure with no inventory, assets, or contact opportunity;
- a consumer retail discount with no evidence of commercial-scale stock;
- an old or expired news article with no actionable route;
- a job-loss article without asset-sale evidence;
- a single used garment listing;
- a household clothing bundle;
- an inaccessible page with no preservable evidence.

## 8. Likely publication channels

Channels may include:

- the company website;
- shopping-centre announcements;
- local newspapers;
- social-media posts from the branch or company;
- public marketplaces;
- auction platforms;
- commercial property or lease announcements;
- industry news;
- direct B2B listings;
- public company announcements.

These are discovery channels, not governing sources.

## 9. Minimum discovery data

Preserve the candidate when the following are available:

- source URL;
- raw title;
- raw description or excerpt;
- branch or location name;
- closure signal;
- what may be sold;
- location, when available;
- public contact route or actionable link;
- discovered timestamp;
- source provider and source domain;
- scenario classification;
- discovery evidence supporting the classification.

## 10. Permitted unknowns

The following may remain unknown at discovery time:

- exact quantity;
- brand list;
- size distribution;
- condition breakdown;
- asking price;
- VAT treatment;
- transport cost;
- fixtures included;
- ownership of stock;
- whether inventory will be transferred internally;
- final sale deadline;
- whether the branch closure is part of a wider restructuring.

Unknown values must remain `null` or explicitly unknown.

## 11. Opportunity Dossier evidence targets

Collect, when publicly available:

### Text evidence

- exact closure wording;
- closing date;
- branch address;
- company identity;
- sale terms;
- stock description;
- auction or contact instructions;
- statements about other branches continuing;
- exclusions and reservation clauses.

### Image evidence

Observe without guessing:

- visible clothing racks;
- boxed inventory;
- shelves and fixtures;
- category mix;
- approximate visible density;
- signage indicating closure;
- visible brands only when readable;
- storage and condition indicators.

### Attachments and linked records

- inventory lists;
- auction catalogues;
- terms and conditions;
- branch notices;
- company announcements;
- public registration information;
- lease or relocation notices, when public.

## 12. Qualification outcomes

### `SALE_CONFIRMED`

Use only when the source confirms that branch inventory or commercial assets are actually offered for sale or auction.

### `CONTACT_REQUIRED`

Use when the branch closure is confirmed but stock availability or sale terms are not confirmed.

### `REJECTED`

Use when there is no commercial inventory opportunity or the result is outside scope.

### `EXPIRED`

Use when the closing event or sale has ended and no actionable route remains.

## 13. Questions for the seller or company

- Is the inventory being sold, transferred, returned, or destroyed?
- Is the complete branch stock available?
- What categories and approximate quantities are included?
- Are fixtures included?
- Is the sale one lot or several lots?
- What is the asking price or sales process?
- Is VAT included or added?
- What is the final collection date?
- Who owns the inventory?
- Are any brands restricted from resale?
- Are returns, damaged goods, or display items included?
- Is there an inventory list or image set?

## 14. Controlled fixtures

### Positive fixture — confirmed sale

```text
Title: Filialen i Bergen stenger – hele kleslageret selges samlet
Description: Siste åpningsdag er 30. september. Omtrent 1 200 plagg, stativer og hyller tilbys samlet. Kontakt selskapet for visning.
```

Expected:

- scenario: `BRANCH_CLOSURE`
- status: `SALE_CONFIRMED`
- what_is_sold: clothing inventory and fixtures
- unsupported values generated: false

### Ambiguous fixture — contact required

```text
Title: Kleskjeden legger ned avdelingen i Tromsø
Description: Butikken stenger ved utgangen av måneden. Det er ikke opplyst hva som skjer med varelageret.
```

Expected:

- scenario: `BRANCH_CLOSURE`
- status: `CONTACT_REQUIRED`
- price: null
- quantity: null
- must not enter financial analysis

### Negative fixture — temporary closure

```text
Title: Butikken holder stengt under oppussing
Description: Vi åpner igjen om tre uker.
```

Expected:

- status: `REJECTED`
- reason: temporary closure, no disposal opportunity

### Negative fixture — ordinary sale

```text
Title: Helgetilbud på jakker
Description: 20 prosent rabatt fredag og lørdag.
```

Expected:

- status: `REJECTED`
- reason: ordinary retail promotion

### Duplicate fixture

Two pages describe the same branch, closing date, company, location, and inventory sale.

Expected:

- preserve one canonical candidate;
- retain both source references as evidence when useful;
- count one duplicate removed.

## 15. Acceptance tests

The scenario passes when observable implementation tests prove that:

1. explicit closure of one named branch can classify as `BRANCH_CLOSURE`;
2. a branch-closure announcement without confirmed stock sale becomes `CONTACT_REQUIRED`;
3. confirmed inventory sale may become `SALE_CONFIRMED`;
4. temporary closure is rejected;
5. ordinary consumer discounts are rejected;
6. missing price and quantity remain `null`;
7. no financial estimate is generated during discovery;
8. duplicate branch-closure results are deduplicated;
9. text and image observations retain provenance;
10. only confirmed sales may proceed to the Analysis Engine;
11. no automatic purchase, bid, or contact action occurs.

## 16. Completion decision

This card defines the final scenario in the Clothing Inventory Opportunity Map. After approval and merge:

- mark all ten scenario cards complete;
- close the knowledge-card phase;
- begin the approved Clothing Inventory end-to-end implementation checkpoint;
- do not expand to another domain before one complete discovery-to-report cycle succeeds.
