# Pre-Market Clothing Leads Pilot v1.0

## Goal

Test whether recent clothing-related bankruptcy registrations can produce a
useful human review queue before a verified public inventory sale appears.

## Scope

The pilot reuses the existing bounded Konkurs.app clothing collector and adds a
separate review-priority layer. It remains limited to:

- `47.710` — clothing retail;
- `46.420` — clothing and footwear wholesale;
- active bankruptcy estates returned by the existing bounded API reads;
- company-level fields already retained by the approved adapter.

## Score meaning

`inventory_signal_score` is a transparent heuristic based on:

- bankruptcy recency;
- wholesale versus retail industry;
- MVA registration;
- reported company asset scale;
- reported company revenue scale.

It is **not** a statistical probability, inventory evidence, sale evidence, or
valuation. Missing financial values add no points and remain unknown.

## Output contract

The manual runner writes:

- `pre-market-clothing-leads.json` — all ranked early leads and score evidence;
- `pre-market-leads-top5.json` — the bounded human review queue;
- `live-clothing-top5.json` — always empty in this pilot;
- `operator-summary.txt` — concise operator review summary.

Every lead remains:

```text
PRE_MARKET_LEAD
inventory_sale_verified = false
inventory_quantity_verified = false
public_sale_found = false
top5_eligible = false
analysis_eligible = false
operator_review_required = true
```

## Manual execution

```bash
python scripts/run_pre_market_clothing_leads.py \
  --lookback-days 365 \
  --page-size 50 \
  --review-limit 5
```

## Pilot success criteria

1. The bounded Konkurs.app source scan completes without errors.
2. The score is deterministic and exposes its complete breakdown.
3. Large, recent clothing wholesalers rank ahead of weak old retail records.
4. No bankruptcy lead enters the commercial Top 5 or Analysis Engine.
5. No personal name or detailed address is retained.
6. No contact, bid, purchase, reservation, payment, schedule, or automatic
   investment decision is added.
7. Human review of the first 5–10 results determines whether the signal is useful
   enough to justify a later estate-manager enrichment pilot.

## Explicitly deferred

- estate-manager or law-firm enrichment;
- liquidator identification;
- automated contact or email;
- recurring monitoring;
- public-sale verification;
- financial analysis.
