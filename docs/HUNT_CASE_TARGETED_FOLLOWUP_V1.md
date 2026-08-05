# HUNT_CASE_TARGETED_FOLLOWUP_V1

## Product purpose

Turn the strongest OpenAI hunt-case suggestions into bounded public-web searches without rebuilding the existing engine.

The existing flow remains authoritative:

```text
Direct collectors + official registers + Brave radar
→ MarketSignalRecord persistence
→ daily domain bulletin
→ OpenAI hunt-case correlation
→ targeted Brave follow-up
→ human/source-page verification
```

The follow-up stage does not create an opportunity. It only produces evidence candidates that may justify opening a source page and verifying the company, seller, liquidator, sale channel, or inventory.

## Bounded execution

Default limits:

```text
HUNT_FOLLOWUP_MAX_CASES=2
HUNT_FOLLOWUP_MAX_QUERIES_PER_CASE=3
HUNT_FOLLOWUP_RESULTS_PER_QUERY=5
HUNT_FOLLOWUP_MAX_REQUESTS=6
```

Only hunt cases with successful deep analysis and at least one valid targeted query are eligible. Cases are ranked by the existing hunt-case priority score.

Each query must:

- be no longer than 320 characters;
- contain no URL scheme or control characters;
- be unique within the case;
- come from the OpenAI deep-analysis artifact.

## Search provider

The current `BRAVE_SEARCH_API_KEY` is reused. No new secret or provider is required.

Brave is configured for:

- the hunt case market (`NO`, `SE`, or `DE`);
- operator support for quoted names and `site:` queries;
- extra snippets;
- a one-year freshness window;
- at most two retries.

## Deterministic evidence classification

Every returned URL is normalized and tracking parameters are removed.

A result becomes `IDENTITY_AND_COMMERCIAL_SIGNAL` only when deterministic text matching finds:

1. an exact organisation number already present in the hunt case, or an exact normalized company name; and
2. at least one inventory or sale-channel term in the result title, URL, or Brave snippet.

This state is still only:

```text
EVIDENCE_CANDIDATE_REQUIRES_PAGE_VERIFICATION
```

A result without exact identity linkage remains `COMMERCIAL_SIGNAL_UNLINKED`. A URL already present in the source signals is marked `ALREADY_KNOWN_SOURCE` and is not counted as new evidence.

## Trust boundary

Targeted search results cannot:

- create or promote an opportunity;
- make a record Top 5 or analysis eligible;
- prove a company owns the inventory;
- prove an auction, liquidation, price, quantity, or condition;
- contact, bid, buy, reserve, or pay.

The exact source page must be opened and verified in a later bounded stage before any lifecycle promotion.

## Failure behavior

- Missing Brave key: `SKIPPED_NO_BRAVE_KEY`.
- No eligible hunt cases: `NO_ELIGIBLE_CASES`.
- No accepted links: `VALID_ZERO`.
- One or more query failures: `PARTIAL`, while successful queries remain available.
- All queries fail: `FAILED`.

A targeted-search failure does not fail the direct collectors, OpenAI hunt analysis, or daily market bulletin.

## Artifacts

```text
hunt-case-targeted-followup.json
hunt-case-targeted-followup.txt
domain-market-intelligence-brief.json
```

The domain bulletin receives a compact `targeted_followup_intelligence` section while preserving the existing single human action and all automatic-action prohibitions.
