# Operational Transport Input V1

## Purpose

`operational_transport_input_v1.json` connects the opportunity already selected
by `operational_landed_cost_v1.json` with Mahmoud's buyer profile in Namsos and
the Norway domestic market profile.

It creates an auditable `TransportEstimateInputV1` record without selecting a
new opportunity, parsing listing prose, calculating distance, contacting a
carrier, or inventing a transport price.

## Pipeline position

```text
decision_intelligence.json
        ↓
operational_landed_cost_v1.json
        ↓
operational_transport_input_v1.json
        ↓
manual shipment evidence or transport quote
```

The operational landed-cost sidecar remains the owner of opportunity selection.
The transport adapter must use the same `opportunity_id`.

## Inputs

The default CLI inputs are:

```text
data/operational_landed_cost_v1.json
config/buyers/mahmoud_namsos_v1.json
config/markets/no_v1.json
```

The buyer profile supplies the destination and settlement currency. The Norway
market profile supplies the domestic market boundary and origin country when
the selected source does not contain a structured country code.

## Structured-copy policy

Only explicit structured logistics fields are copied:

- source country, city, postal code, and coordinates
- cargo type
- weight and volume
- pallet, package, and item counts
- longest length
- loading, unloading, forklift, tail-lift, and dismantling requirements
- transport mode
- an existing landed-cost transport component

Missing fields remain `null` or `UNKNOWN`.

The adapter deliberately does **not** parse measurements from title or prose.
For example, a title containing `800kg` does not become `weight_kg=800` until a
structured field or documented evidence supplies that value.

## Quote reuse

The existing `transport` component in `LandedCostEstimateV1` maps as follows:

| Landed-cost status | Transport quote status |
|---|---|
| `UNKNOWN` | `UNKNOWN` |
| `ESTIMATED` | `ESTIMATED` |
| `CONFIRMED` | `CONFIRMED` |
| `NOT_APPLICABLE` | `NOT_APPLICABLE` |

No amount is recalculated. Confirmed transport still requires evidence, and an
estimated range still requires assumption notes.

## Zero-result behavior

When the landed-cost sidecar reports `NO_ELIGIBLE_OPPORTUNITY`, the transport
sidecar is valid and contains:

```json
{
  "selection_status": "NO_ELIGIBLE_OPPORTUNITY",
  "source_opportunity": null,
  "transport_input": null,
  "transport_snapshot": null
}
```

A zero-result run does not fail the P4 pipeline.

## Current expected operational result

For the current selected opportunity, the source city is available and the
destination is Namsos, but shipment dimensions and transport mode are not
structured. The expected state is therefore:

```text
REQUIRES_SHIPMENT_INPUTS
```

Transport cost remains `null`.

## CLI

```bash
PYTHONPATH=src python scripts/build_operational_transport_input.py \
  --landed-cost data/operational_landed_cost_v1.json \
  --buyer config/buyers/mahmoud_namsos_v1.json \
  --market config/markets/no_v1.json \
  --output data/operational_transport_input_v1.json
```

## Safety boundaries

This integration does not:

- select or rerank opportunities
- parse title or description text for shipment measurements
- calculate routes or distance
- query maps or carriers
- request transport quotes
- calculate VAT or customs
- change `final_decision`, scoring, Top 5, or alerts
- purchase, bid, or contact a seller

The next step after this contract is to collect structured shipment evidence or
enter a documented manual quote. Only then can the transport component become
ready for complete landed-cost qualification.
