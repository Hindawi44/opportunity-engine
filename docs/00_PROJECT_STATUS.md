# Opportunity Engine — Project Status

**Last updated:** 2026-08-12  
**Status:** ACTIVE / OPERATIONAL  
**Authoritative repository:** `Hindawi44/opportunity-engine`

## Source-of-truth rule

Current `main` behavior is authoritative. Historical task documents and old PR
status text must not override newer merged behavior.

For a new development session, read:

1. `docs/00_PROJECT_STATUS.md`
2. `README.md`
3. `config/market_completion_matrix.json`
4. `docs/UNIFIED_MARKET_INTELLIGENCE_RIVER_V1.md`
5. `docs/CENTRAL_INTELLIGENCE_ORCHESTRATOR_V1.md`
6. the documentation for the subsystem being changed

## Product goal

`opportunity-engine` is a conservative market-intelligence and decision-support
system for clothing inventory, liquidation, auctions, insolvency/business-closure
signals, and bounded fabric procurement.

The system preserves this distinction:

```text
source observation
→ market signal / procurement item / historical evidence
→ linked market case
→ verified opportunity when evidence allows
→ analysis / benchmark
→ central operator view
→ human decision
```

Signals are not automatically promoted into opportunities. AI output is advisory.

## Current market model

### Canonical opportunity markets

```text
NO — Norway
SE — Sweden
DE — Germany
```

These three clothing-inventory market foundations are complete. Individual source
activation, a valid zero-result run, or a blocked source must not be confused with
market-foundation status.

### Italy visibility

Italy is explicitly visible in the daily report as:

```text
IT — FABRIC_PROCUREMENT
```

Italy is not a fourth canonical liquidation/opportunity market and fabric
candidates do not enter the opportunity Top 5.

Current daily visibility:

```text
NO | SE | DE | IT
```

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
UNIFIED DECISION PRIORITY
        ↓
MARKET COMPARABLES BENCHMARK
        ↓
CENTRAL INTELLIGENCE ORCHESTRATOR
        ↓
one operator view / one human action
```

The river preserves independent record kinds such as:

- `MARKET_SIGNAL`
- `BUSINESS_EVENT_SIGNAL`
- `B2B_STOCK_OFFER`
- `AUCTION_LOT`
- `BRIDAL_LIQUIDATION_SIGNAL`
- `FABRIC_PROCUREMENT_ITEM`
- `CANONICAL_OPPORTUNITY`
- `HISTORICAL_EVIDENCE`

## Unified decision priority

The existing priority layer separates:

```text
ACTIONABLE_NOW
MARKET_WATCH
HISTORICAL_EVIDENCE
```

Actionability is evaluated before raw source-signal strength so a strong watch-only
insolvency signal does not outrank a current commercial item that can be reviewed
now.

## Central intelligence state

`CENTRAL_INTELLIGENCE_ORCHESTRATOR_V1` is the bounded final coordination layer.

It does not create another engine. It reads existing daily outputs and exposes:

- strongest current direct/B2B/auction commercial opportunity;
- strongest market-watch signal;
- strongest current fabric supplier candidate;
- market visibility and compact daily counts;
- exactly one recommended human action.

Decision precedence is:

```text
1. Current commercial opportunity / offer
2. Otherwise top fabric procurement candidate
3. Otherwise top market-watch signal
4. Otherwise continue monitoring
```

Outputs:

```text
central-intelligence-brief.json
central-intelligence-brief.txt
```

The compact central summary is also attached to
`domain-market-intelligence-brief.json`.

Reference:

```text
docs/CENTRAL_INTELLIGENCE_ORCHESTRATOR_V1.md
```

## Fabric procurement state

The fabric lane is operational.

```text
FABRIC PROCUREMENT WATCH
→ OPENAI FABRIC PROCUREMENT ADVISOR
→ UNIFIED MARKET INTELLIGENCE RIVER
```

The advisor:

- selects at most one candidate per supplier, maximum 7;
- uses at most one OpenAI request when eligible candidates and an API key exist;
- assigns `HIGH`, `MEDIUM`, or `LOW` human review priority;
- summarizes only source-backed facts;
- identifies missing commercial facts such as price, MOQ, available quantity,
  composition, width, VAT basis, lead time, and Norway shipping/logistics;
- never contacts, reserves, buys, or pays automatically;
- never promotes fabric candidates into the canonical opportunity Top 5.

Recent retained implementation chain:

```text
PR #483 — OpenAI Fabric Procurement Advisor
PR #484 — fabric advisor output-budget fix
PR #486 — Italy explicitly visible in the daily report
PR #487 — project-status cleanup
```

Temporary validation PR #485 was intentionally closed without merge.

## Multi-market daily checkpoint

`MULTI_MARKET_DAILY_OPERATOR_CHECKPOINT` is implemented, merged, scheduled daily,
and manually dispatchable. It is not an unimplemented project phase.

Do not restart Norway, Sweden, or Germany because one source returns zero, is
blocked, or remains planned.

## Workflow state

The active `.github/workflows` directory contains five workflows:

```text
germany-clothing-inventory-live.yaml
multi-market-daily-operator-checkpoint.yaml
one-opportunity-commercial-analysis.yaml
sweden-clothing-inventory-live.yaml
tests.yml
```

Older workflow-audit documents are historical records and do not define current
runtime inventory.

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
- `docs/UNIFIED_DECISION_PRIORITY_V1.md` — actionability ordering.
- `docs/MARKET_COMPARABLES_BENCHMARK_V1.md` — bounded public comparables.
- `docs/OPENAI_FABRIC_PROCUREMENT_ADVISOR_V1.md` — bounded fabric AI behavior.
- `docs/CENTRAL_INTELLIGENCE_ORCHESTRATOR_V1.md` — final operator synthesis.

## Decision and safety invariants

- Missing facts remain unknown; never invent price, quantity, company, location,
  VAT, customs, logistics, profit, or ROI.
- Source failure is not a zero-opportunity result.
- A valid zero-result run is not a failure.
- Historical or ended records are not active opportunities.
- AI recommendations remain advisory and evidence-backed.
- `BUY_REVIEW` requires human review and is not automatic buying.
- No automatic contact, bid, reservation, purchase, or payment.
- Do not run authorization-gated collectors without permission.

## Current development priority

Do not restart completed markets or add tools merely because they are available.

The priority is now:

```text
run existing daily intelligence
→ inspect the central operator brief
→ verify commercial facts for the selected target
→ improve only demonstrated gaps
```

New tools, sources, or countries should be added only when the central daily flow
shows a concrete gap that existing components cannot solve.
