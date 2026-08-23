# Unified Pipeline Sidepath Inventory V1

Date: 2026-08-23

## Decision

The repository must have one governing opportunity path:

`Discovery -> Signal Validation -> Entity Resolution -> Memory -> Follow-up -> Exact Lot Verification -> Commercial Qualification -> Evidence -> Opportunity Decision -> Report`

Country collectors, named-source adapters, shadow labs, learning loops, commercial analysis, and operator controls may support this path, but they may not own a competing final decision path.

The governing runtime is `.github/workflows/multi-market-daily-operator-checkpoint.yaml` and the governing market contract is `UNIFIED_SIX_MARKET_PIPELINE_V1` for NO, SE, DE, FR, IT, and NL.

## Operator-visible workflows

| Workflow | Classification | Decision |
|---|---|---|
| `multi-market-daily-operator-checkpoint.yaml` | PRIMARY_RUNTIME | Keep as the single governing daily path. |
| `one-opportunity-commercial-analysis.yaml` | DOWNSTREAM_ANALYSIS | Keep. Consume verified unified opportunities; do not rescan markets as a parallel discovery engine. |
| `mind-forge-live-research-launcher.yaml` | LEARNING_AND_RESEARCH | Keep separate from daily decision authority. Learned patterns may return to Discovery only through validation/promotion gates. |
| `sweden-clothing-inventory-live.yaml` | MANUAL_DIAGNOSTIC | Keep manual-only. Production Sweden discovery already belongs to the multi-market checkpoint. |
| `germany-clothing-inventory-live.yaml` | MANUAL_DIAGNOSTIC | Keep manual-only. Production Germany discovery already belongs to the multi-market checkpoint. |
| `tests.yml` | CI_GUARD | Keep as test infrastructure only. |

## Architectural sidepath families

### 1. Source-specific adapters

Examples: Auksjonen, FINN Gmail intake, cross-source Norway, Blinto, Klaravik, PS Auction, Riegermann, VENTA, DPV.

Decision: **KEEP AS OPTIONAL INGESTION PROVIDERS**.

They should plug into Discovery. A source may provide high-confidence evidence, but the source itself must not define a separate opportunity lifecycle or final decision authority.

### 2. Shadow and lab systems

Examples: Mathematical Logic Shadow, Keyword Shadow Verification, Source Discovery Shadow, Source Shadow Live Validation, Stocklear shadow rounds.

Decision: **KEEP SHADOW-ONLY**.

Allowed output: observations, benchmark results, proposed patterns, diagnostics.

Forbidden output: direct production promotion, direct final opportunity decision, automatic contact/bid/purchase.

### 3. Learning, Query Gap, and feedback

Examples: root-cause feedback, missed-opportunity learning, Query Gap handoff, MIND FORGE learning memory, fast memory, experiment outcomes, pattern promotion.

Decision: **KEEP AS A CONTROLLED FEEDBACK LOOP**.

Target loop:

`Outcome / Miss -> Root Cause -> Candidate Pattern -> Holdout / Validation -> Promotion Gate -> Discovery Strategy`

Learning must never bypass evidence or promotion gates.

### 4. Commercial evidence, cost, logistics, and financial analysis

Examples: operational transport, shipment evidence queue, landed cost, market comparables, economic evaluation, one-opportunity commercial analysis.

Decision: **KEEP AS SHARED DOWNSTREAM STAGES**.

These capabilities should be reused after Exact Lot Verification / Commercial Qualification. They should not be rebuilt per country.

### 5. State, human review, and operator control

Examples: checkpoint state restore, human review outcome, action center, domain market intelligence feed.

Decision: **KEEP AS A SHARED CONTROL PLANE** attached to the unified pipeline.

There should be one lifecycle truth and one operator action surface, not separate state machines per source or country.

### 6. Domain-specific experiments

Examples currently include fabric procurement watch and the quote-to-job experiment kit.

Decision: **NON-GOVERNING UNTIL MAPPED TO THE UNIFIED CONTRACT**.

A new domain should not become another parallel engine. It should define its Opportunity Map / discovery semantics and then enter the same unified contract.

## Migration order

1. Keep `multi-market-daily-operator-checkpoint` as the sole daily governing runtime.
2. Move FR/IT/NL execution from sidecar semantics behind the unified market contract.
3. Route source-specific adapters into the common Discovery stage.
4. Route Exact Lot and Commercial Qualification through shared country-neutral contracts with country/source adapters only where parsing differs.
5. Attach shared Evidence / Cost / Logistics / Analysis stages once, downstream of verified lots.
6. Attach MIND FORGE / Query Gap as a feedback loop into Discovery, never as a parallel decision engine.
7. Keep shadow systems observatory-only.
8. After runtime unification is proven, perform a separate cleanup PR for obsolete diagnostics and Git branches.

## Git branch hygiene snapshot

A branch search on 2026-08-23 found **240 `agent/...` branches**. Many names are clearly temporary/live-proof/fix branches (`temp-*`, `one-time-*`, `*-live-proof-*`, `fix-*`, and older country/MIND FORGE implementation branches).

These branches do **not** have runtime authority over `main`, so they are a maintenance issue rather than an execution-path issue.

Decision: do not delete them in this inventory. A separate branch-cleanup pass must first verify merge/closed/open status and protect any branch that still contains unmerged work.

## Safety invariants

The unification work must preserve:

- no automatic contact;
- no automatic bid;
- no automatic reservation;
- no automatic purchase;
- no automatic payment;
- no invented missing commercial values;
- no direct learning promotion without validation;
- no deletion of legacy paths until a dedicated cleanup PR proves they are redundant.

## Machine-readable source of truth

`config/unified_pipeline_sidepaths_v1.json`

`tests/test_unified_pipeline_sidepaths_inventory_v1.py` enforces that every operator-visible GitHub Actions workflow is classified and that there remains exactly one governing daily runtime.
