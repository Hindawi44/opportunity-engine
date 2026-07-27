# First Active Clothing Inventory Opportunity Task v1.0

**Task type:** Planning and evidence checkpoint  
**Domain:** `CLOTHING_INVENTORY`  
**Status:** `ACTIVE_LEAD_FOUND_EVIDENCE_REQUIRED`  
**Automatic commercial action:** Prohibited

## 1. Purpose

Return the project to the approved product path:

```text
Discover one real active Clothing Inventory opportunity
  -> verify the opportunity itself
  -> Opportunity Dossier
  -> verified market comparables
  -> verified acquisition costs
  -> existing Analysis Engine
  -> BUY_REVIEW / WATCH / REJECT
  -> final investment report
```

This task does not approve a new domain, source-adapter project, workflow-cleanup wave, classifier expansion, or automatic purchase/contact action.

## 2. Discovery decision

The product begins from the commercial scenario, not from one website.

Approved scenarios remain:

- store closing;
- company bankruptcy;
- inventory liquidation;
- public auction;
- warehouse surplus;
- importer liquidation;
- manufacturer excess production;
- large lot sale;
- business-model change;
- branch closure.

A source is only an evidence channel.

## 3. First active lead discovered

```text
Candidate: AXL Sport og Fritid Kolvereid AS konkursbo
Scenario: company bankruptcy / active bankruptcy sale
Location: Sentrumsgata 2, 7970 Kolvereid, Trøndelag, Norway
Lead state: ACTIVE_SALE_LEAD
Commercial decision: NO_DECISION
```

### Public evidence observed on 2026-07-27

1. Norsk Avvikling lists:

```text
STATUS: AKTIV
AXL Sport Og Fritid Kolvereid
KONKURSSALG PÅGÅR
```

Source:

```text
https://norskavvikling.no/aktive-salg/
```

2. Brønnøysundregistrene identifies AXL Sport og Fritid Kolvereid AS as bankrupt from March 2026 and identifies the associated bankruptcy estate.

Sources:

```text
https://virksomhet.brreg.no/nb/oppslag/enheter/934309715
https://virksomhet.brreg.no/oppslag/enheter/937325746
```

3. Public company-purpose evidence describes retail activity including equipment and clothing for outdoor activities.

## 4. Honest classification

The lead is stronger than a bankruptcy notice because a public liquidation operator currently labels the bankruptcy sale as active.

However, the available public page does not yet prove:

- that clothing inventory remains available now;
- whether merchandise is sold as one lot, several lots, or retail items;
- quantity, brands, sizes, condition, or SKU distribution;
- current price, bid, reserve, VAT treatment, fees, or payment terms;
- pickup dates, access conditions, or transport requirements;
- whether fixtures or non-clothing equipment dominate the remaining stock.

Therefore the canonical result at this checkpoint is:

```text
ACTIVE_CLOTHING_INVENTORY_LEAD_FOUND
EVIDENCE_REQUIRED
NO_DECISION
```

It is not yet:

```text
ACTIVE_CANDIDATE_SELECTED
BUY_REVIEW
```

## 5. Qualification gate

The lead may become a confirmed Clothing Inventory opportunity only when human-verifiable evidence establishes all of the following:

1. the sale remains active;
2. clothing or apparel inventory is included;
3. the available stock is commercially meaningful rather than one irrelevant item;
4. the seller or liquidation operator confirms the sale route;
5. a public link or human contact route is preserved;
6. observed values are labeled by meaning and are not invented;
7. ended, withdrawn, or already-sold inventory is excluded.

If clothing inventory is not confirmed, the correct result is:

```text
LEAD_REJECTED_NOT_CONFIRMED_CLOTHING_INVENTORY
NO_DECISION
```

## 6. Next task only

Exactly one task may follow:

```text
AXL_ACTIVE_CLOTHING_INVENTORY_EVIDENCE_VERIFICATION
```

It must verify, without automatic contact or purchase:

- active sale status;
- whether clothing inventory is actually included;
- stock or lot scope;
- sale format;
- observed price or bid type when available;
- location and pickup constraints;
- public evidence links and observation times.

The verification may produce only one of:

```text
CONFIRMED_ACTIVE_CLOTHING_INVENTORY_OPPORTUNITY
EVIDENCE_REQUIRED
LEAD_REJECTED
```

Only `CONFIRMED_ACTIVE_CLOTHING_INVENTORY_OPPORTUNITY` may proceed to an Opportunity Dossier.

## 7. Out of scope

This task does not approve:

- adding a new domain;
- continuing Auksjonen parser refinements;
- changing classifiers or keyword dictionaries;
- modifying any workflow;
- changing production code, tests, fixtures, state, cache, reports, or financial formulas;
- treating a bankruptcy registration alone as a purchase opportunity;
- inventing quantity, market value, acquisition cost, or expected profit;
- automatic purchase, bid, contact, payment, reservation, or financial decision.

## 8. Safety invariants

Preserve:

```text
automatic_purchase_decision: false
automatic_bid: false
automatic_contact: false
automatic_payment: false
```

`BUY_REVIEW` remains a human-review state only.

## 9. Definition of done

This task-definition PR succeeds only when:

1. this document is the only changed file;
2. one real active commercial lead is named with public traceability;
3. confirmed facts and unknowns are separated;
4. no Opportunity Dossier or financial analysis is manufactured prematurely;
5. exactly one evidence-verification task is identified;
6. no workflow or production behavior is modified;
7. all repository checks pass.
