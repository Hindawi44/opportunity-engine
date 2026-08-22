# Full Runtime Coverage Audit — 2026-08-22

## Purpose

Inventory the discovery/search capabilities that exist in the repository and classify whether they are actually executed by the single automatic production scheduler.

This audit is deliberately read-only with respect to production behavior. It does not add schedules, automatic purchasing, bidding, contact, or payment.

## Production scheduler verified

The repository currently has one automatic production scheduler:

- `.github/workflows/multi-market-daily-operator-checkpoint.yaml`
- cron: `17 5 * * *`

The automatic checkpoint directly executes the following current source lanes:

### Norway

- Auksjonen public clothing path
- FINN saved-search alerts via Gmail
- bounded Norway cross-source verification

### Sweden

- Blinto bounded direct scan
- Klaravik bounded direct scan
- PS Auction bounded direct scan

### Germany

- Sen & Sen bounded liquidation scan
- Riegermann active discovery
- VENTA active clothing watch
- Deutsche Pfandverwertung active clothing watch

It then builds the central checkpoint/intelligence/reporting path.

## Implemented capabilities outside the automatic checkpoint

The repository contains additional implemented discovery/feed families that are not called by the automatic checkpoint.

### Country market discovery runners

- Italy: `scripts/build_italy_market_discovery.py`
- France: `scripts/build_france_market_discovery.py`
- Netherlands: `scripts/build_netherlands_market_discovery.py`

Associated discovery modules and case-memory adapters exist for these markets.

### Optional commercial / procurement side feeds

`scripts/build_optional_market_intelligence_side_feeds.py` contains bounded collectors for:

- fabric procurement / deadstock watch
- Merkandi B2B liquidation
- Fashion Stock Netherlands
- Stockhurt B2B feed
- Stockhurt official catalog enrichment
- Jobalots clothing auction feed
- Jobalots official page enrichment
- Jobalots official catalog discovery

The automatic daily entry point intentionally does not call this side-feed runner.

## Configuration drift discovered

Two repository state/config documents are stale relative to current runtime wiring:

1. `config/market_completion_matrix.json` says Sweden `daily_watch_status` is `NOT_SCHEDULED`, but the production workflow currently schedules Blinto, Klaravik, and PS Auction every day.
2. `config/source_expansion_plan.json` still describes several Sweden/Germany sources as PLANNED and retains historical standalone watch schedules, while the consolidated automatic checkpoint now directly invokes those scans.

Therefore these configuration documents cannot currently be treated as authoritative runtime inventory without reconciliation.

## Classification model

Every discovery capability should be assigned exactly one primary runtime class:

- `ACTIVE_DAILY` — directly invoked by the automatic production checkpoint.
- `DOWNSTREAM` — analysis, persistence, enrichment, ranking, or report generation invoked after discovery.
- `MANUAL` — intentionally available through `workflow_dispatch` or a manual runner only.
- `OPTIONAL_SIDE_FEED` — implemented but intentionally excluded from default automatic scope.
- `ORPHANED_CODE_READY` — implemented capability with no verified production/manual owner.
- `BLOCKED` — implementation exists but required auth/access is unavailable.
- `PLANNED_ONLY` — documented but not implemented.
- `ARCHIVED_OR_REGRESSION_ONLY` — retained only for rollback, tests, or historical evidence.

## Immediate next audit steps

1. Enumerate all `src/opportunity_engine/discovery/*.py` modules.
2. Enumerate all `scripts/*.py` runners/builders that invoke discovery collectors.
3. Enumerate all `.github/workflows/*` execution owners.
4. Build a source/capability → runner → workflow → schedule mapping.
5. Detect duplicate execution and code-ready capabilities with no runtime owner.
6. Reconcile stale market/source configuration with actual production wiring.
7. Only after that mapping is complete, propose the minimum safe changes required to widen useful daily coverage without duplicate searches or uncontrolled API cost.

## Current verdict

The repository is not suffering from a lack of discovery code. The main structural issue is runtime coverage fragmentation: multiple implemented market/search capabilities exist outside the single production checkpoint, while some project-state files still describe pre-consolidation runtime status.

No production behavior has been changed by this audit.
