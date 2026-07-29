# Source-Targeted Clothing Retrieval v1.0

**Domain:** `CLOTHING_INVENTORY` only  
**Provider:** Brave Web Search API  
**Scope:** bounded retrieval validation before page verification

## Problem

The latest structured search was safe but produced no usable opportunity:

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

The current hard gates are not the problem. The retrieval surface is still too broad and spends requests on editorials, ordinary shops, category pages, and generic source channels.

## Approved implementation

1. Preserve all sixteen canonical Clothing Inventory query IDs, scenarios, intents, asset scope, and rotation groups.
2. Assign every query to exactly one approved sale source or event registry through a Brave `site:` operator.
3. Use these sale sources:
   - `auksjonen.no`;
   - `norskavvikling.no`;
   - `stadssalg.no`;
   - specific FINN recommerce item pages.
4. Use these event sources only as unverified event leads:
   - `forvalt.no/Konkurs`;
   - `virksomhet.brreg.no`;
   - `konkurs.app`.
5. Apply a URL gate before the existing classifier:
   - reject news, articles, blogs, contact pages, and generic homepages;
   - accept FINN only when the URL is one specific public item page;
   - accept Brønnøysund only when the URL is one specific organisation page;
   - preserve registry evidence as an event lead, never as a confirmed sale.
6. Limit the first live validation to eight discovery requests plus three bounded reference-recall requests.
7. Keep Brave freshness at `pm` by default, with manual `pw`, `pm`, or `py` selection.
8. Record raw hits, accepted hits, pre-classification rejections, rejection reasons, accepted hosts, request use, and reference recall.

## Reference success gate

The bounded live validation passes only when:

- AXL Sport Og Fritid Kolvereid is recovered; and
- at least one of the two event references is also recovered; and
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
- contact sellers, bid, reserve, purchase, or pay;
- merge the previous FINN rescue Draft PR as proof of success.

## Deferred

Playwright for Auksjonen is deferred until Brave demonstrates that it can retrieve eligible Auksjonen listing URLs. It must be implemented in a separate task and invoked only when ordinary public-page reading cannot extract the JavaScript-rendered listing evidence.
