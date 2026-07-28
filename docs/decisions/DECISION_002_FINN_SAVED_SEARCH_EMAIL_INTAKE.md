# Decision 002 — FINN Saved-Search Email Intake

**Status:** APPROVED
**Date:** 2026-07-28

## Decision

Until written FINN automation permission or authorized API access exists, the
current Clothing Inventory experiment will use saved-search alert messages as
the FINN Discovery intake path.

```text
FINN alert email
  -> normalized lead
  -> REQUIRES_VERIFICATION
  -> manual advert review
  -> existing Opportunity Dossier and Analysis Engine
```

The authorized Playwright adapter remains code-ready but frozen for live use.

## Why

The project had implemented and tested a bounded Playwright adapter but had not
performed live FINN collection. FINN's terms require explicit consent for
systematic or regular automated use. Saved-search alerts can expose new advert
references without running a browser collector against FINN.

## Architectural impact

- This is a replaceable Discovery input adapter, not a new engine.
- The existing normalization, deduplication, Discovery gates, Opportunity
  Dossier, and Analysis Engine remain authoritative.
- No new opportunity domain, financial formula, or decision model is added.
- No FINN page is opened automatically.

## Evidence rule

Alert-message values are not page verification. Price, location, quantity, and
active status remain unverified until manually confirmed from the specific
advert. A price of `0` or `1 kr`, or request/contact wording, is never treated as
a verified acquisition cost.

## Acceptance condition

This decision is implemented when:

- genuine FINN alert formats are parsed without following links;
- stable advert IDs are deduplicated;
- Clothing Inventory leads enter Discovery as
  `STRONG_LEAD_REQUIRES_VERIFICATION`;
- `analysis_eligible` remains `false`;
- sanitized artifacts contain no raw mailbox content; and
- the first genuine Clothing Inventory alert can be reviewed through the
  existing end-to-end path.

## Supersession rule

Authorized FINN API access may replace this adapter later without changing the
Discovery-to-Analysis contract. Live Playwright collection remains blocked until
the explicit written-permission gate is satisfied.
