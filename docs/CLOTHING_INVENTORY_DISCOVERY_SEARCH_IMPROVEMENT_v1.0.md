# Clothing Inventory Discovery Search Improvement v1.0

**Task:** `CLOTHING_INVENTORY_DISCOVERY_SEARCH_IMPROVEMENT`  
**Domain:** `CLOTHING_INVENTORY` only  
**Implementation status:** Implemented in this draft PR  
**Analysis Engine changes:** None  
**Automatic commercial actions:** Prohibited

## Purpose

Improve the Discovery Engine so it can discover and explain real Clothing Inventory opportunities without requiring a known opportunity to be entered manually.

The task is limited to:

```text
structured search
  -> discovery qualification
  -> multi-source merging
  -> bounded public-page verification
  -> discovery-only ranking
  -> top-five operator artifacts
```

It does not calculate ROI, expected profit, maximum bid, or an investment decision.

## Prior task status

Draft PR #309 is intentionally deferred. It remains separate from this task and must not be merged into this branch.

This task does not modify confirmed-dossier intake, Opportunity Dossier construction, market comparables, acquisition costs, scoring, decision intelligence, or the V2.8–V3.7 Analysis Engine.

## Implemented search matrix

The search matrix contains exactly sixteen structured queries:

- six sale-intent queries;
- six commercial-event lead queries;
- four specialized large-inventory queries.

Each query carries:

```json
{
  "query_id": "sale-05",
  "scenario": "COMPANY_BANKRUPTCY",
  "intent": "SALE_INTENT",
  "asset_scope": "CLOTHING_INVENTORY",
  "query": "konkursbo klær auksjon Norge"
}
```

## Qualification states

The implementation uses exactly three discovery outcomes:

```text
CONFIRMED_SALE
STRONG_LEAD_REQUIRES_VERIFICATION
REJECTED_NOISE
```

A traceable clothing-business bankruptcy, closure, branch shutdown, or liquidation event is retained even when the search snippet does not contain an explicit sale word.

The implementation rejects:

- ordinary single-item listings;
- job advertisements;
- generic information pages without a commercial event;
- ordinary online shops without a liquidation or inventory signal;
- missing titles;
- non-HTTPS URLs.

## Duplicate merging

The implementation:

- removes tracking parameters;
- normalizes domains and paths;
- merges exact canonical URLs;
- compares distinctive company/title tokens;
- respects scenario and location compatibility;
- retains all source URLs, providers, and query IDs.

A news page, estate page, auction page, and sale listing may therefore become one opportunity with several evidence sources rather than four separate opportunities.

## Public-page verification

The manual runner can optionally read the public HTTPS pages of the highest-ranked twenty candidates.

It does not:

- log in;
- bypass access controls;
- contact a seller;
- submit a form;
- make a bid, reservation, purchase, or payment.

Visible page evidence may confirm:

- title;
- sale status;
- location;
- inventory type;
- price;
- quantity;
- active or ended status.

Verification failures remain explicit and do not fabricate evidence.

## Discovery score

The ranking is a discovery score, not an investment score:

| Element | Maximum points |
|---|---:|
| Commercial-event strength | 25 |
| Clothing-inventory clarity | 20 |
| Public sale signal | 20 |
| Source traceability | 15 |
| Freshness | 10 |
| Location and logistics | 5 |
| Public price or quantity | 5 |

Missing price or quantity reduces evidence completeness but does not delete a traceable opportunity.

The implementation does not use:

```text
ROI
expected profit
maximum bid
BUY_REVIEW
WATCH
investment REJECT
```

## Artifacts

The runner writes:

```text
artifacts/clothing-inventory-discovery/
├── search-run-report.json
├── all-discovered-candidates.json
├── discovery-top5.json
└── operator-summary.txt
```

Each top-five record contains:

- title;
- scenario;
- discovery state;
- discovery score and breakdown;
- location when known;
- all public source URLs;
- query IDs that found it;
- duplicate count;
- why it qualifies;
- confirmed information;
- missing information;
- next verification step.

Ended listings remain historical evidence and are excluded from the active top five.

## Validation

Focused tests prove:

1. an AXL-like bankruptcy lead is retained without an explicit sale word;
2. a confirmed inventory sale becomes `CONFIRMED_SALE`;
3. ordinary single garments are rejected;
4. jobs, generic information pages, and ordinary shops are rejected;
5. ended listings do not enter the active top five;
6. multiple URLs for one company are merged;
7. missing price and quantity do not delete the opportunity;
8. five unique traceable opportunities can be produced;
9. financial fields are absent from discovery ranking;
10. an empty search produces an honest no-opportunity result;
11. URL tracking parameters are removed;
12. optional public-page verification can promote a lead to a confirmed sale.

Local focused validation result:

```text
14 passed
```

## Manual execution

```bash
BRAVE_SEARCH_API_KEY=... python scripts/run_clothing_inventory_discovery_search.py \
  --verify-pages \
  --output-dir artifacts/clothing-inventory-discovery
```

The next step after this PR passes repository checks is one manual live run and human inspection of `discovery-top5.json`. The best traceable active result may then proceed to the existing Opportunity Dossier boundary.
