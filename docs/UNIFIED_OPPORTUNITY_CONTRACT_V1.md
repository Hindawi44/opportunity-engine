# Unified Opportunity Contract V1

## Purpose

`UnifiedOpportunityContractV1` is the stable, source-agnostic boundary between:

- discovery and source collectors;
- verification and evidence collection;
- commercial evaluation;
- operator workflow;
- dashboards and alerts;
- future market profiles and buyer matching.

This first version is additive. It does not replace `final_decision`, change Top 5
eligibility, add network requests, or invoke Analysis automatically.

## Status axes

The contract deliberately separates four independent concerns.

### `listing_status`

Describes the public listing itself:

- `UNKNOWN`
- `ACTIVE`
- `ENDED`
- `REMOVED`
- `SOLD`
- `UNAVAILABLE`

### `verification_status`

Describes evidence quality and completeness:

- `UNVERIFIED`
- `REQUIRES_VERIFICATION`
- `VERIFIED`
- `CONFLICTING_EVIDENCE`

### `commercial_status`

Describes commercial evaluation, not listing availability:

- `NOT_ANALYZED`
- `WATCH`
- `QUALIFIED`
- `DISQUALIFIED`

### `workflow_status`

Describes the human operating workflow:

- `NEW`
- `WATCHING`
- `CONTACTED`
- `NEGOTIATING`
- `PURCHASED`
- `LOST`
- `ARCHIVED`

## Required boundary

Every contract contains:

```json
{
  "schema_version": "unified-opportunity-contract-v1",
  "opportunity_id": "...",
  "market": "NO",
  "source": {},
  "identity": {},
  "listing_status": "ACTIVE",
  "verification_status": "REQUIRES_VERIFICATION",
  "commercial_status": "WATCH",
  "workflow_status": "NEW",
  "evidence": [],
  "cost_estimate": {},
  "risk": {},
  "final_decision": "NO_DECISION",
  "missing_information": [],
  "recommended_actions": [],
  "automatic_purchase_decision": false
}
```

Unknown values remain unknown. The contract must not invent quantity, price, fees,
VAT, transport, resale value, ROI, or a purchase decision.

## First compatibility adapter

`UnifiedOpportunityContractV1.from_checkpoint_outcome(...)` converts the existing
controlled Clothing Inventory checkpoint into the unified boundary.

The adapter:

- preserves the existing `opportunity_id`;
- preserves traceable source evidence;
- maps missing evidence to `REQUIRES_VERIFICATION` and `WATCH`;
- copies only existing verified-cost fields;
- keeps `final_decision=NO_DECISION` because the checkpoint is not the official
  decision engine;
- rejects any attempt to set `automatic_purchase_decision=true`.

## Non-goals for V1

This change does not add:

- Pydantic or another dependency;
- SQLite, SQLAlchemy, or migrations;
- FastAPI or a customer-facing API;
- new market sources;
- Sweden or Denmark profiles;
- user accounts or buyer matching;
- changes to scoring, ranking, alerts, or Top 5.

Those layers can use this contract only after the compatibility boundary is proven
against current outputs.
