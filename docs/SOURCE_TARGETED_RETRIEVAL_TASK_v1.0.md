# Source-Targeted Clothing Retrieval v1.1

**Domain:** `CLOTHING_INVENTORY` only  
**Provider:** Brave Web Search API  
**Scope:** bounded retrieval validation before page verification

## Original problem

The structured search was safe but produced no usable opportunity:

```text
34 raw hits
30 unique public URLs
24 merged candidates
24 rejected results
0 confirmed sales
0 strong leads
```

Manual retrieval found one active liquidation sale and two useful bankruptcy-event references that the structured search did not preserve:

- AXL Sport Og Fritid Kolvereid;
- ANNA J AS / By Fiona, Namsos;
- TOMMELITEN BARNEKLÆR AS, Lillehammer.

## First live source-targeted result

The first bounded source-targeted run executed all eleven Brave requests but returned zero web hits before the URL gate:

```text
requests = 11/11
raw_hits = 0
accepted_hits = 0
rejected_hits = 0
reference_recall = 0/3
provider_errors = 0
```

Therefore the URL gate was not the cause. The retrieval request was over-constrained by a combination of:

- path-scoped `site:` expressions;
- exact phrases and many negative terms;
- `freshness=pm`, which filters by the page's indexed date rather than whether a sale remains active.

## Corrected implementation

1. Preserve all sixteen canonical Clothing Inventory query IDs, scenarios, intents, asset scope, and rotation groups.
2. Assign every query to exactly one approved host through a host-only Brave `site:` operator.
3. Keep the existing URL gate responsible for exact page-shape enforcement:
   - reject news, articles, blogs, contact pages, and generic homepages;
   - accept FINN only when the URL is one specific public item page;
   - accept Brønnøysund only when the URL is one specific organisation page;
   - preserve registry evidence as an event lead, never as a confirmed sale.
4. Use short source-specific queries instead of stacking exact phrases and broad exclusion lists.
5. Do not apply a Brave freshness filter by default. The manual operator may still select `pd`, `pw`, `pm`, or `py` for a diagnostic run.
6. Limit validation to eight discovery requests plus three bounded reference-recall requests.
7. Record per-query raw, accepted, rejected, and provider-error diagnostics.
8. Explicitly classify `raw_hits=0` as a retrieval/query-window failure, not a URL-gate rejection.

## Approved sources

Sale sources:

- `auksjonen.no`;
- `norskavvikling.no`;
- `stadssalg.no`;
- specific FINN recommerce item pages.

Event sources only:

- `forvalt.no` bankruptcy pages;
- `virksomhet.brreg.no` organisation pages;
- `konkurs.app`.

## Reference success gate

The bounded live validation passes only when:

- Brave returns at least one raw web result;
- AXL Sport Og Fritid Kolvereid is recovered;
- at least one of the two event references is also recovered;
- no reference request fails.

This is a retrieval test only. A recovered reference is not a purchase opportunity and cannot enter Analysis without the existing verification conjunction.

## Cost control

The default live validation executes:

```text
8 discovery queries
+ 3 reference queries
= 11 Brave requests
```

The workflow is manual only. Pull-request checks run offline regressions and do not use the Brave API key.

## Boundaries

This task must not:

- run Playwright;
- add a scheduled workflow;
- weaken page verification, the early-opportunity gate, or the post-verification Top 5 hard gate;
- treat a search snippet or bankruptcy registry page as a confirmed sale;
- change the Opportunity Dossier, Analysis Engine, financial formulas, scoring, or decision intelligence;
- contact sellers, bid, reserve, purchase, or pay.

## Deferred

Playwright for Auksjonen remains deferred until Brave demonstrates that it can retrieve eligible Auksjonen listing URLs. It must be implemented in a separate task and invoked only when ordinary public-page reading cannot extract the JavaScript-rendered listing evidence.
