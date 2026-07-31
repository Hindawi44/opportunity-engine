# Landed Cost Estimate V1

`LandedCostEstimateV1` is a conservative, auditable contract for estimating the
cash required and net economic cost of moving one opportunity to one buyer
destination.

V1 defines the data boundary only. It does not fetch carrier quotes, calculate a
route, apply tax or customs rules, rank opportunities, or change the official
opportunity decision.

## Why ranges are required

Many listings omit weight, dimensions, pallet count, loading conditions, final
platform fees, and transport terms. An estimate must therefore use a range:

```text
low_nok <= expected_nok <= high_nok
```

A confirmed component uses one exact amount in all three fields and requires an
auditable `source_ref`. An estimated component requires a range and at least one
note explaining the assumption.

## Component statuses

Each cost component has one status:

- `CONFIRMED`: exact amount supported by evidence;
- `ESTIMATED`: supported range with an explicit assumption;
- `UNKNOWN`: no amount is available;
- `NOT_APPLICABLE`: the component does not apply to this transaction.

Unknown and not-applicable components must not contain amounts. Unknown values
remain unknown; the contract never replaces them with zero.

## Economic treatment

Cash flow and economic cost are not always identical. Each known component is
classified as:

- `ECONOMIC_COST`: a non-recoverable cost;
- `RECOVERABLE_CASH_OUTFLOW`: cash may be required, but the amount may later be
  recovered or deducted;
- `UNKNOWN`: the amount is known or estimated, but its final economic treatment
  has not been verified;
- `NOT_APPLICABLE`.

This is particularly important for VAT. V1 does not embed any VAT rate and does
not assume that VAT is either recoverable or non-recoverable.

## Output totals

The snapshot reports:

- `known_cash_required_range`: sum of every confirmed or estimated amount;
- `complete_cash_required_range`: available only when no required amount is
  unknown;
- `known_recoverable_cash_outflow_range`: known recoverable cash outflows;
- `known_net_economic_cost_range`: known non-recoverable economic costs;
- `complete_net_economic_cost_range`: available only when all required amounts
  and economic treatments are known.

A known subtotal is not presented as a complete landed cost.

## Estimate status and confidence

Possible statuses:

```text
REQUIRES_COST_INPUTS
PARTIAL_ESTIMATE
COMPLETE
```

Possible confidence values:

```text
NONE
LOW
MEDIUM
HIGH
```

A missing required component creates a partial estimate with low confidence. A
complete estimate containing ranges has medium confidence. A complete estimate
made only of confirmed exact amounts has high confidence.

## Destination precision

The contract records the destination supplied by the buyer profile. The initial
Mahmoud profile contains `Namsos` but no postal code or coordinates, so the
precision is:

```text
CITY_LEVEL_INPUT_ONLY
```

This is enough to preserve the destination context, but V1 does not claim that a
precise route or carrier price has been calculated.

## Safety boundary

Landed Cost Estimate V1:

- does not perform route or shipping-quote lookup;
- does not perform tax or customs-rule lookup;
- does not change `final_decision`;
- does not change ranking, Top 5, or alerts;
- does not contact sellers, bid, or purchase;
- does not invent price, transport, tax, or handling values.

## Validation CLI

Validate an input document and write an auditable snapshot:

```bash
PYTHONPATH=src python scripts/build_landed_cost_estimate.py \
  --input path/to/estimate-input.json \
  --output data/landed_cost_estimate_v1.json
```

The CLI uses only local JSON input. V1 makes no network request and adds no new
dependency.

## Next step

After this contract is stable, a later PR can adapt one real opportunity into
this shape. That integration must preserve the official decision and must keep
missing transport or tax inputs visible rather than estimating them silently.
