# AXL Active Clothing Inventory Evidence Verification v1.0

**Task type:** Evidence verification checkpoint  
**Domain:** `CLOTHING_INVENTORY`  
**Candidate:** `AXL Sport og Fritid Kolvereid AS konkursbo`  
**Observed at:** `2026-07-27`  
**Verification outcome:** `CONFIRMED_ACTIVE_CLOTHING_INVENTORY_OPPORTUNITY`  
**Commercial decision:** `NO_DECISION`  
**Automatic commercial action:** Prohibited

## 1. Purpose

Execute exactly the approved verification task:

```text
AXL_ACTIVE_CLOTHING_INVENTORY_EVIDENCE_VERIFICATION
```

This checkpoint determines only whether the named lead is a real active Clothing Inventory opportunity that may proceed to an Opportunity Dossier.

It does not estimate purchase value, market value, expected profit, resale time, transport cost, or a maximum bid. It does not contact the seller, reserve goods, bid, purchase, or pay.

## 2. Verification result

```text
CONFIRMED_ACTIVE_CLOTHING_INVENTORY_OPPORTUNITY
NO_DECISION
```

The opportunity is confirmed because current public evidence establishes all of the following:

1. the bankruptcy sale remains publicly marked active;
2. the named bankrupt company is the same company operating the public product catalogue;
3. the public catalogue contains a commercially meaningful clothing and footwear range;
4. the sale location and public contact route are traceable;
5. observed catalogue prices are preserved as retail catalogue prices only, not acquisition prices or lot bids.

Only the existence and active commercial relevance of the opportunity are confirmed. Acquisition terms remain unknown.

## 3. Confirmed evidence

### 3.1 Active bankruptcy sale

Norsk Avvikling publicly shows:

```text
STATUS: AKTIV
AXL Sport Og Fritid Kolvereid
KONKURSSALG PÅGÅR
```

Public evidence:

```text
https://norskavvikling.no/
```

This verifies that the liquidation operator continues to present the AXL sale as active on the observation date.

### 3.2 Company and bankruptcy estate identity

Brønnøysundregistrene identifies:

```text
AXL SPORT OG FRITID KOLVEREID AS
Organisation number: 934 309 715
Status: Konkurs from 10 March 2026
Address: Sentrumsgata 2, 7970 Kolvereid
Bankruptcy estate: 937 325 746
Industry: retail sale of sporting equipment
```

The registered company purpose explicitly includes equipment and clothing for outdoor activities.

Public evidence:

```text
https://virksomhet.brreg.no/nb/oppslag/enheter/934309715
https://virksomhet.brreg.no/oppslag/enheter/937325746
```

### 3.3 Commercially meaningful clothing catalogue

The public AXL store currently exposes a dedicated clothing category with:

```text
161 catalogue results
```

Observed categories include:

- children;
- belts;
- women;
- gloves and mittens;
- men;
- headwear;
- junior;
- mid-layers;
- socks;
- underwear;
- unisex;
- outerwear.

Observed product examples include:

- Aclima HotWool Crewneck Unisex;
- Aclima WoolTerry Longs Mann;
- Deerhunter Excape Winter Jakke;
- Deerhunter Excape Winter Trousers;
- Didriksons Annema WNS Full Zip;
- Lundhags jackets, trousers, shirts, and headwear.

Public evidence:

```text
https://axlsportogfritid.no/produktkategori/klaer/
```

The full public shop exposes:

```text
388 catalogue results
```

and includes clothing, footwear, outdoor, hunting, fishing, and dog-related merchandise.

Public evidence:

```text
https://axlsportogfritid.no/butikk/
https://axlsportogfritid.no/
```

These are catalogue-entry counts, not verified physical-unit quantities.

### 3.4 Footwear evidence

The same public store exposes footwear and boot categories, including products such as Muckboot, Alfa, Skechers, Treksta, Nokian, and other outdoor footwear.

Footwear may be included in the later Opportunity Dossier as an adjacent saleable inventory class, but it must remain separated from clothing in quantity, market comparison, and resale assumptions.

## 4. Evidence labels

The following meaning must remain explicit:

```text
catalogue_price_nok
```

means the current public retail price displayed on the AXL store.

It does not mean:

```text
acquisition_price_nok
current_bid_nok
lot_price_nok
liquidation_price_nok
maximum_safe_bid_nok
```

The displayed result counts are catalogue entries. They do not prove SKU quantity, unit quantity, condition, ownership, or availability of every item.

## 5. Remaining unknowns

The following evidence is still required before financial analysis or a purchase review:

- exact inventory remaining now;
- physical unit quantity and SKU distribution;
- sizes, colours, brands, and condition by unit;
- which catalogue entries are actually part of the bankruptcy sale;
- whether the sale is retail, one lot, several lots, or negotiated sale;
- acquisition price or bid structure;
- VAT treatment;
- buyer premium or other fees;
- payment deadline and payment method;
- inspection opportunity;
- pickup window and access constraints;
- packing, loading, pallets, and transport requirements;
- third-party ownership, reservations, returns, or excluded goods.

These unknowns do not invalidate the opportunity. They block valuation and decision intelligence until documented.

## 6. Qualification-gate evaluation

| Gate | Result | Evidence |
|---|---|---|
| Sale remains active | PASS | Norsk Avvikling marks the bankruptcy sale active |
| Clothing inventory included | PASS | Dedicated public clothing catalogue with 161 entries |
| Commercially meaningful scope | PASS | Multi-category, multi-brand catalogue rather than one isolated item |
| Sale route confirmed | PASS_WITH_UNKNOWN_TERMS | Liquidation operator confirms bankruptcy sale in progress; exact transaction format remains unknown |
| Public traceability | PASS | Liquidation, company-register, store, category, and contact pages preserved |
| Values correctly labelled | PASS | Retail catalogue prices are not treated as acquisition prices |
| Ended or withdrawn inventory excluded | MANUAL_VERIFICATION_REQUIRED | Exact live physical availability must be confirmed during dossier evidence intake |

## 7. Canonical decision

The previous state:

```text
ACTIVE_CLOTHING_INVENTORY_LEAD_FOUND
EVIDENCE_REQUIRED
NO_DECISION
```

is now advanced to:

```text
CONFIRMED_ACTIVE_CLOTHING_INVENTORY_OPPORTUNITY
OPPORTUNITY_DOSSIER_ALLOWED
NO_DECISION
```

This is not:

```text
BUY_REVIEW
WATCH
REJECT
```

No investment decision is permitted until verified acquisition terms, quantities, costs, and market comparables exist.

## 8. Next task only

Exactly one task may follow:

```text
AXL_CLOTHING_INVENTORY_OPPORTUNITY_DOSSIER
```

The dossier task must:

1. preserve all confirmed source facts;
2. record all remaining unknowns explicitly;
3. separate clothing, footwear, and non-clothing inventory;
4. request or ingest human-verified stock and sale-route evidence;
5. avoid invented quantities, costs, market values, or profit;
6. stop at `EVIDENCE_REQUIRED` when acquisition evidence remains incomplete.

Market analysis, financial integration, scoring, and BUY_REVIEW/WATCH/REJECT remain later stages.

## 9. Out of scope

This verification does not approve:

- adding a new domain or source-adapter project;
- returning to Auksjonen parser refinement;
- modifying any workflow, code, classifier, test, fixture, state, cache, report, or financial formula;
- contacting AXL, Norsk Avvikling, the bankruptcy administrator, or any seller automatically;
- treating catalogue prices as liquidation acquisition prices;
- automatic purchase, bid, contact, reservation, payment, or financial decision.

## 10. Safety invariants

Preserve:

```text
automatic_purchase_decision: false
automatic_bid: false
automatic_contact: false
automatic_payment: false
```

`BUY_REVIEW` remains human-review-only.

## 11. Definition of done

This evidence-verification task is complete only when:

1. this document is the only changed file;
2. current public sale status is preserved;
3. clothing inventory evidence is commercially meaningful and traceable;
4. catalogue counts and retail prices are labelled accurately;
5. unknown physical quantities and acquisition terms remain unknown;
6. the canonical result is `CONFIRMED_ACTIVE_CLOTHING_INVENTORY_OPPORTUNITY` with `NO_DECISION`;
7. exactly one Opportunity Dossier task is identified;
8. no production or workflow behavior changes;
9. all repository checks pass.
