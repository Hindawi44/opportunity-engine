# CENTRAL_INTELLIGENCE_ORCHESTRATOR_V1

## Purpose

Provide one operator-facing daily synthesis over the intelligence that the project
already produces.

This is not a new collector, model, market, database, lifecycle, or opportunity
engine. It is the final deterministic coordination layer above the existing:

```text
fabric procurement watch
→ OpenAI fabric procurement advisor
→ unified market intelligence river
→ unified decision priority
→ market comparables benchmark
→ CENTRAL INTELLIGENCE ORCHESTRATOR
```

## Inputs

The orchestrator reads existing daily artifacts when available:

```text
domain-market-intelligence-brief.json
unified-daily-decision-brief.json
fabric-procurement-watch.json
openai-fabric-procurement-advisor.json
market-comparables-benchmark.json
```

It does not fetch pages and does not call OpenAI.

## Output

The daily output directory gains:

```text
central-intelligence-brief.json
central-intelligence-brief.txt
```

A compact `central_intelligence_orchestrator` summary is also attached to the
existing `domain-market-intelligence-brief.json`.

The central brief exposes separate views for:

- the strongest current commercial opportunity or offer;
- the strongest watch-only market signal;
- the strongest current fabric supplier candidate;
- the current market visibility (`NO | SE | DE | IT` when Italy fabric
  procurement is present);
- one and only one recommended human action.

## Decision precedence

The orchestrator does not replace `Unified Decision Priority`.

It reuses its actionability ordering and keeps the business roles separate:

```text
1. Current direct / B2B / auction commercial opportunity
2. Otherwise top fabric procurement candidate
3. Otherwise top market-watch signal
4. Otherwise continue monitoring
```

Fabric supplier ranking uses the existing Fabric Advisor `HIGH / MEDIUM / LOW`
review priority when available, then source-backed procurement relevance. AI
output remains advisory and never overrides source evidence.

## Safety boundary

```text
decision_owner: HUMAN_OPERATOR
single_human_action_enforced: true
promotion_to_opportunity_allowed: false
automatic_contact: false
automatic_bid: false
automatic_reservation: false
automatic_purchase: false
automatic_payment: false
```

The layer does not invent price, MOQ, quantity, composition, width, shipping,
VAT, logistics, profit, or ROI.

## Runtime ordering

The CLI hook is registered before the existing post-bulletin hooks so Python's
reverse `atexit` order produces:

```text
fabric watch
→ fabric AI
→ unified river
→ market comparables
→ central intelligence brief
```

A failure or missing optional artifact is represented truthfully; it does not
erase the established daily bulletin.
