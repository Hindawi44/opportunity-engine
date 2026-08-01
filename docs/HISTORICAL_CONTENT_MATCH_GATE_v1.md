# Historical Evidence Content-Match Gate v1

## Decision

A verified ended item page enters `HISTORICAL_MARKET_EVIDENCE` only when the bounded public verification text itself proves matching bulk clothing inventory.

The following are not sufficient by themselves:

- listing title;
- search snippet;
- source-policy aliases;
- generic auction, financing, vehicle, transport, or seller boilerplate.

## Accepted path

The bounded verification text must contain both:

1. clothing or footwear inventory evidence; and
2. bulk or quantity evidence.

Accepted records receive:

- `verification_content_match=true`;
- `historical_market_evidence_eligible=true`;
- `historical_data_fields_trusted=true`.

## Mismatch path

An ended, stable, verified item page whose bounded content does not prove the advertised clothing lot receives:

- `opportunity_state=HISTORICAL_EVIDENCE_REQUIRES_MANUAL_REVIEW`;
- `verification_content_match=false`;
- `historical_market_evidence_eligible=false`;
- `historical_data_fields_trusted=false`;
- no current Top 5 or Analysis eligibility.

Title-derived inventory type and quantity are cleared before output. The record may be admitted to historical evidence only after alternate item-specific public evidence is reviewed.
