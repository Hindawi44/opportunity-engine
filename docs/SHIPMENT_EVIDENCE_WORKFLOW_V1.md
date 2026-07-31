# Shipment Evidence Workflow V1

## Purpose

`Shipment Evidence Workflow V1` converts missing structured logistics inputs from
`data/operational_transport_input_v1.json` into a deterministic human-review
queue:

```text
data/operational_transport_input_v1.json
        ↓
Shipment Evidence Workflow V1
        ↓
data/shipment_evidence_queue_v1.json
```

The workflow does not extract measurements from listing prose and does not
contact sellers or carriers. It only describes what evidence is missing and why
it matters.

## Current output

The current selected opportunity has a structured origin city and Namsos as the
destination, but shipment type, dimensions or mass, handling requirements, and
transport mode are unknown. The expected workflow state is:

```text
EVIDENCE_REQUIRED_FOR_QUOTE
```

The queue contains tasks for:

- packing or cargo type;
- total weight, packed dimensions or volume, pallet/package/item count, or longest length;
- loading responsibility;
- unloading requirements in Namsos;
- forklift availability;
- tail-lift requirement;
- dismantling requirement;
- transport mode.

Each task includes:

- a stable task ID;
- the exact opportunity ID;
- requested structured fields;
- expected information source;
- priority;
- Norwegian and Arabic questions;
- whether the task blocks a manual quote and qualification;
- status and evidence placeholders.

## Workflow states

### `NO_ELIGIBLE_OPPORTUNITY`

No operational opportunity was selected. The queue is valid and empty.

### `EVIDENCE_REQUIRED_FOR_QUOTE`

One or more evidence tasks block a manual transport quote.

### `READY_FOR_MANUAL_QUOTE`

Structured route, shipment, handling, and transport-mode inputs are sufficient,
but no transport amount has been supplied.

### `EVIDENCE_REVIEW_OPTIONAL`

An estimated or confirmed transport component already exists. Remaining missing
shipment inputs are shown as non-blocking review tasks.

### `TRANSPORT_COMPONENT_READY`

The transport component is ready and no shipment-evidence tasks remain.

## Evidence rules

A value is considered available only when it exists as a structured field in the
transport input. Text such as `800kg` inside a title or description does not
resolve `shipment.weight_kg`.

An unknown future input is never ignored. It becomes an
`UNMAPPED_TRANSPORT_INPUT` manual-review task that blocks the quote until the
field is mapped or resolved.

## Questions and sources

Seller-facing questions use Norwegian Bokmål and include Arabic translations for
operator review. Questions are not sent automatically.

Source channels are:

- `LISTING_OR_SELLER`
- `BUYER_OR_CARRIER`
- `OPERATOR`
- `MANUAL_REVIEW`

## CLI

```bash
PYTHONPATH=src python scripts/build_shipment_evidence_queue.py \
  --transport-input data/operational_transport_input_v1.json \
  --output data/shipment_evidence_queue_v1.json
```

The writer uses a temporary file and atomic replacement.

## Safety boundary

V1 does not:

- parse listing prose into logistics facts;
- send messages to a seller or carrier;
- request quotes automatically;
- calculate routes, distances, taxes, or prices;
- preserve task completion between runs;
- change `final_decision`, score, ranking, Top 5, alerts, or discovery;
- purchase, bid, or approve any opportunity.

Persistent task status is intentionally deferred until the database phase.
