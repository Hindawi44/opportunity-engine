# Menswear Norge AS — Pre-Market Validation v1.0

**Validation date:** 2026-07-30  
**Domain:** `CLOTHING_INVENTORY`  
**Pilot source:** Konkurs.app bounded clothing-bankruptcy lead adapter  
**Result:** `EARLY_LEAD_VALIDATED_FOR_ESTATE_MANAGER_FOLLOW_UP`

## Purpose

Validate the first-ranked pre-market lead without converting a bankruptcy record
into a confirmed inventory sale.

## Identity

| Field | Value | Evidence class |
|---|---|---|
| Debtor | MENSWEAR NORGE AS | `CONFIRMED_SOURCE_FACT` |
| Debtor organisation number | 986 425 284 | `CONFIRMED_SOURCE_FACT` |
| Bankruptcy estate | MENSWEAR NORGE AS KONKURSBO | `CONFIRMED_SOURCE_FACT` |
| Estate organisation number | 938 018 014 | `CONFIRMED_SOURCE_FACT` |
| Bankruptcy opened | 2026-07-01 | `CONFIRMED_SOURCE_FACT` |
| Municipality | Oslo | `CONFIRMED_SOURCE_FACT` |
| Industry | 46.420 — wholesale of clothing and footwear | `CONFIRMED_SOURCE_FACT` |

Official sources:

- https://virksomhet.brreg.no/nb/oppslag/enheter/986425284
- https://virksomhet.brreg.no/nb/oppslag/enheter/938018014

## Estate manager and professional contact route

The official estate page publishes the postal route:

```text
v/Adv. Henrik Schumann Sager
Karenslyst allé 16
0278 OSLO
```

Advokatfirmaet LEXIS publishes Henrik Schuman Sager as a partner working mainly
with insolvency and bankruptcy matters. The firm publishes a dedicated route for
bankruptcy-estate enquiries:

```text
konkurs@lexis.no
```

Sources:

- https://virksomhet.brreg.no/nb/oppslag/enheter/938018014
- https://www.lexis.no/ansatte/henrik-schuman-sager

The pilot records only the professional role and the firm-level bankruptcy
contact route. It does not send any message automatically.

## Inventory signal

The 2024 accounts presented by Proff show:

```text
Total assets: NOK 11,011,991
Inventory: NOK 5,264,000
Operating revenue: NOK 13,807,628
```

Source:

- https://www.proff.no/regnskap/menswear-norge-as/oslo/grossister/IGBAIMC10NS

This is strong historical evidence that the company recently operated with a
material clothing inventory balance. It does **not** prove how much inventory
remained on the bankruptcy date, whether the goods were pledged, whether they
were already sold, or whether the estate will offer them for sale.

Evidence classification:

```text
historical_inventory_balance = CONFIRMED_SECONDARY_ACCOUNTING_FACT
inventory_at_bankruptcy_date = UNKNOWN
inventory_available_for_sale = UNKNOWN
sale_method = UNKNOWN
sale_deadline = UNKNOWN
```

## Public-sale search

A bounded public search on 2026-07-30 found no traceable active sale listing tied
to the debtor or estate on the currently integrated auction paths.

```text
public_sale_found = false
inventory_sale_verified = false
listing_status = UNKNOWN
commercial_top5_eligible = false
analysis_eligible = false
```

This is not proof that no sale exists. Direct sale, private outreach, an
unindexed listing, or a future listing remain possible.

## Commercial interpretation

The lead is materially stronger than a normal industry-code-only bankruptcy
lead because it has all of the following:

- recent bankruptcy opening;
- clothing and footwear wholesale activity;
- historical inventory of approximately NOK 5.264 million;
- official estate-manager identification;
- a public professional contact route for bankruptcy-estate enquiries.

The correct next state is:

```text
PRE_MARKET_LEAD
  -> HISTORICAL_INVENTORY_EVIDENCE_FOUND
  -> ESTATE_MANAGER_IDENTIFIED
  -> OPERATOR_CONTACT_REVIEW_REQUIRED
```

It must not advance to `VERIFIED_ACTIVE_INVENTORY_SALE` until the estate confirms
that clothing stock exists and is available for acquisition, or a verifiable
public sale listing appears.

## Questions for human-approved contact

1. Does the estate currently control clothing, footwear, accessories, fixtures,
   or related stock belonging to MENSWEAR NORGE AS?
2. Is there an inventory list, quantity estimate, brand list, or photo package?
3. Is the stock offered as one lot or can it be divided?
4. Has a liquidator, auction company, or direct-sale channel been appointed?
5. What are the inspection, offer, payment, pickup, and removal deadlines?
6. Is the stated price or expected offer inclusive or exclusive of MVA?
7. Are any goods pledged, consigned, reserved by suppliers, damaged, returned, or
   otherwise excluded from the estate sale?

## Safety boundary

- No automatic email or contact.
- No bid, reservation, purchase, commitment, or payment.
- No assumption that the historical inventory remains available.
- No commercial Top 5 or Analysis Engine admission without current sale evidence.
