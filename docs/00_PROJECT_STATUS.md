# Opportunity Engine — Project Status

**Last updated:** 2026-08-12  
**Status:** ACTIVE / OPERATIONAL  
**Authoritative repository:** `Hindawi44/opportunity-engine`

## Source-of-truth rule

The repository and current `main` behavior are authoritative. Historical task documents and old PR status text must not override newer merged behavior.

For a new development session, read:

1. `docs/00_PROJECT_STATUS.md`
2. `README.md`
3. `config/market_completion_matrix.json`
4. `docs/UNIFIED_MARKET_INTELLIGENCE_RIVER_V1.md`
5. the documentation for the subsystem being changed

## Product goal

`opportunity-engine` is a conservative market-intelligence and decision-support system for clothing inventory, liquidation, auctions, insolvency/business-closure signals, and bounded fabric procurement.

It preserves the distinction between:

```text
source observation
→ market signal / procurement item / historical evidence
→ linked market case
→ verified opportunity when evidence allows
→ analysis
→ human decision
```

Signals are not automatically promoted into opportunities, and AI output is advisory only.

## Current market model

### Canonical opportunity markets

The validated clothing-inventory opportunity scope remains:

```text
NO — Norway
SE — Sweden
DE — Germany
```

The foundations of these three markets are complete. Individual source activation, a valid zero-result run, or a blocked source must not be confused with market-foundation status.

### Italy visibility

Italy is now explicitly visible in the daily market report as:

```text
IT — FABRIC_PROCUREMENT
```

This does **not** make Italy a fourth canonical liquidation/opportunity market and does not place fabric candidates into the opportunity Top 5.

Current daily visibility is therefore:

```text
NO | SE | DE | IT
```

with `IT` serving the fabric-procurement tributary.

## Current operating architecture

```text
NO / SE / DE opportunity discovery
        +
early market / closure / insolvency signals
        +
bridal and bounded B2B intelligence
        +
IT fabric procurement
        ↓
UNIFIED MARKET INTELLIGENCE RIVER
        ↓
linked intelligence items / market cases
        ↓
daily decision brief
        ↓
human review
```

The river preserves record kinds such as:

- `MARKET_SIGNAL`
- `BUSINESS_EVENT_SIGNAL`
- `B2B_STOCK_OFFER`
- `AUCTION_LOT`
- `BRIDAL_LIQUIDATION_SIGNAL`
- `FABRIC_PROCUREMENT_ITEM`
- `CANONICAL_OPPORTUNITY`
- `HISTORICAL_EVIDENCE`

## Fabric procurement state

The fabric lane is operational and is no longer a blocked future domain.

Current flow:

```text
FABRIC PROCUREMENT WATCH
→ OPENAI FABRIC PROCUREMENT ADVISOR
→ UNIFIED MARKET INTELLIGENCE RIVER
```

The advisor:

- selects at most one candidate per supplier, maximum 7;
- uses at most one OpenAI request when eligible candidates and an API key are available;
- assigns `HIGH`, `MEDIUM`, or `LOW` human review priority;
- summarizes only source-backed facts;
- identifies missing commercial facts such as price, MOQ, available quantity, composition, width, VAT basis, lead time, and Norway shipping/logistics;
- never contacts, reserves, buys, or pays automatically;
- never promotes fabric candidates into the canonical opportunity Top 5.

Recent merged implementation chain:

```text
PR #483 — OpenAI Fabric Procurement Advisor
PR #484 — fabric advisor output-budget fix
PR #486 — Italy explicitly visible in the daily report
```

Temporary validation PR #485 was intentionally closed without merge after the fixed advisor was proven against production candidates.

## Multi-market daily checkpoint

`MULTI_MARKET_DAILY_OPERATOR_CHECKPOINT` is implemented and merged; it is not the next unimplemented project phase.

The current workflow is scheduled daily and can also be dispatched manually. It is part of the production support surface and feeds the wider market-intelligence path.

Do not use old text saying that PR #413 is still awaiting merge or that the first post-merge checkpoint run is pending.

## Workflow state

The active `.github/workflows` directory currently contains five workflows:

```text
germany-clothing-inventory-live.yaml
multi-market-daily-operator-checkpoint.yaml
one-opportunity-commercial-analysis.yaml
sweden-clothing-inventory-live.yaml
tests.yml
```

Older workflow-audit documents are historical records. Their old workflow counts are not the current runtime inventory.

## Authoritative operational files

- `config/market_completion_matrix.json` — market foundation and source-state semantics.
- `config/source_expansion_plan.json` — source expansion/activation planning.
- `data/source_gap_matrix.json` — runtime source-status snapshot.
- `data/decision_intelligence.json` — decision intelligence.
- `data/action_queue.json` — operator actions.
- `data/follow_up_status.json` — follow-up state.
- `data/discovery_health.json` — discovery/source health.
- `data/source_funnel.json` — source coverage/funnel.
- `docs/UNIFIED_MARKET_INTELLIGENCE_RIVER_V1.md` — unified intelligence projection.
- `docs/OPENAI_FABRIC_PROCUREMENT_ADVISOR_V1.md` — bounded fabric AI behavior.

## Decision and safety invariants

- Missing facts remain unknown; do not invent price, quantity, company, location, VAT, customs, logistics, profit, or ROI.
- Source failure is not a zero-opportunity result.
- A valid zero-result run is not a failure.
- Historical or ended records are not active opportunities.
- AI recommendations remain advisory and evidence-backed.
- `BUY_REVIEW` requires human review and is not automatic buying.
- No automatic contact, bid, reservation, purchase, or payment.
- Do not run authorization-gated collectors without permission.

## Current development priority

Do **not** restart completed markets or add tooling merely because it is available.

The near-term priority is to strengthen the existing unified system:

```text
collect existing evidence
→ link related signals/items
→ improve one central daily decision view
→ verify commercial facts for the best candidates
→ human action
```

New tools, sources, or countries should be added only when they solve a demonstrated gap in this flow.
