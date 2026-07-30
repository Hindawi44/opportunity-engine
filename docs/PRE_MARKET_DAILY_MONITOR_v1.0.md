# Pre-Market Daily Monitor v1.0

## Goal

Turn the pre-market clothing bankruptcy path into a bounded daily operating loop
that remembers prior cases, searches only the highest-priority current estates,
and publishes changes without interpreting a source outage as evidence that no
sale exists.

## Scheduled execution

The existing workflow is reused instead of creating another workflow file:

```text
.github/workflows/daily-opportunity-pipeline.yml
```

A dedicated schedule runs at `05:37 UTC` each day. The unusual minute reduces
contention around the top of the hour. The existing six-hour opportunity pipeline
schedule remains unchanged.

Manual workflow dispatch runs the primary pipeline first and then the pre-market
monitor. A shared workflow concurrency group prevents two scheduled workflow runs
from writing state at the same time.

## Bounded search budget

The production command is:

```bash
python scripts/run_pre_market_daily_monitor.py \
  --previous-registry data/pre_market_cases.json \
  --case-limit 10 \
  --results-per-query 10 \
  --lookback-days 365 \
  --freshness py \
  --output-dir artifacts/pre-market-daily-monitor
```

Each selected estate uses the existing five-query exact-identity query pack.
Therefore the maximum daily request allocation is:

```text
10 estates x 5 queries = 50 Brave search requests
```

The monitor does not expand to every bankruptcy record and does not run more than
20 estates even when invoked manually.

## Persistent state

The workflow commits only the durable operating outputs:

- `data/pre_market_cases.json`
- `data/pre_market_case_changes.json`
- `data/pre_market_sale_channel_alerts.json`
- `data/pre_market_operator_action_queue.json`
- `data/pre_market_live_clothing_top5.json`
- `data/pre_market_source_status.json`
- `data/pre_market_daily_monitor_status.json`

Raw bounded search reports remain in the 30-day workflow artifact and are not
committed to the repository.

## Source-failure rule

A failed estate enrichment or incomplete targeted search is recorded as:

```text
SOURCE_TEMPORARILY_UNAVAILABLE
```

That observation is not passed into the persistent case tracker. Existing case
state, candidate URLs, and commercial eligibility are therefore preserved rather
than downgraded or cleared by a temporary outage.

The monitor explicitly records:

```text
incomplete_sources_are_treated_as_no_sale = false
failed_or_incomplete_observations_applied_to_registry = false
```

## Alert rule

The persistent tracker continues to alert only for material commercial changes:

- a new liquidation-channel candidate;
- a new sale-listing candidate;
- a verified active inventory sale.

Repeated identical observations produce no alert. Source unavailability is visible
in the source-status output but does not create a commercial opportunity alert.

## FINN boundary

FINN remains `MANUAL_REVIEW_ONLY`. Search-provider results may identify a possible
FINN page, but the scheduled monitor does not open, scrape, log in to, or copy FINN
content automatically.

## Non-negotiable safety boundaries

- no automatic page opening;
- no automatic email or seller contact;
- no bid, purchase, reservation, commitment, or payment;
- no automatic investment decision;
- no commercial Top 5 admission before `VERIFIED_ACTIVE_INVENTORY_SALE`;
- no source failure interpreted as absence of a sale.
