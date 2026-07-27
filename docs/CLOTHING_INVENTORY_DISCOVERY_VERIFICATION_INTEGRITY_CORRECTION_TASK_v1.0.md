# Clothing Inventory Discovery Verification Integrity Correction Task v1.0

**Task:** `CLOTHING_INVENTORY_DISCOVERY_VERIFICATION_INTEGRITY_CORRECTION`  
**Domain:** `CLOTHING_INVENTORY` only  
**Task type:** Planning-only  
**Implementation status:** Not started  
**Automatic commercial action:** Prohibited

## 1. Purpose

Correct the verification and top-five integrity defects exposed by the first live structured Clothing Inventory Discovery run.

The live run proved that search coverage, duplicate merging, and artifact production work. It also proved that page-level verification can incorrectly combine unrelated text from category pages, ordinary stores, and source portals and then promote them as confirmed opportunities.

This task must make Discovery fail closed:

```text
search hit
  -> page-role identification
  -> opportunity-identity validation
  -> context-bounded evidence extraction
  -> conservative state transition
  -> top-five eligibility gate
```

No candidate may proceed to the Opportunity Dossier unless it represents one specific, traceable, currently available Clothing Inventory opportunity.

## 2. Evidence from the first live run

The first live run returned five high-ranked records, but none was dossier-ready:

1. an Auksjonen category page mixed the category filter, one lot quantity, and unrelated clothing terms;
2. Proffsport was an ordinary active store misclassified as a bankruptcy sale;
3. AltPåSalg was a resale/source channel, not one specific inventory opportunity;
4. the motorcycle-clothing auction was a potentially relevant listing but its current status and listing evidence were unresolved;
5. Konkursnett was a generic source portal and verification timed out.

The current report status `PASS` means execution completed without provider errors. It must not be interpreted as proof that all top-five candidates are valid opportunities.

## 3. Confirmed defects

### D1 — Whole-page evidence contamination

The verifier flattens up to a large page body into one text stream. Price, quantity, location, clothing terms, sale terms, and status may therefore come from different listings or navigation elements.

### D2 — Missing page-role classification

The system does not distinguish:

```text
ITEM_LISTING
CATEGORY_INDEX
SOURCE_CHANNEL
ORDINARY_STORE
ARTICLE_OR_INFO
UNRESOLVED_SOURCE
```

Category indexes and source portals can therefore enter the opportunity ranking.

### D3 — Weak sale confirmation

Generic terms such as `pris`, `auksjon`, or a zero-value shopping cart can create a sale signal without proving that one identified Clothing Inventory lot is offered for sale.

### D4 — Incorrect zero-price extraction

`0 NOK` can be extracted from an empty cart, navigation component, placeholder, or crossed-out display and then treated as public opportunity price evidence.

### D5 — Query-scenario leakage

A search query scenario can survive when the target page does not contain evidence supporting that scenario. An ordinary store found by a bankruptcy query may therefore remain labelled `COMPANY_BANKRUPTCY`.

### D6 — Unsafe verification promotion

A verified page can promote a candidate to `CONFIRMED_SALE` without proving:

- one stable opportunity identity;
- an item/listing page role;
- matching clothing-inventory evidence;
- matching sale evidence;
- current active status.

### D7 — Weak top-five eligibility

The top-five selection accepts non-rejected records whose listing status remains `UNKNOWN`, including source portals and unresolved pages.

### D8 — Operational status ambiguity

`PASS` currently reports execution health only. The artifact does not separately state whether opportunity-quality validation passed.

## 4. Required correction design

### 4.1 Add a page-role decision

Every verified source must receive exactly one role:

```text
ITEM_LISTING
CATEGORY_INDEX
SOURCE_CHANNEL
ORDINARY_STORE
ARTICLE_OR_INFO
UNRESOLVED_SOURCE
```

#### ITEM_LISTING

A page representing one identifiable commercial lot or one identifiable business inventory sale.

Required indicators:

- listing-specific title or stable listing identifier;
- bounded sale object or lot description;
- clothing/inventory relevance within the same evidence scope;
- traceable public HTTPS URL.

#### CATEGORY_INDEX

A page listing multiple lots, filters, search results, or categories. It may be retained as a source-discovery surface, but not as an opportunity.

#### SOURCE_CHANNEL

A portal, buyer, liquidator, auction homepage, resale company, or bankruptcy index without one specific candidate sale.

#### ORDINARY_STORE

An active retail or wholesale store without a verified liquidation, closure, bankruptcy-estate sale, or whole-inventory sale.

#### ARTICLE_OR_INFO

A news article, guide, information page, or announcement that does not itself establish one currently available sale.

#### UNRESOLVED_SOURCE

A page whose identity or content cannot be verified because of timeout, redirect shell, client-side rendering shell, access failure, or insufficient public content.

### 4.2 Add opportunity-identity validation

A candidate must have a stable opportunity identity before confirmation. At least one must exist:

- listing ID in the URL or page metadata;
- specific company/store name plus a specific inventory-sale event;
- specific lot title that is materially narrower than a category title;
- canonical item URL distinct from a category or homepage URL.

Generic titles such as the following are insufficient:

```text
Torget / Vareparti-og-konkursbo
Auksjon - konkursbo, partivare, restlager
Forside
Om oss
```

### 4.3 Bound evidence to one opportunity context

Price, quantity, location, status, inventory type, and sale evidence must be extracted from the same listing context.

Acceptable contexts, in priority order:

1. structured data for one product/listing object;
2. listing-specific metadata;
3. a single HTML container representing one lot;
4. a listing-specific page body when the page role is already proven as `ITEM_LISTING`.

The implementation must not combine:

- quantity from one lot;
- location from a filter;
- inventory type from navigation;
- price from another product;
- status from a generic page banner.

If a bounded context cannot be established, extracted commercial fields remain `null` and the candidate cannot become `CONFIRMED_SALE`.

### 4.4 Rebuild sale confirmation as an evidence conjunction

`CONFIRMED_SALE` requires all of the following:

```text
page_role == ITEM_LISTING
AND stable opportunity identity exists
AND clothing/inventory evidence exists in the bounded context
AND sale/auction/transfer evidence exists in the bounded context
AND listing_status == ACTIVE
AND verification succeeded
```

A generic sale word by itself is insufficient.

### 4.5 Enforce conservative state transitions

Allowed post-verification transitions:

| Verified outcome | Resulting state |
|---|---|
| Specific active item listing with complete confirmation conjunction | `CONFIRMED_SALE` |
| Specific item listing with unresolved active status or incomplete sale proof | `STRONG_LEAD_REQUIRES_VERIFICATION` |
| Traceable bankruptcy/closure event without verified listing sale | `STRONG_LEAD_REQUIRES_VERIFICATION` |
| Category index | `REJECTED_NOISE` for opportunity ranking, retained as source metadata |
| Source channel | `REJECTED_NOISE` for opportunity ranking, retained as source metadata |
| Ordinary store | `REJECTED_NOISE` |
| Article/info without a current sale | `REJECTED_NOISE` |
| Verification timeout or shell page | no promotion; retain prior state only when search evidence independently supports a specific lead, otherwise `REJECTED_NOISE` |
| Ended listing | historical evidence only; excluded from active top five |

Verification may confirm or downgrade. It must never promote a generic page solely because page-wide keywords are present.

### 4.6 Correct price handling

The price extractor must:

- reject `0 NOK` and equivalent zero placeholders as a confirmed acquisition price;
- distinguish shopping-cart totals and navigation totals from listing prices;
- preserve bid price separately from asking/fixed price when identifiable;
- return `null` when price context is ambiguous;
- never increase opportunity confidence merely because a zero or unrelated price was found.

No financial calculations are added.

### 4.7 Prevent query-scenario leakage

The query scenario is a discovery hint, not verified evidence.

After public verification:

- a scenario may remain only if the page or independently traceable sources support it;
- an ordinary store must not remain `COMPANY_BANKRUPTCY` because it was found by a bankruptcy query;
- when the verified page supports a different event, the scenario may be corrected;
- when no event is verified, the scenario must become `UNVERIFIED_EVENT` or the candidate must remain a lead without confirmed event scoring.

### 4.8 Add top-five eligibility gates

A candidate is eligible for `discovery-top5.json` only when:

```text
page_role == ITEM_LISTING
AND opportunity identity is stable
AND listing_status in {ACTIVE, UNKNOWN}
AND state in {CONFIRMED_SALE, STRONG_LEAD_REQUIRES_VERIFICATION}
AND source traceability is valid
```

Additional rules:

- `UNKNOWN` status is allowed only for a specific listing and only as `STRONG_LEAD_REQUIRES_VERIFICATION`;
- `CATEGORY_INDEX`, `SOURCE_CHANNEL`, `ORDINARY_STORE`, `ARTICLE_OR_INFO`, and `UNRESOLVED_SOURCE` are never top-five opportunities;
- top five means **up to five** valid opportunities;
- the system must output fewer than five rather than fill the list with weak or generic records;
- zero valid opportunities must produce an honest no-opportunity result.

### 4.9 Split execution health from opportunity-quality status

`search-run-report.json` must include separate fields:

```json
{
  "execution_status": "PASS | PARTIAL | FAIL",
  "opportunity_quality_status": "PASS | REVIEW_REQUIRED | NO_VALID_OPPORTUNITIES",
  "top5_eligible_count": 0,
  "generic_pages_excluded": 0,
  "verification_failures": 0,
  "false_positive_guard_triggered": 0
}
```

The existing top-level `status` may remain temporarily for compatibility, but documentation must state that it reflects execution health only.

## 5. Mandatory regression fixtures

The implementation tests must include deterministic fixtures representing the five live-run cases.

### F1 — Auksjonen category page

Expected:

```text
page_role = CATEGORY_INDEX
not CONFIRMED_SALE
not eligible for top five
quantity/location/inventory must not be cross-combined
```

### F2 — Proffsport ordinary store

Expected:

```text
page_role = ORDINARY_STORE
state = REJECTED_NOISE
scenario != confirmed COMPANY_BANKRUPTCY
price_nok = null
not eligible for top five
```

### F3 — AltPåSalg source channel

Expected:

```text
page_role = SOURCE_CHANNEL
retained only as a discovery source
not treated as one opportunity
not eligible for top five
```

### F4 — Specific motorcycle-clothing auction with unresolved page content

Expected:

```text
specific listing identity retained
state = STRONG_LEAD_REQUIRES_VERIFICATION
listing_status = UNKNOWN unless independently proven
not promoted to CONFIRMED_SALE
eligible only if item-listing identity is proven
```

### F5 — Konkursnett portal timeout

Expected:

```text
page_role = UNRESOLVED_SOURCE or SOURCE_CHANNEL
verified = false
not promoted
not eligible for top five
```

## 6. Additional mandatory tests

The implementation must prove:

1. a valid active clothing-inventory item listing becomes `CONFIRMED_SALE`;
2. a category page containing many valid auction terms is excluded;
3. location from a filter is not assigned to a lot;
4. quantity from one listing is not assigned to another;
5. a cart total of `0,00` does not become opportunity price;
6. a generic `pris` token does not confirm a sale;
7. an ordinary store returned by a bankruptcy query is rejected;
8. an active source channel is not an active opportunity;
9. a timeout cannot upgrade a candidate;
10. an ended item listing is historical only;
11. an unknown-status specific listing remains a lead, not a confirmed sale;
12. fewer than five valid opportunities produces fewer than five outputs;
13. no valid opportunities produces an honest empty top-five file;
14. Discovery scoring uses no ROI, expected profit, maximum bid, or investment decision;
15. no seller contact, bid, reservation, purchase, payment, or automatic notification occurs.

## 7. Approved implementation scope

Exactly one implementation PR may follow this planning PR.

It may modify only:

```text
src/opportunity_engine/discovery/clothing_inventory_search.py
tests/test_clothing_inventory_discovery_search.py
tests/fixtures/clothing_inventory_discovery_verification/
docs/00_PROJECT_STATUS.md
```

A fixture directory may contain only deterministic public-page representations required by the tests.

No workflow change is required because the existing manual structured Discovery operation already runs the target module and uploads the required artifacts.

## 8. Explicitly prohibited changes

The subsequent implementation must not:

- modify query count or add another opportunity domain;
- modify Brave credentials or provider behavior;
- modify the Opportunity Dossier contract;
- modify confirmed-dossier intake;
- modify market-comparable or acquisition-cost logic;
- modify V2.8–V3.7 formulas;
- modify investment scoring or decision intelligence;
- add schedules or automatic runs;
- contact sellers;
- submit forms;
- bid, reserve, purchase, or pay;
- fabricate active status, price, quantity, company, or location;
- hard-code acceptance around Auksjonen, Proffsport, AltPåSalg, or Konkursnett domains.

The five named cases are regression examples, not production allowlists or denylists.

## 9. Implementation sequence

The correction implementation must proceed in this order:

1. add page-role and opportunity-identity models;
2. add deterministic page-role tests;
3. implement context-bounded evidence extraction;
4. implement strict confirmation conjunction;
5. implement zero-price and generic-price rejection;
6. prevent query-scenario leakage;
7. add top-five eligibility gate;
8. split execution health from opportunity-quality status;
9. run all focused tests;
10. run complete repository checks;
11. merge only after all checks pass;
12. manually rerun `structured_clothing_discovery`;
13. inspect all candidates and `discovery-top5.json`;
14. pass one candidate to the Opportunity Dossier only when the new gate proves it is a specific traceable active opportunity.

## 10. Definition of success

The correction succeeds only when:

- the five live-run false-positive cases produce the required conservative outcomes;
- category pages and source channels cannot appear as opportunities;
- ordinary stores cannot inherit bankruptcy confirmation from search queries;
- commercial fields come from one bounded listing context;
- `CONFIRMED_SALE` requires a specific active item listing;
- `UNKNOWN` status never becomes a confirmed sale;
- top five contains only specific opportunities and may contain fewer than five;
- execution success is reported separately from opportunity-quality success;
- a new live run produces either valid traceable opportunities or an honest empty result;
- no Analysis Engine or commercial-action boundary is crossed.

## 11. Current decision

No result from the first live `discovery-top5.json` is approved for Opportunity Dossier intake.

The only approved next task after this planning PR is:

```text
CLOTHING_INVENTORY_DISCOVERY_VERIFICATION_INTEGRITY_CORRECTION_IMPLEMENTATION
```
