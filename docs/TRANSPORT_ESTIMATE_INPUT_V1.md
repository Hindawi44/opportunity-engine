# Transport Estimate Input V1

## Purpose

`TransportEstimateInputV1` records the information needed to obtain or enter a
transport estimate for one opportunity and one buyer destination. It does not
calculate a road route, query a map, contact a carrier, or invent a transport
price.

The first supported destination is the buyer profile for Mahmoud in Namsos.
The contract is generic enough to support other origins and destinations later.

## Core rule

Unknown information remains `null` or `UNKNOWN`. It is never converted to zero.
A zero transport cost must not be used to represent missing data. Documented
free delivery is represented as `NOT_APPLICABLE` with a reason and evidence.

## Input sections

### Origin and destination

Each location contains:

- `country_code`
- `city`
- `postal_code`
- `coordinates`

The destination city is required. The origin must contain at least a city,
postal code, or coordinates before route readiness is available.

Route precision is reported as:

- `INCOMPLETE`
- `CITY_LEVEL_INPUT_ONLY`
- `POSTAL_CODE_LEVEL`
- `COORDINATE_LEVEL`

No distance is calculated in V1.

### Shipment

The shipment section records:

- cargo type
- weight in kilograms
- volume in cubic metres
- pallet count
- package count
- item count
- longest length in metres

Supported cargo types are:

- `UNKNOWN`
- `BOXES`
- `PALLETIZED`
- `LOOSE`
- `BULKY`
- `MIXED`

At least one shipment metric plus a known cargo type is required before the
record can proceed to transport-mode selection.

### Handling

Handling requirements are nullable booleans:

- loading required
- unloading required
- forklift required
- tail lift required
- dismantling required

A missing handling value remains visible in `unknown_handling_requirements`.
It does not silently become `false`.

### Transport mode

Supported modes are:

- `UNKNOWN`
- `SELF_PICKUP`
- `CARRIER`
- `COURIER`
- `FREIGHT`

A known route and shipment remain `REQUIRES_TRANSPORT_MODE` until one of these
methods is selected. Only then can the record become `READY_FOR_MANUAL_QUOTE`.

### Quote

Quote status is one of:

- `UNKNOWN`
- `ESTIMATED`
- `CONFIRMED`
- `NOT_APPLICABLE`

`ESTIMATED` requires a low, expected, and high NOK range plus at least one
assumption note. `CONFIRMED` requires one exact amount and a `source_ref`.
`NOT_APPLICABLE` requires a documented reason, such as seller-provided free
delivery.

## Output statuses

`build_transport_estimate_snapshot()` returns one of:

- `REQUIRES_ROUTE_INPUTS`
- `REQUIRES_SHIPMENT_INPUTS`
- `REQUIRES_TRANSPORT_MODE`
- `READY_FOR_MANUAL_QUOTE`
- `ESTIMATE_AVAILABLE`
- `CONFIRMED_QUOTE`
- `TRANSPORT_NOT_APPLICABLE`

A transport component is ready for the landed-cost engine only when the quote
is estimated, confirmed, or documented as not applicable.

## Confidence

- `NONE`: route origin is incomplete
- `LOW`: route exists but shipment, mode, or quote evidence is incomplete
- `MEDIUM`: a documented estimate range exists
- `HIGH`: an exact confirmed quote or documented not-applicable case exists

## CLI

```bash
PYTHONPATH=src python scripts/build_transport_estimate.py \
  --input path/to/transport-input.json \
  --output path/to/transport-snapshot.json
```

## Safety boundaries

Transport Estimate Input V1 does not:

- query maps or routes
- calculate distance
- request carrier quotes
- call external price services
- calculate VAT or customs
- change `final_decision`
- change scoring, ranking, Top 5, or alerts
- purchase, bid, or contact a seller

The next integration step is to build this input from the selected operational
opportunity and buyer profile, then convert an evidence-backed quote into the
existing `transport` component of `LandedCostEstimateV1`.
