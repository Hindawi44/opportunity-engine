# Norway Market Profile V1

## Purpose

`NO_DOMESTIC_V1` is the first market-specific boundary built above the unified
opportunity contract. It identifies Norway as a domestic NOK market and defines
which registries and policy references later tax, customs, logistics, risk, and
qualification engines must use.

The profile is descriptive and conservative. It does not calculate tax, customs,
transport, profit, ROI, or a final decision.

## Files

- `config/markets/no_v1.json`: checked-in Norway configuration.
- `src/opportunity_engine/markets/profile.py`: generic V1 validation and source
  registry reconciliation.
- `src/opportunity_engine/markets/norway.py`: Norway loader and snapshot builder.
- `scripts/build_norway_market_profile.py`: explicit validation/export command.

## Source truth

The profile does not copy mutable source statuses. It references:

- `config/source_expansion_plan.json` for the approved Norway source plan.
- `data/source_gap_matrix.json` for the current runtime status, access mode,
  configuration requirements, fetch count, and source error.

The build fails when the planned and runtime Norway source sets differ. This
prevents a missing source from being silently hidden.

Channels declared as `bankruptcy_lead` or `public_auction_event_lead` are exported
as `SIGNAL_ONLY`. They cannot act as direct proof of an active inventory sale.
Sources without a signal channel remain `REQUIRES_RECORD_VERIFICATION`; this does
not imply that their records are active or commercially qualified.

## Policy references

V1 contains policy identifiers and evidence requirements only:

- Tax: `NO_DOMESTIC_TAX_REFERENCE_V1`
- Customs: `NO_DOMESTIC_CUSTOMS_REFERENCE_V1`
- Logistics: `NO_DOMESTIC_LOGISTICS_ESTIMATE_V1`

No tax rate or percentage is embedded in the profile. Mutable rates must come
from a dated, authoritative rule source when a later calculation engine is built.
The domestic V1 profile does not support cross-border import calculations.

A later logistics engine must receive both listing origin and buyer destination.
The market profile deliberately does not hard-code Namsos or another buyer
location; that belongs in a separate Buyer Profile.

## Qualification boundary

The profile requires:

- `listing_status=ACTIVE`
- `verification_status=VERIFIED`
- a verified sale page
- documented price or bid basis
- documented VAT status
- documented logistics basis

Unknown costs block qualification. A source failure must not be interpreted as a
valid zero-opportunity result. Automatic purchase remains forbidden.

## Manual validation

```bash
PYTHONPATH=src python scripts/build_norway_market_profile.py
```

The command writes:

```text
data/norway_market_profile_v1.json
```

This generated snapshot is an audit view. It does not replace
`source_expansion_plan.json`, `source_gap_matrix.json`, or `final_decision`.
