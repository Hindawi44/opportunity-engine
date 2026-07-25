# AUCTION Knowledge Card v1.0

**Domain:** `CLOTHING_INVENTORY`  
**Scenario:** `AUCTION`  
**Status:** READY FOR REVIEW

## 1. Real-world event

A clothing, footwear, accessory, bridal, textile, or related commercial inventory is offered through a public or private auction process.

The auction may sell:

- one complete inventory;
- several commercial lots;
- one mixed apparel lot;
- stock from a bankruptcy estate;
- stock from a closing store;
- warehouse or importer surplus;
- returned, discontinued, or seasonal goods;
- fixtures and inventory together.

The defining feature is not the commercial cause. The defining feature is the sale mechanism:

```text
buyer competes through bids or an auction allocation process
```

## 2. Seller motivation

Typical motivations include:

- realizing value from a bankruptcy estate;
- disposing of inventory quickly;
- clearing a warehouse or store;
- ending a product line;
- selling repossessed or abandoned goods;
- liquidating assets after restructuring;
- converting commercial stock into cash through a transparent bidding process.

## 3. Scenario boundary

`AUCTION` describes the sales mechanism, while other cards describe the commercial cause.

Examples:

- a bankruptcy estate selling clothing through bidding is both a bankruptcy-origin opportunity and an auction sale;
- a closing store selling complete stock through bidding is a store-closing-origin opportunity and an auction sale;
- an importer selling overstock through bidding is importer-clearance-origin and auction-based.

For classification, preserve both:

```yaml
scenario: AUCTION
origin_context: BANKRUPTCY | STORE_CLOSING | WAREHOUSE_SURPLUS | IMPORTER_CLEARANCE | UNKNOWN
```

Do not erase the origin context when it is supported by evidence.

## 4. Opportunity forms

Common forms include:

- complete inventory sold as one lot;
- several categorized apparel lots;
- pallet or carton lots;
- mixed clothing, shoes, and accessories;
- bridal or formalwear lots;
- textile and fabric lots related to apparel;
- inventory plus shelves, racks, mannequins, and store fixtures;
- timed online auction;
- live auction;
- sealed-bid process;
- direct estate sale described as an auction or bidding round.

## 5. Norwegian language signals

### Strong signals

- `auksjon`
- `nettauksjon`
- `budrunde`
- `høyeste bud`
- `auksjonsobjekt`
- `auksjonsstart`
- `auksjon avsluttes`
- `budfrist`
- `selges på auksjon`
- `konkursauksjon`
- `vareparti på auksjon`
- `lager på auksjon`
- `komplett varelager på auksjon`

### Medium signals

- `bud mottas`
- `gi bud`
- `forbehold om godkjenning av bud`
- `selges samlet til høystbydende`
- `budgivning`
- `auksjonsvilkår`
- `visning etter avtale`
- `kjøpersalær`
- `tilslag`

### Weak signals

These are insufficient alone:

- `salg`
- `parti`
- `restlager`
- `konkursbo`
- `varelager`
- `alt skal bort`
- `pris etter avtale`

A weak signal requires additional auction-mechanism evidence.

## 6. Context combinations

A result is likely `AUCTION` when one of these combinations appears:

### Combination A — explicit auction

```text
auction term
+ commercial apparel inventory
+ public lot or object page
```

### Combination B — bidding process

```text
bid deadline or highest-bid wording
+ stock, inventory, pallets, cartons, or commercial quantity
+ seller or estate context
```

### Combination C — auction cost structure

```text
buyer premium or auction fee
+ bidding or award terms
+ apparel-related lot
```

### Combination D — estate auction

```text
bankruptcy-estate signal
+ auction platform or bidding round
+ inventory is explicitly offered for sale
```

A bankruptcy announcement without an auctioned asset is not an auction opportunity.

## 7. False positives and rejection rules

Reject or downgrade when:

- the page is only a news article about an auction;
- the auction contains one ordinary used garment with no commercial scale;
- the page mentions an auction house but no matching apparel lot;
- bidding is already closed and no sale result or reusable evidence remains;
- the lot is inaccessible and no minimum evidence can be preserved;
- the page is an auction calendar without a specific inventory candidate;
- the word `bud` refers to a job offer, construction tender, or unrelated procurement;
- the auction is for vehicles, heavy machinery, or other excluded assets;
- the listing is a household wardrobe bundle rather than commercial inventory.

## 8. Likely publication channels

Channels may include:

- general auction platforms;
- bankruptcy-estate auction pages;
- liquidator or estate-administrator pages;
- local auction houses;
- business-sale portals;
- marketplace listings that link to a bidding process;
- company or warehouse pages announcing a timed sale;
- public notices and social posts linking to auction lots.

Channels are discovery surfaces, not the governing product model.

## 9. Minimum discovery data

Preserve the candidate when the following are available:

- title or lot name;
- source URL;
- evidence of auction or bidding mechanism;
- what is being sold;
- commercial-scale indication;
- location when available;
- auction end time or bid deadline when available;
- current bid or opening bid when available;
- source/provider identity;
- status of the auction page.

The following may remain unknown:

- final quantity;
- full brand list;
- size distribution;
- condition breakdown;
- reserve price;
- VAT treatment;
- buyer premium;
- dismantling or pickup cost;
- transport cost;
- final winning price;
- market value.

Unknown values must remain `null` or explicitly unknown.

## 10. Opportunity Dossier evidence targets

Collect and preserve:

- full lot title and description;
- auction start and end dates;
- bid deadline;
- opening bid, current bid, and bid increments when public;
- reserve or approval conditions when public;
- buyer premium, fees, VAT, and payment terms;
- pickup location and deadline;
- inspection or viewing details;
- seller, estate, auctioneer, or administrator identity;
- all accessible images;
- attachments, inventory lists, condition reports, and terms;
- source timestamps and provenance;
- evidence of commercial quantity;
- evidence connecting the lot to clothing inventory.

## 11. Image-observation rules

Images may support observations such as:

- racks of garments;
- pallets, cartons, or bags;
- visible categories such as jackets, dresses, shoes, or accessories;
- store or warehouse setting;
- visible tags or unopened packaging;
- mixed or uniform stock;
- apparent condition;
- fixtures included in the lot.

Images must not be used to invent:

- exact quantity;
- exact brand distribution;
- authenticity;
- precise condition percentage;
- resale value;
- hidden damage;
- compliance status.

Record image observations separately from confirmed textual facts.

## 12. Qualification outcomes

### `SALE_CONFIRMED`

Use when:

- a specific matching apparel inventory lot is publicly offered through auction or bidding;
- the lot is active or otherwise actionable;
- there is sufficient evidence to preserve the candidate.

### `CONTACT_REQUIRED`

Use when:

- an auction or estate process is announced but the apparel lot is not yet published;
- the lot exists but essential access details require contact;
- the bidding process is private or by invitation.

### `REJECTED`

Use when:

- the result is unrelated;
- commercial scale is absent;
- it is a household bundle;
- no actual auction candidate exists;
- the asset category is excluded.

### `EXPIRED`

Use when:

- bidding has ended and the opportunity is no longer actionable;
- no follow-up sale or relisting path is available.

Expired evidence may still be retained as a fixture, but must not be presented as live.

## 13. Questions for the seller, auctioneer, or estate

- What exactly is included in the lot?
- Is an inventory list available?
- What is the approximate quantity?
- Are goods sold as one lot or several lots?
- Is VAT added to the winning bid?
- What buyer premium or auction fee applies?
- Is there a reserve price?
- Is the highest bid subject to seller approval?
- What is the pickup deadline?
- Is loading assistance available?
- Are pallets, racks, or fixtures included?
- Can the goods be inspected before bidding?
- Are there damaged, returned, counterfeit-risk, or restricted items?
- Are there brand, size, or condition lists?
- Are any bids already received outside the public page?

## 14. Controlled fixtures

### Positive fixture

```text
Title: Komplett varelager fra klesbutikk selges på nettauksjon
Description: Ca. 1,500 plagg, sko og tilbehør. Budfrist fredag kl. 14. Kjøpersalær 10 %. Henting i Oslo.
Expected: SALE_CONFIRMED / AUCTION
```

### Ambiguous fixture

```text
Title: Konkursbo etter motebutikk
Description: Aktiva vil bli realisert. Mer informasjon kommer.
Expected: CONTACT_REQUIRED / BANKRUPTCY origin, not yet confirmed AUCTION
```

### Negative fixture

```text
Title: Vintagejakke på auksjon
Description: Én brukt jakke fra privat selger.
Expected: REJECTED — no commercial inventory scale
```

### Duplicate fixture

```text
The same lot appears on the auction platform and in a social post linking to it.
Expected: one canonical candidate, auction-platform page retained as primary evidence.
```

## 15. Acceptance tests

The future implementation passes this card when it can demonstrate that:

1. explicit auction wording plus commercial clothing inventory becomes an `AUCTION` candidate;
2. one ordinary used garment is rejected;
3. a bankruptcy notice without an actual auction lot remains `CONTACT_REQUIRED`;
4. current bid, deadline, fees, and VAT remain separate fields;
5. missing quantity or reserve price does not create invented values;
6. expired auctions are not presented as live opportunities;
7. origin context is preserved when supported;
8. duplicate links resolve to one canonical opportunity;
9. only confirmed auction sales enter downstream financial analysis;
10. no automatic bid or purchase decision is generated.

## 16. Completion decision

This card defines the complete `AUCTION` scenario knowledge required for the Clothing Inventory Opportunity Map.

After approval and merge:

- mark `AUCTION` complete;
- set `BRANCH_CLOSURE` as the only next scenario;
- do not begin broader automation before the final scenario card is merged.
