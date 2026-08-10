# OPENAI_FABRIC_PROCUREMENT_ADVISOR_V1

## Purpose

Expand the existing AI role without creating a second engine. The established
OpenAI hunt-case enrichment continues to analyze early liquidation and closure
signals. This advisor adds one bounded AI task for the existing
`FABRIC_DEADSTOCK_PROCUREMENT_FEED_V1` covering supplier candidates including
Prato, Como and Biella.

## Daily flow

```text
FABRIC PROCUREMENT WATCH
  -> OPENAI FABRIC PROCUREMENT ADVISOR
  -> UNIFIED MARKET INTELLIGENCE RIVER
```

The advisor runs after supplier discovery and before the unified river. Successful
assessments are attached as advisory metadata to their original fabric candidates,
so the existing river carries the AI context without a new database, lifecycle or
report.

## What the AI may do

For at most one top candidate per supplier, it may:

- summarize the material information already present in source evidence;
- assign a review priority (`HIGH`, `MEDIUM`, `LOW`);
- list source facts that support the review;
- identify missing commercial information such as exact composition, MOQ, price,
  available metres, VAT basis, lead time or shipping;
- prepare operator questions for later human verification;
- list Norway import/logistics checks that still need verification.

The advisor does not browse independently and does not convert missing information
into facts.

## Boundaries

- maximum 7 selected supplier candidates;
- maximum one selected candidate per supplier;
- exactly one OpenAI request when candidates and `OPENAI_API_KEY` are available;
- default model: `gpt-5.6-luna`;
- no automatic contact;
- no reservation;
- no purchase or payment;
- no promotion into opportunity Top 5;
- model output remains advisory and source evidence remains authoritative.

## Failure behavior

- missing API key -> `SKIPPED_NO_API_KEY`;
- zero fabric candidates -> `NO_ELIGIBLE_CANDIDATES`;
- API/schema failure -> `FAILED`;
- all states preserve the existing fabric watch and daily bulletin.

The advisor is intentionally non-blocking: a model failure must not hide supplier
results already collected by the deterministic fabric watch.

## Artifacts

The daily output directory gains:

```text
openai-fabric-procurement-advisor.json
openai-fabric-procurement-advisor.txt
```

The existing `domain-market-intelligence-brief.json` receives a compact
`fabric_ai_advisor` section. When the model succeeds, each matching row in
`fabric-procurement-watch.json` receives:

```text
metadata.openai_procurement_advisory
```

The already established unified river then carries that metadata into the
corresponding `FABRIC_PROCUREMENT_ITEM`.

## Operator rule

AI output answers: **what should the human verify next?** It does not answer:
**buy this automatically**.
