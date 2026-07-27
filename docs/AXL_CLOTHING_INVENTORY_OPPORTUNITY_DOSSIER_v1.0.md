# AXL Clothing Inventory Opportunity Dossier v1.0

**Task:** `AXL_CLOTHING_INVENTORY_OPPORTUNITY_DOSSIER`  
**Domain:** `CLOTHING_INVENTORY`  
**Opportunity ID:** `CLOTHING_INVENTORY:NO:934309715:AXL`  
**Candidate:** `AXL Sport og Fritid Kolvereid AS konkursbo`  
**Observed at:** `2026-07-27`  
**Primary dossier state:** `DOSSIER_EVIDENCE_REQUIRED`  
**Commercial decision:** `NO_DECISION`  
**Retention rule:** Preserve in the opportunity report and evidence queue; do not reject or delete because decision evidence is incomplete.  
**Automatic commercial action:** Prohibited

## 1. Purpose

Build the first complete Opportunity Dossier for the confirmed AXL Clothing Inventory opportunity.

This dossier converts the merged evidence-verification checkpoint into a structured evidence package. It preserves the active opportunity, records what is confirmed and unknown, prepares seller questions, and defines the exact gates for later market and cost analysis.

This dossier does not calculate market value, acquisition cost, expected profit, ROI, maximum bid, or an investment decision. It does not contact, reserve, bid, purchase, or pay.

## 2. Canonical dossier result

```text
CONFIRMED_ACTIVE_CLOTHING_INVENTORY_OPPORTUNITY
DOSSIER_EVIDENCE_REQUIRED
CONTACT_REQUIRED
NO_DECISION
```

The opportunity remains commercially relevant and must remain visible in later operator and final reports.

Missing quantity, acquisition price, VAT, fees, inspection, pickup, packing, and transport evidence blocks financial analysis. Missing evidence is not a discovery rejection reason.

## 3. Identity and source

| Field | Value | Evidence class | Source |
|---|---|---|---|
| Opportunity ID | `CLOTHING_INVENTORY:NO:934309715:AXL` | Internal deterministic identifier | This dossier |
| Domain | `CLOTHING_INVENTORY` | CONFIRMED_SOURCE_FACT | Approved project scope |
| Primary scenario | `COMPANY_BANKRUPTCY` | CONFIRMED_SOURCE_FACT | Brønnøysundregistrene |
| Secondary scenario | `INVENTORY_LIQUIDATION` | CONFIRMED_SOURCE_FACT | Norsk Avvikling active sale |
| Record type | `SALE_LISTING` | CONFIRMED_SOURCE_FACT | Public active bankruptcy sale |
| Discovery status | `SALE_CONFIRMED` | CONFIRMED_SOURCE_FACT | Norsk Avvikling marks the sale active |
| Advertisement title | `AXL Sport Og Fritid Kolvereid — KONKURSSALG PÅGÅR` | CONFIRMED_SOURCE_FACT | Norsk Avvikling |
| Source provider | `Norsk Avvikling AS` | CONFIRMED_SOURCE_FACT | Norsk Avvikling |
| Source domain | `norskavvikling.no` | CONFIRMED_SOURCE_FACT | Norsk Avvikling |
| Primary source URL | `https://norskavvikling.no/` | CONFIRMED_SOURCE_FACT | Norsk Avvikling |
| Discovery query | `UNKNOWN_NOT_PRESERVED_IN_CHECKPOINT` | UNKNOWN | Not present in merged evidence checkpoint |
| First public observation used by dossier | `2026-07-27` | CONFIRMED_SOURCE_FACT | Merged evidence checkpoint |
| Publication date | `UNKNOWN` | UNKNOWN | Not published on the observed sale card |
| Expiry or sale deadline | `UNKNOWN` | UNKNOWN | Not published on the observed sale card |

## 4. Company, bankruptcy estate, and liquidation identity

### 4.1 Debtor company

| Field | Value | Evidence class | Source |
|---|---|---|---|
| Legal name | `AXL SPORT OG FRITID KOLVEREID AS` | CONFIRMED_SOURCE_FACT | Brønnøysundregistrene |
| Organisation number | `934 309 715` | CONFIRMED_SOURCE_FACT | Brønnøysundregistrene |
| Company form | `Aksjeselskap` | CONFIRMED_SOURCE_FACT | Brønnøysundregistrene |
| Registered status | `Konkurs` | CONFIRMED_SOURCE_FACT | Brønnøysundregistrene |
| Bankruptcy registered | `10 March 2026` | CONFIRMED_SOURCE_FACT | Brønnøysundregistrene |
| Bankruptcy opening time | `9 March 2026` | CONFIRMED_SOURCE_FACT | Brønnøysundregistrene expanded company information |
| Industry code | `47.631 — Detaljhandel med sportsvarer` | CONFIRMED_SOURCE_FACT | Brønnøysundregistrene |
| Business address | `Sentrumsgata 2, 7970 Kolvereid, Nærøysund, Norway` | CONFIRMED_SOURCE_FACT | Brønnøysundregistrene |
| Registered business purpose | Retail within hunting, fishing, leisure and dog products, including equipment and clothing for outdoor activities | CONFIRMED_SOURCE_FACT | Brønnøysundregistrene expanded company information |

Public company record:

```text
https://virksomhet.brreg.no/nb/oppslag/enheter/934309715
```

### 4.2 Bankruptcy estate

| Field | Value | Evidence class | Source |
|---|---|---|---|
| Estate name | `AXL SPORT OG FRITID KOLVEREID AS KONKURSBO` | CONFIRMED_SOURCE_FACT | Brønnøysundregistrene |
| Estate organisation number | `937 325 746` | CONFIRMED_SOURCE_FACT | Brønnøysundregistrene |
| Estate business address | `Sentrumsgata 2, 7970 Kolvereid` | CONFIRMED_SOURCE_FACT | Brønnøysundregistrene |
| Estate postal route | `v/Adv. Nils Christian Sudbø Brandzæg, Postboks 8809 Nedre Elvehavn, 7481 Trondheim` | CONFIRMED_SOURCE_FACT | Brønnøysundregistrene |
| Estate administrator | `Adv. Nils Christian Sudbø Brandzæg` | CONFIRMED_SOURCE_FACT | Brønnøysundregistrene |
| Exact cause of bankruptcy | `UNKNOWN` | UNKNOWN | No verified public cause statement captured |
| Estate report or administrator report | `NOT_CAPTURED` | UNKNOWN | Must be requested or located before stating the cause |

Public estate record:

```text
https://virksomhet.brreg.no/nb/oppslag/enheter/937325746
```

### 4.3 Reason for liquidation

The confirmed reason the goods are being offered through a liquidation route is the registered bankruptcy and the public statement that a bankruptcy sale is ongoing.

The underlying commercial cause of the bankruptcy is not confirmed. Revenue, loss, debt, timing, or negative-equity data must not be presented as the cause without an estate report, court document, or explicit administrator statement.

```text
sale_reason: BANKRUPTCY_SALE
bankruptcy_cause: UNKNOWN
```

## 5. Sale operator and contact routes

### 5.1 Primary public sale route

Norsk Avvikling publicly marks:

```text
STATUS: AKTIV
AXL Sport Og Fritid Kolvereid
KONKURSSALG PÅGÅR
```

Public sale operator contact:

| Route | Published value | Evidence class |
|---|---|---|
| Website | `https://norskavvikling.no/` | CONFIRMED_SOURCE_FACT |
| Telephone | `480 75 000` | CONFIRMED_SOURCE_FACT |
| Email | `info@norskavvikling.no` | CONFIRMED_SOURCE_FACT |
| Address | `Norvald Strands veg 45, 2212 Kongsvinger` | CONFIRMED_SOURCE_FACT |

This is the preferred first route for sale terms because Norsk Avvikling publicly presents the active sale.

### 5.2 Estate-administrator route

The public estate record identifies the administrator and postal route:

```text
Adv. Nils Christian Sudbø Brandzæg
Postboks 8809 Nedre Elvehavn
7481 Trondheim
```

No administrator email or direct telephone number is preserved in this dossier. Do not invent one.

### 5.3 Store contact route

The public AXL store still exposes:

| Route | Published value | Evidence class |
|---|---|---|
| Contact page | `https://axlsportogfritid.no/kontakt-oss/` | CONFIRMED_SOURCE_FACT |
| Address | `Sentrumsgata 2, 7970 Kolvereid` | CONFIRMED_SOURCE_FACT |
| Telephone | `+47 901 64 884` | CONFIRMED_SOURCE_FACT |
| Email/contact form | Published on the store contact page | CONFIRMED_SOURCE_FACT |

This route proves traceability but is not automatically treated as the authoritative acquisition route after bankruptcy. Sale terms must be confirmed by Norsk Avvikling or the estate administrator.

## 6. Sale terms

| Field | Current dossier value | Evidence class | Consequence |
|---|---|---|---|
| Sale active | `true` | CONFIRMED_SOURCE_FACT | Opportunity remains live |
| Sale method | `CONTACT_REQUIRED` | CONFIRMED_SOURCE_FACT | No public AXL lot price or bid interface captured |
| Whole lot or partial sale | `UNKNOWN` | UNKNOWN | Blocks lot design and valuation |
| Asking price | `UNKNOWN` | UNKNOWN | Blocks acquisition-cost analysis |
| Current bid | `NOT_APPLICABLE_OR_NOT_PUBLISHED` | UNKNOWN | No public auction bid captured |
| Currency | `UNKNOWN_FOR_LOT` | UNKNOWN | Confirm with sale operator |
| VAT statement for lot | `UNKNOWN` | UNKNOWN | Blocks true acquisition cost |
| Buyer premium or fees | `UNKNOWN` | UNKNOWN | Blocks true acquisition cost |
| Payment deadline and method | `UNKNOWN` | UNKNOWN | Blocks execution planning |
| Inspection availability | `UNKNOWN` | UNKNOWN | Blocks condition verification |
| Pickup location | `LIKELY_KOLVEREID_BUT_UNCONFIRMED` | ESTIMATE | Company address is not proof of stock location |
| Pickup deadline | `UNKNOWN` | UNKNOWN | Blocks logistics planning |
| Loading support | `UNKNOWN` | UNKNOWN | Blocks transport planning |
| Packing or pallets | `UNKNOWN` | UNKNOWN | Blocks transport planning |
| Warranty | General site terms state bankruptcy goods are sold as-is without guarantee | CONFIRMED_SOURCE_FACT | Requires inspection and conservative condition evidence |
| Quantity or quality warranty | General site terms state the operator may not warrant count or quality for lot sales | CONFIRMED_SOURCE_FACT | Inventory list must be independently verified |
| Third-party ownership risk | General site terms acknowledge possible third-party-owned goods | CONFIRMED_SOURCE_FACT | Included-goods and title confirmation required |

The general terms are published by Norsk Avvikling. The dossier must still confirm which terms and exclusions apply specifically to AXL.

## 7. Inventory evidence

### 7.1 Clothing

The public AXL clothing category exposes:

```text
161 catalogue entries
```

Observed clothing categories include:

- children;
- belts;
- women;
- gloves and mittens;
- men;
- headwear;
- junior;
- mid-layers;
- suspenders;
- socks;
- outdoor and hunting clothing accessories;
- underwear;
- unisex;
- outerwear.

Public category:

```text
https://axlsportogfritid.no/produktkategori/klaer/
```

Evidence classification:

```text
clothing_catalogue_present: CONFIRMED_SOURCE_FACT
clothing_catalogue_entry_count: 161
physical_clothing_unit_count: UNKNOWN
included_clothing_skus: UNKNOWN
```

### 7.2 Sample clothing products and catalogue prices

The following are examples visible on the public clothing page. These values are retail catalogue prices only.

| Product | Public catalogue price | Evidence class |
|---|---:|---|
| Aclima HotWool Crewneck Unisex | 799 NOK | CONFIRMED_SOURCE_FACT |
| Aclima WoolTerry Longs Mann | 899 NOK | CONFIRMED_SOURCE_FACT |
| Aclima WoolTerry Polo Mann | 749 NOK | CONFIRMED_SOURCE_FACT |
| Deerhunter Excape Winter Jakke | 3,599 NOK current public price | CONFIRMED_SOURCE_FACT |
| Deerhunter Excape Winter Trousers | 2,490 NOK current public price | CONFIRMED_SOURCE_FACT |
| Didriksons Annema WNS Full Zip 6 | 1,249 NOK current public price | CONFIRMED_SOURCE_FACT |

```text
catalogue_price_nok != acquisition_price_nok
catalogue_price_nok != liquidation_price_nok
catalogue_price_nok != market_value_nok
catalogue_price_nok != maximum_safe_bid_nok
```

### 7.3 Confirmed clothing brands visible in public sources

The public store and category pages expose examples from brands including:

- Aclima;
- BS;
- Deerhunter;
- Didriksons;
- Lundhags;
- Harkila;
- Swedteam;
- Move On.

Brand visibility confirms product-range relevance. It does not confirm that every visible brand, SKU, size, or unit remains physically present or is included in the bankruptcy sale.

### 7.4 Footwear

The public store exposes a footwear category and products from brands including:

- Alfa;
- Crispi;
- Muckboot;
- Nokian;
- Skechers;
- Treksta.

Classification:

```text
footwear_catalogue_present: CONFIRMED_SOURCE_FACT
physical_footwear_unit_count: UNKNOWN
included_footwear_skus: UNKNOWN
```

Footwear is an adjacent inventory class. It must be separated from clothing in quantity, market comparables, expected sell-through, and resale assumptions.

### 7.5 Non-clothing inventory

The full public shop exposes:

```text
388 catalogue entries
```

The wider catalogue includes fishing, outdoor, dog, hunting, clothing, footwear, and related merchandise.

Public shop:

```text
https://axlsportogfritid.no/butikk/
```

Classification:

| Inventory class | Public catalogue evidence | Physical inclusion in sale |
|---|---|---|
| Clothing | Confirmed | Unknown by SKU and unit |
| Footwear | Confirmed | Unknown by SKU and unit |
| Fishing | Confirmed in wider catalogue | Unknown |
| Hunting | Confirmed in wider catalogue | Unknown |
| Dog products | Confirmed in wider catalogue | Unknown |
| Outdoor equipment | Confirmed in wider catalogue | Unknown |
| Fixtures, furniture, IT, or shop equipment | Not established by captured sources | Unknown |

Non-clothing inventory must not be mixed into the Clothing Inventory financial model. It may remain recorded as adjacent or excluded inventory pending a verified stock list.

## 8. Quantity, sizes, condition, and ownership

| Required fact | Status | Evidence class |
|---|---|---|
| Exact total physical units | Not known | UNKNOWN |
| Exact clothing units | Not known | UNKNOWN |
| Exact footwear units | Not known | UNKNOWN |
| SKU distribution | Not known | UNKNOWN |
| Size distribution | Not known | UNKNOWN |
| Colour distribution | Not known | UNKNOWN |
| Brand distribution by units | Not known | UNKNOWN |
| New, returned, display, used, damaged, or seconds status | Not known by unit | UNKNOWN |
| Packaging condition | Not verified | UNKNOWN |
| Stock ownership by estate | Not verified by line item | UNKNOWN |
| Reserved, sold, returned, or excluded goods | Not known | UNKNOWN |
| Catalogue availability equals physical availability | Not established | UNKNOWN |

A catalogue entry is not a unit count. A visible product page is not proof that the item is physically present, owned by the estate, unsold, or included in the transaction.

## 9. Images and attachments

| Evidence item | Status | Classification |
|---|---|---|
| Norsk Avvikling AXL sale-card image | Publicly referenced but not archived in this dossier | AVAILABLE_NOT_INGESTED |
| AXL product images | Publicly accessible on product pages but not archived in this dossier | AVAILABLE_NOT_INGESTED |
| Inventory spreadsheet | Not found | UNKNOWN |
| Inventory PDF | Not found | UNKNOWN |
| Sale prospectus | Not found | UNKNOWN |
| Photograph set of the physical remaining stock | Not found | UNKNOWN |
| Purchase invoices or cost records | Not found | UNKNOWN |
| Estate report or administrator report | Not captured | UNKNOWN |

No exact physical count, storage condition, packaging condition, or lot size is inferred from public catalogue images.

## 10. Evidence register: confirmed, unconfirmed, and required

### 10.1 Confirmed

| Fact | Status |
|---|---|
| AXL company identity and organisation number | CONFIRMED |
| Bankruptcy status | CONFIRMED |
| Bankruptcy estate identity | CONFIRMED |
| Estate administrator identity and postal route | CONFIRMED |
| Public active bankruptcy sale | CONFIRMED |
| Norsk Avvikling contact route | CONFIRMED |
| Company and public-store location in Kolvereid | CONFIRMED |
| Dedicated clothing catalogue | CONFIRMED |
| 161 clothing catalogue entries | CONFIRMED_AS_CATALOGUE_COUNT_ONLY |
| 388 full-shop catalogue entries | CONFIRMED_AS_CATALOGUE_COUNT_ONLY |
| Clothing and footwear categories | CONFIRMED |
| Public retail catalogue prices | CONFIRMED_AS_RETAIL_CATALOGUE_PRICES_ONLY |

### 10.2 Unconfirmed

| Fact | Status |
|---|---|
| Exact reason the company became insolvent | UNCONFIRMED |
| Exact inventory remaining now | UNCONFIRMED |
| Physical unit quantity | UNCONFIRMED |
| Which catalogue products are in the bankruptcy sale | UNCONFIRMED |
| Whole-lot or partial-sale structure | UNCONFIRMED |
| Acquisition price | UNCONFIRMED |
| VAT and buyer fees | UNCONFIRMED |
| Pickup location and deadline | UNCONFIRMED |
| Loading, packing, pallets, and transport requirements | UNCONFIRMED |
| Condition by unit | UNCONFIRMED |
| Third-party ownership or exclusions | UNCONFIRMED |

### 10.3 Required verification

| Evidence required | Why it matters |
|---|---|
| Dated inventory list in Excel, CSV, or PDF | Establishes SKUs and quantities |
| Confirmation of units remaining on the response date | Prevents stale-catalogue valuation |
| Clothing, footwear, and non-clothing separation | Prevents category contamination |
| Brand, size, colour, and condition distribution | Enables comparable selection and sell-through analysis |
| Sale method and whether the lot can be divided | Defines acquisition structure |
| Asking price, reserve, bid, or offer basis | Enables acquisition-cost analysis |
| VAT statement and buyer fees | Enables true acquisition cost |
| Inspection route and physical stock photographs | Enables condition and count verification |
| Pickup address, deadline, access, and loading support | Enables logistics evidence |
| Packing, pallet, volume, and weight information | Enables transport quotations |
| Included, sold, reserved, excluded, returned, or third-party goods | Confirms legal and physical scope |
| Estate report or explicit administrator statement | Required before stating the cause of bankruptcy |

## 11. Opportunity-specific seller questions

The following question set is ready for human review. No message is sent automatically.

1. Is the AXL sale still active, and who is the authorised person for purchase discussions?
2. Is the inventory sold as one complete lot, several category lots, or individual products?
3. Can you provide a dated Excel, CSV, or PDF list of all remaining inventory?
4. How many physical units remain in total, separated into clothing, footwear, and non-clothing goods?
5. Does the list include SKU, brand, product name, size, colour, quantity, and condition?
6. Which goods shown in the online catalogue are sold, reserved, excluded, returned, or no longer physically available?
7. What is the asking price, bid basis, reserve, or required offer format?
8. Is the transaction price including or excluding MVA, and are buyer fees or other charges added?
9. Can the clothing and footwear stock be purchased separately from fishing, hunting, dog, or other goods?
10. Is inspection possible before an offer, and are current photographs of the physical stock available?
11. Where is the inventory physically stored, and what are the pickup and removal deadlines?
12. Is loading equipment or labour available, and is the stock packed on pallets, in boxes, or on racks?
13. Are any goods owned by third parties, subject to retention of title, or otherwise excluded from sale?
14. Are purchase invoices, supplier lists, or original cost records available?
15. Is an estate report or another public document available that states the verified background of the bankruptcy?

## 12. Prepared market-analysis attributes

The dossier may prepare attributes but does not collect or evaluate comparables yet.

| Attribute | Prepared value |
|---|---|
| Geographic resale market | Norway |
| Opportunity location | Kolvereid, Nærøysund |
| Primary inventory class | Outdoor, hunting, and leisure clothing |
| Adjacent inventory class | Outdoor footwear and boots |
| New or used status | Appears retail catalogue stock; physical condition remains unverified |
| Brand examples | Aclima, Deerhunter, Didriksons, Lundhags, Harkila, Swedteam, Move On |
| Clothing segment examples | Base layers, socks, outerwear, mid-layers, underwear, gloves, headwear |
| Target comparable unit | Same brand, model, condition, and size when verified |
| Quantity range | UNKNOWN |
| Sellable-unit count | UNKNOWN |

No market value is prepared or implied.

## 13. Handoff gates

### 13.1 Dossier existence gate

```text
PASS
```

The dossier has:

- a valid public sale source and contact route;
- a clear description of the commercial inventory opportunity;
- a confirmed bankruptcy and liquidation scenario;
- evidence that this is an inventory event rather than a single-item listing;
- a complete known/unknown evidence register.

### 13.2 Market-comparable gate

Current state:

```text
BLOCKED_EVIDENCE_REQUIRED
```

Minimum evidence required before verified comparable collection:

- confirmed included categories;
- representative or complete SKU list;
- brand and product/model identity;
- condition;
- size information when size materially affects saleability;
- physical availability date.

A limited exploratory market scan may be prepared only after these attributes are verified. It must not generate a lot valuation from catalogue counts alone.

### 13.3 Acquisition-cost gate

Current state:

```text
BLOCKED_EVIDENCE_REQUIRED
```

Required before true acquisition-cost integration:

- acquisition price or offer basis;
- VAT treatment;
- buyer premium and fees;
- payment terms;
- pickup and removal conditions;
- packing and loading requirements;
- verified transport quotation or evidence;
- storage or handling costs when applicable.

Missing components must remain unknown and must not be treated as zero.

### 13.4 Financial-analysis gate

Current state:

```text
NOT_ALLOWED
```

The existing Analysis Engine may be invoked only when the market and acquisition-cost evidence gates are satisfied to the level required by their existing contracts.

The following are prohibited now:

```text
expected_profit_nok
roi_percent
maximum_safe_bid_nok
BUY_REVIEW
WATCH
REJECT
```

`WATCH` must not be used merely as a substitute for incomplete dossier evidence unless the existing downstream decision policy is actually invoked with eligible evidence.

## 14. Reporting and retention contract

This opportunity must remain in the system and appear in operator and final opportunity reports while active.

Recommended report presentation:

```text
AXL Clothing Inventory
Status: Confirmed active opportunity
Dossier: Evidence required
Decision: No decision
Why retained: real active bankruptcy inventory opportunity
Blocking evidence: quantity, included SKUs, price, VAT, fees, condition, pickup, packing, transport
Next action: human-approved evidence request to Norsk Avvikling or the estate administrator
```

Allowed later transitions:

```text
DOSSIER_EVIDENCE_REQUIRED
  -> DOSSIER_CONTACT_REQUIRED
  -> DOSSIER_READY_FOR_ANALYSIS
  -> VERIFIED_MARKET_COMPARABLES
  -> VERIFIED_ACQUISITION_COSTS
  -> ANALYSIS_ENGINE
  -> BUY_REVIEW / WATCH / REJECT
```

The opportunity may transition to rejected or expired only through documented evidence such as:

- the sale ended or was withdrawn;
- no commercially meaningful clothing inventory remains;
- the assets are not available for sale;
- the source becomes inaccessible and no contact route remains;
- verified acquisition or market evidence produces a downstream `REJECT`.

Incomplete information alone does not delete or reject the opportunity.

## 15. Source register

| Source | Purpose | Observation |
|---|---|---|
| `https://norskavvikling.no/` | Active sale status, operator contact, general bankruptcy-sale terms | AXL marked active; bankruptcy sale ongoing |
| `https://virksomhet.brreg.no/nb/oppslag/enheter/934309715` | Debtor identity, status, address, industry, bankruptcy relationship | Company bankrupt; estate linked |
| `https://virksomhet.brreg.no/nb/oppslag/enheter/937325746` | Estate identity, administrator postal route, estate address | Estate traceable |
| `https://axlsportogfritid.no/produktkategori/klaer/` | Clothing range, categories, sample products and retail catalogue prices | 161 catalogue entries |
| `https://axlsportogfritid.no/butikk/` | Full catalogue scope and non-clothing adjacency | 388 catalogue entries |
| `https://axlsportogfritid.no/kontakt-oss/` | Public store contact and location traceability | Contact page accessible |
| `https://axlsportogfritid.no/` | Public storefront and clothing/footwear positioning | Storefront accessible |

## 16. Safety invariants

```text
automatic_purchase_decision: false
automatic_bid: false
automatic_contact: false
automatic_reservation: false
automatic_payment: false
```

`BUY_REVIEW` remains human-review-only.

## 17. Definition of done

This dossier task is complete when:

1. exactly one dossier document is added;
2. every important fact is traceable to a public source or explicitly labelled internal;
3. the active opportunity remains retained in reports despite incomplete decision evidence;
4. company, estate, sale operator, location, clothing, footwear, and non-clothing scope are separated;
5. catalogue counts and retail prices are not treated as physical quantities, acquisition prices, liquidation prices, or market values;
6. the exact cause of bankruptcy remains unknown unless supported by verified evidence;
7. missing quantity, price, VAT, fees, condition, pickup, packing, and transport remain explicit;
8. seller questions target only material unknowns;
9. market and acquisition-cost gates remain blocked until verified evidence exists;
10. the canonical output is `DOSSIER_EVIDENCE_REQUIRED` with `NO_DECISION`;
11. no workflow, production code, classifier, test, fixture, state, cache, financial formula, scoring threshold, or decision policy is modified;
12. no contact, bid, reservation, purchase, or payment is performed.

## 18. Next task only

Exactly one task may follow after this dossier is reviewed and merged:

```text
AXL_CLOTHING_INVENTORY_EVIDENCE_REQUEST_PACKAGE
```

That task may prepare, but must not automatically send, a concise human-reviewable evidence request in Norwegian to the authorised sale contact.

Market analysis, acquisition-cost integration, scoring, and investment decisions remain blocked until the required evidence is obtained.
