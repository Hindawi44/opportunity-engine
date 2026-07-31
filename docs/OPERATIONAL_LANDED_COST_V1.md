# Operational Landed Cost Sidecar V1

This step applies `LandedCostEstimateV1` to one real record from:

```text
data/decision_intelligence.json
```

It is an additive operational sidecar. The decision report remains the owner of
`final_decision`, `opportunity_score`, ranking, Top 5, and alerts.

## Selection policy

The scheduled P4 pipeline selects the first ranked decision record that has:

- a non-empty `opportunity_id`; and
- a non-negative `asking_price_nok`.

An explicit opportunity can be selected through the CLI with
`--opportunity-id`.

When the decision result is empty, or no record has a known asking price, the
sidecar is still written successfully with:

```text
NO_ELIGIBLE_OPPORTUNITY
```

This preserves reliable zero-result behavior.

## Real-data mapping

The adapter copies only explicit values from the selected decision record.

| Landed-cost component | Decision field |
| --- | --- |
| Current purchase baseline | `asking_price_nok` |
| Auction/platform fee | `auction_fee_nok` |
| Transport | `transport_cost_nok` |
| Dismantling/loading | `dismantling_cost_nok` |
| Storage | `storage_cost_nok` |
| Repair/condition allowance | `repair_cost_nok` |
| Other costs | `other_costs_nok` |
| VAT cash outflow | `vat_nok` |

The asking price is recorded as a confirmed current amount, but its note states
that it is not a final purchase commitment.

Missing values remain `UNKNOWN` with `null` amounts. They are never converted to
zero.

## VAT treatment

A known VAT amount is not automatically treated as a final economic cost.

- `vat_recoverable=true`, or a documented recoverable status, produces
  `RECOVERABLE_CASH_OUTFLOW`.
- an explicitly non-recoverable status produces `ECONOMIC_COST`.
- no documented treatment produces `UNKNOWN`, even when the VAT amount is known.

This separates liquidity required from net economic cost.

## Buyer destination

The destination is copied from:

```text
config/buyers/mahmoud_namsos_v1.json
```

The current destination is Namsos, Norway, in NOK. Postal code and coordinates
remain unknown, so destination precision remains `CITY_LEVEL_INPUT_ONLY`.

No route lookup, map request, carrier quote, tax lookup, customs lookup, or
external API is performed.

## Output

The P4 pipeline writes:

```text
data/operational_landed_cost_v1.json
```

The sidecar contains:

- selected source opportunity summary;
- unchanged `final_decision` and `opportunity_score` copies for audit;
- the landed-cost component snapshot;
- known cash-required range;
- known recoverable cash outflow;
- known net economic cost;
- missing and missing-required inputs;
- qualification-cost readiness;
- explicit safety scope.

## Manual execution

```bash
PYTHONPATH=src python scripts/build_operational_landed_cost.py
```

Select a specific current decision:

```bash
PYTHONPATH=src python scripts/build_operational_landed_cost.py \
  --opportunity-id unified-auksjonen-614288
```

## Safety boundary

This step does not:

- change `final_decision`;
- change scoring, ranking, Top 5, or alerts;
- estimate unknown shipping or fees;
- calculate VAT or customs rules;
- contact sellers;
- place bids;
- purchase automatically.
