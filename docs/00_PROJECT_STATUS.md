# Opportunity Engine — Project Status

**Last updated:** 2026-08-02  
**Status:** ACTIVE  
**Authoritative repository:** `Hindawi44/opportunity-engine`

## Session startup rule

Every development session must begin by reading, in this order:

1. `docs/00_PROJECT_STATUS.md`
2. `docs/Opportunity_Discovery_Analysis_Blueprint_v2.0.md`
3. `docs/REPOSITORY_ARCHITECTURE_AUDIT_v2.0.md`
4. `docs/MARKET_COMPLETION_MATRIX_v1.0.md`
5. The current-task document named below

The repository is the source of truth. Market completion and source activation must be read from separate fields.

## Product principle

The project has two independent engines:

- **Discovery Engine:** discovers and verifies traceable opportunities.
- **Analysis Engine:** analyzes confirmed opportunities.

Neither engine may perform the other engine's responsibility. The bridge between them is the **Opportunity Dossier**.

## Approved end-to-end path

```text
Opportunity Map
  -> Discovery Engine
  -> Opportunity Dossier
  -> Verified Market Comparables
  -> Verified Acquisition Costs
  -> Existing Analysis Engine
  -> Opportunity Score
  -> Decision Intelligence
  -> Final Investment Report or Evidence-Required Outcome
```

Canonical investment decisions remain:

```text
BUY_REVIEW / WATCH / REJECT
```

`BUY_REVIEW` is a human-review state only.

## Current scope lock

The only validated domain is:

```text
CLOTHING_INVENTORY
```

Blocked domains remain:

- Wedding dresses
- Sewing equipment
- Fabrics
- Store fixtures
- Other opportunity domains

No new domain, country, or source implementation is currently approved.

## Current project decision

```text
PROJECT_ENGINE_OPERATIONAL
COUNTRY_FOUNDATIONS_NO_SE_DE_COMPLETE
SOURCE_ACTIVATION_PARTIAL_AND_EXPLICIT
NEW_SOURCE_EXPANSION_PAUSED
NEXT_TASK_MULTI_MARKET_DAILY_OPERATOR_CHECKPOINT
```

Norway, Sweden and Germany must not be restarted merely because an individual source is `PLANNED`, authorization-blocked, or waiting for a qualifying live case.

## Market completion semantics

The project tracks five separate dimensions:

```text
MARKET_FOUNDATION_STATUS
SOURCE_IMPLEMENTATION_STATUS
RUNTIME_ACTIVATION_STATUS
DAILY_WATCH_STATUS
CURRENT_OPPORTUNITY_STATUS
```

Authoritative files:

```text
config/market_completion_matrix.json
docs/MARKET_COMPLETION_MATRIX_v1.0.md
config/source_expansion_plan.json
data/source_gap_matrix.json
```

`data/source_gap_matrix.json` remains the official runtime source-status snapshot. It does not by itself describe whether a bounded pilot or daily watch has already been implemented.

## Country status

### Norway (`NO`)

```text
MARKET_FOUNDATION_STATUS = COMPLETE
SOURCE_NETWORK_STATUS = PARTIAL
RESTART_MARKET = false
```

Active public channels:

- Auksjonen.no;
- Konkurs.app as a bankruptcy-lead channel;
- Politiet.no as a public-auction-event lead channel.

Authorization dependencies:

- FINN.no;
- Konkurskupp;
- Bjarøy.

Other planned Norwegian sources are backlog entries and do not make the market foundation incomplete.

### Sweden (`SE`)

```text
MARKET_FOUNDATION_STATUS = COMPLETE
SOURCE_IMPLEMENTATION_STATUS = BOUNDED_PILOT_IMPLEMENTED
RESTART_MARKET = false
```

Implemented paths:

- Blinto;
- Klaravik;
- PS Auction;
- Swedish open-web discovery.

Latest validated Blinto evidence:

```text
status = PASS
merged_candidates = 6
ended_or_historical = 6
confirmed_sales = 0
top5_count = 0
sqlite_persisted_record_count = 6
conversion_error_count = 0
```

This proves the Swedish pipeline and SQLite path. It does not prove a current active opportunity and does not automatically change the source runtime status to `ACTIVE`.

### Germany (`DE`)

```text
MARKET_FOUNDATION_STATUS = COMPLETE
SOURCE_NETWORK_STATUS = ONE_ACTIVE_TWO_OPERATIONAL_WATCHES
RESTART_MARKET = false
```

Current source paths:

| Source | Runtime status | Implementation | Schedule |
|---|---|---|---|
| Riegermann | `ACTIVE` | Active discovery and complete catalog handling | `05:17 UTC` |
| VENTA Industrieversteigerungen | `PLANNED` | Daily active-index and complete-catalog watch | `05:47 UTC` |
| Deutsche Pfandverwertung | `PLANNED` | Daily active-index, catalog and exact bulk-item watch | `06:17 UTC` |

VENTA and Deutsche Pfandverwertung are implemented watches that remain unactivated until their required live clothing evidence appears and passes verification.

### Denmark (`DK`)

```text
MARKET_FOUNDATION_STATUS = PLANNED
SOURCE_IMPLEMENTATION_STATUS = NOT_IMPLEMENTED
```

No Denmark implementation is authorized by the current task.

## Completed and retained

- Blueprint v2.0 approved.
- Repository Architecture Audit v2.0 approved.
- Existing Analysis Engine V2.8–V3.7 retained and frozen.
- Clothing Inventory selected as the reference MVP domain.
- Opportunity Dossier specification and confirmed-dossier intake retained.
- Controlled end-to-end and real-case validation chain retained.
- Scenario-driven Clothing Inventory discovery and strict verification gates retained.
- Post-verification Top 5 hard gate retained.
- Norway market profile and active public channels retained.
- Sweden market profile and bounded Blinto, Klaravik and PS Auction pilots retained.
- Germany market profile and open-web pilot retained.
- Riegermann active source with daily discovery retained.
- VENTA daily zero-result-capable watch retained.
- Deutsche Pfandverwertung daily zero-result-capable watch retained.
- Unified JSON reporting and SQLite persistence retained.
- Full project review checkpoint merged through PR #411.
- Market/source completion semantics reconciled through the current configuration and documentation update.

## Accepted operator surface

```text
1 — Discover Clothing Inventory Opportunities
2 — Review One Opportunity End to End
```

The canonical repository-wide regression owner remains:

```text
.github/workflows/tests.yml
```

Geographic and source-specific workflows remain supporting workflows, not replacements for the two principal operator workflows.

## Workflow state

The repository currently retains 36 workflow files, including production support, acceptance checks, geographic pilots and historical diagnostics.

Many `TEMP` and `Temporary` workflows remain visible in GitHub Actions. This is an operator-usability defect, not a product blocker. No workflow may be deleted or disabled without preserved history, equivalent coverage evidence and a rollback path.

## Current phase

**Phase:** Multi-market operator checkpoint  
**Status:** `TASK_DEFINED_READY_FOR_IMPLEMENTATION`

## Current implementation checkpoint

```text
PROJECT_STATE_RECONCILIATION_v1.0
```

The reconciliation establishes:

- Norway, Sweden and Germany foundations are complete;
- individual source runtime status remains independent;
- a successful historical-only pilot is not a current opportunity;
- a daily zero-result watch is an implemented capability even while its source remains `PLANNED`;
- new source expansion remains paused.

## Current task document

```text
docs/MULTI_MARKET_DAILY_OPERATOR_CHECKPOINT_TASK_v1.0.md
```

## Next implementation contract

The next implementation must:

1. remain limited to `CLOTHING_INVENTORY`;
2. reuse existing Norway, Sweden and Germany outputs;
3. produce one read-only phone summary and one structured report;
4. distinguish source failure from a valid zero-result run;
5. distinguish active, historical, ended, blocked and unresolved records;
6. deduplicate opportunity identities across the consolidated result;
7. preserve source-native currencies (`NOK`, `SEK`, `EUR`);
8. preserve verification, dossier, eligibility and post-verification Top 5 gates;
9. identify no more than one immediate human action;
10. add no fourth country and no new source adapter.

## Strict confirmation conjunction

`CONFIRMED_SALE` requires:

```text
page_role == ITEM_LISTING
AND stable opportunity identity
AND bounded clothing-inventory evidence
AND bounded sale evidence
AND listing_status == ACTIVE
AND successful public verification
```

Search snippets, source names, company names, category labels and historical records cannot confirm a sale by themselves.

## Source-state rules

- `ACTIVE`: formally activated source with validated runtime evidence.
- `CODE_READY`: implementation ready but activation configuration remains.
- `BLOCKED_AUTH`: official authorization or feed is required.
- `PLANNED`: runtime activation is not approved; implementation detail must be read separately.
- `DEPRECATED`: source removed by an explicit documented decision.

Implementation detail uses:

```text
NOT_IMPLEMENTED
BOUNDED_PILOT_IMPLEMENTED
DAILY_WATCH_IMPLEMENTED
ACTIVE_IMPLEMENTATION
```

## Non-negotiable rules

- Do not restart Norway, Sweden or Germany.
- Do not add Denmark or another country in the next task.
- Do not add a new opportunity domain.
- Do not weaken public verification or eligibility gates.
- Do not modify the Opportunity Dossier contract.
- Do not modify V2.8–V3.7 financial formulas.
- Do not invent price, quantity, company, location, VAT, customs, logistics, profit or ROI.
- Do not treat source failure as zero opportunities.
- Do not treat a valid zero result as failure.
- Do not contact sellers.
- Do not bid, reserve, purchase or pay.
- Do not run authorization-gated collectors without explicit permission.

## Immediate next action

Implement only:

```text
MULTI_MARKET_DAILY_OPERATOR_CHECKPOINT
```

The first version must be manual and read-only. It must consolidate existing Norway, Sweden and Germany evidence before any further source or country expansion is considered.
