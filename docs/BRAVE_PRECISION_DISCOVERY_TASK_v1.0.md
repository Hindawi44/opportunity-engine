# Brave Precision Discovery v1.0

**Domain:** `CLOTHING_INVENTORY` only  
**Provider:** Brave Web Search API  
**Scope:** pre-verification search precision only

## Trigger

The post-verification hard gate is working correctly, but the latest structured
live run showed that retrieval quality remains inefficient:

```text
140 raw hits
120 unique public URLs
109 merged candidates
108 rejected results
0 confirmed sales
1 review candidate blocked after failed verification
```

The system is safe, but it spends most of its search and verification budget on
predictable noise: buyer-intent adverts, jobs, ordinary web shops, generic
content, stale listings, and weak snippets.

## Goal

Improve the evidence surface delivered by Brave before page verification,
without weakening the final eligibility gate or changing the Analysis Engine.

## Approved implementation

1. Add optional Brave `freshness` support.
2. Enable Brave search operators explicitly for the structured Clothing
   Inventory operation.
3. Enable Brave `extra_snippets` and merge at most five bounded alternative
   excerpts into the normalized result description.
4. Add a precision policy that preserves all sixteen approved query IDs,
   scenarios, intents, asset scope, and rotation groups.
5. Refine query text with exact phrases and negative operators that remove
   buyer intent, jobs, ordinary web shops, generic information, and stale sale
   language where appropriate.
6. Default the manual structured operation to Brave freshness `pm` (last 31
   days), while allowing the operator to select `pd`, `pw`, `pm`, or `py`.
7. Record the precision policy, freshness window, operator setting, and
   extra-snippet setting in the search-run artifact.

## Boundaries

This task must not:

- add a new opportunity domain;
- add a new source or browser collector;
- change the canonical sixteen-query scenario structure;
- change page verification, the early-opportunity gate, or the
  post-verification Top 5 hard gate;
- modify the Opportunity Dossier contract;
- modify market comparables, acquisition costs, financial formulas, scoring,
  or decision intelligence;
- contact sellers, bid, reserve, buy, or pay;
- add a schedule or automatic execution;
- run FINN Playwright collection.

## Acceptance

The task succeeds when:

1. the Brave adapter validates supported freshness presets and custom date
   ranges;
2. the structured operation sends `freshness`, `extra_snippets=true`, and
   `operators=true`;
3. normalized descriptions retain the main snippet plus deduplicated bounded
   extra snippets;
4. all sixteen query IDs and scenario contracts remain unchanged;
5. direct-sale queries exclude `ønskes kjøpt` and `kjøpes` where applicable;
6. event-lead queries remove jobs, ordinary shops, Wikipedia, and podcast
   noise without requiring a confirmed sale phrase;
7. all focused and repository-wide checks pass;
8. a post-merge live run produces the same four artifacts and remains allowed
   to return an empty Top 5.

## Deferred

The following are useful future steps but are intentionally outside v1.0:

- company-name follow-up queries generated from event leads;
- per-query yield history across multiple live runs;
- source re-ranking through Brave Goggles;
- automated query retirement or promotion.
