# Commercial Foothold Learning Loop V0

**Status:** MANUAL / HUMAN-LED / NO RUNTIME

## Purpose

This is a deliberately small commercial-learning loop used after Search Engine V1 discovers a real opportunity.

It does **not** change search, ranking, verification, Exact-Lot qualification, or automated decision logic.

The purpose is to learn, case by case, where a realistic market foothold exists before building any larger commercial system.

Core sequence:

```text
Find Deal
→ Identify Exit Routes
→ Identify Downstream Buyers
→ Estimate Absorbable Quantity
→ Gather Price Evidence
→ Measure Friction
→ CONTINUE / NEED_EVIDENCE / STOP
→ Record Commercial Lesson
→ Update Foothold Hypothesis
```

## Non-goals

V0 must not:

- create a new search runtime;
- change Search Engine V1;
- auto-score deals into BUY / REJECT;
- invent exit prices;
- treat a shop as a buyer without evidence;
- treat an asking price as a completed transaction;
- assume one country is an exit market without a concrete buyer/channel;
- automate purchasing or contacting buyers;
- promote a foothold hypothesis to proven market fit without repeated evidence.

## One rule above all

A deal is not attractive because the entry price is low.

A deal becomes commercially interesting only when we can explain a plausible path from stock to cash.

```text
ENTRY PRICE < REALISTIC EXIT VALUE
```

is necessary but not sufficient.

We also need enough demand, acceptable friction, and a credible time-to-clear.

## Case workflow

Every opportunity that reaches commercial study is passed through the same nine steps.

### 1. Opportunity facts

Record only what is known:

- product category;
- subcategory;
- quantity;
- location;
- seller / channel;
- condition;
- brands or generic;
- model mix;
- size distribution;
- packaging;
- asking / auction price;
- VAT basis;
- buyer premium / fees;
- transport constraints;
- inventory-list quality;
- source evidence.

Unknown stays `UNKNOWN`.

### 2. Exit-route candidates

List every plausible route separately:

- `DIRECT_BULK_BUYER`
- `B2B_LOTS`
- `DOWNSTREAM_MICRO_LOTS`
- `OUTLET_RETAILER`
- `ONLINE_RESELLER`
- `MARKET_TRADER`
- `EXPORT_RESELLER`
- `SPECIALIST_BUYER`
- `AUCTION_RESALE`
- `OTHER_EVIDENCED_ROUTE`

Do not merge routes with different economics.

### 3. Buyer evidence

For each buyer or channel, record:

- buyer name;
- country;
- buyer type;
- exact product fit;
- brand / generic fit;
- condition fit;
- typical or stated quantity;
- geography / pickup limits;
- logistics model;
- evidence source;
- evidence date.

Evidence strength:

```text
E0 — assumption only
E1 — buyer claim
E2 — quantified buyer / stated conditions
E3 — operational evidence
E4 — published transaction evidence
E5 — our own quote / transaction evidence
```

Only E1+ counts as a real buyer candidate.

### 4. Absorbable quantity

Estimate how much of the opportunity each route could plausibly absorb.

Do not ask only:

> Can somebody buy this lot?

Also ask:

> Can several smaller buyers absorb the lot together?

Record:

```text
route
buyer_count
min_qty_per_buyer
max_or_typical_qty_per_buyer
plausible_total_absorption
confidence
```

### 5. Price evidence

Keep price evidence types separate:

```text
DIRECT_BUYER_OFFER
COMPLETED_TRANSACTION
COMPLETED_AUCTION_HAMMER
POST_AUCTION_NEGOTIATED_PRICE
SOLD_LISTING_AT_ASK
ACTIVE_B2B_ASK
ACTIVE_RETAIL_ASK
NO_SALE_PRICE
UNKNOWN
```

Never convert an active asking price into a market-clearing price.

### 6. Friction

Record the factors that can destroy an otherwise good margin:

- VAT cash requirement;
- buyer premium;
- transport;
- export / customs;
- pickup-only restriction;
- storage;
- sorting;
- repacking;
- authenticity proof;
- weak packing list;
- missing size curve;
- seasonality;
- model concentration;
- slow sizes;
- territory restrictions;
- capital locked during resale;
- unsold-tail risk.

### 7. Foothold hypothesis

For every case, ask one strategic question:

> Did this opportunity reveal a buyer segment we could serve repeatedly with smaller, better-shaped lots?

Examples:

- Norwegian small contractors buying safety footwear in 10–40 pair lots;
- Nordic online resellers buying branded footwear in 20–60 pair lots;
- independent outlets buying 50–150 mixed fashion pieces;
- sewing / upholstery businesses buying fabric rolls or 20–100 metre lots.

Foothold state is descriptive, not a score:

```text
NONE
WEAK
EMERGING
REPEATED
PROVEN
```

Definitions:

- `NONE` — no repeatable buyer segment visible.
- `WEAK` — one plausible buyer/channel, insufficient evidence.
- `EMERGING` — multiple independent signals point to the same buyer segment.
- `REPEATED` — the same buyer segment appears across multiple real opportunities.
- `PROVEN` — our own quote, reservation, repeat inquiry, or transaction confirms the segment.

### 8. Human commercial decision

Only these states are allowed during learning:

```text
CONTINUE
NEED_EVIDENCE
STOP
```

No automated BUY decision exists in V0.

`CONTINUE` means the case is producing useful commercial evidence.

`NEED_EVIDENCE` means one or more missing facts could materially change the conclusion.

`STOP` means the case no longer deserves research effort, and the reason must be recorded.

### 9. Commercial lesson

Every case ends with a short learning record:

```text
what attracted attention
what we investigated
what changed our view
why we continued or stopped
what was learned about buyers
what was learned about price
what was learned about friction
whether a foothold signal strengthened or weakened
next unresolved commercial question
```

## What V0 is trying to discover

The goal is not to maximize the number of deals studied.

The goal is to find a repeatable statement of the form:

```text
WE CAN SOURCE:
  product X
  in quantity Y
  at condition Z

AND REPEATEDLY SERVE:
  buyer segment A
  in lot size B
  at an evidenced price corridor C
  with acceptable friction D
  and acceptable time-to-clear E
```

When the same statement survives several independent real cases, we have found a candidate foothold.

## Current working foothold hypotheses

These are hypotheses only and may be rejected by future cases.

### H1 — Nordic Workwear / Safety Footwear Micro-Lots

Potential buyer segment:

- small contractors;
- workshops;
- transport / cleaning / service companies;
- independent workwear resellers;
- specialist online sellers.

Potential lot shape:

- roughly 10–200 units depending on buyer;
- new stock preferred;
- useful size distribution required;
- product standards and brand matter.

Current state: `EMERGING`

Reason: repeated external evidence shows real workwear/safety-footwear liquidation and resale activity, but we do not yet have our own downstream buyer quotes.

### H2 — Nordic Branded Fashion / Footwear Micro-Lots

Potential buyer segment:

- online resellers;
- small outlets;
- market traders;
- independent shops.

Potential lot shape:

- roughly 20–150 units;
- new/original stock;
- strong size curve;
- clear authenticity and inventory data.

Current state: `WEAK`

### H3 — Small Commercial Fabric Lots

Potential buyer segment:

- tailors;
- upholsterers;
- curtain makers;
- sewing businesses;
- specialist textile resellers.

Potential lot shape:

- rolls or commercial remnants;
- composition, width, GSM and usable length known;
- sold by metre / roll rather than only by kg.

Current state: `WEAK`

## V0 maturity rule

Do not build a larger commercial engine from this loop until at least one foothold reaches `REPEATED` and preferably `PROVEN` through our own market interaction.

Until then, this remains a manual learning protocol.
