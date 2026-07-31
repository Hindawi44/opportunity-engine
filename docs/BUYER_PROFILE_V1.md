# Buyer Profile V1

`BuyerProfileV1` separates buyer-specific facts from market-wide rules.

The Norway market profile describes Norway for every buyer. The buyer profile
describes the specific operating point and constraints of one buyer. This keeps
Namsos, budget, shipping limits, storage capacity, and risk tolerance out of the
shared Norway configuration.

## Initial profile

The first profile is:

```text
config/buyers/mahmoud_namsos_v1.json
```

Confirmed values:

- profile: `MAHMOUD_NAMSOS_V1`
- buyer type: `BUSINESS`
- display name: `Namsos Skredderhus`
- home market: `NO_DOMESTIC_V1`
- city: `Namsos`
- country: `NO`
- settlement currency: `NOK`
- categories: `clothing_inventory`, `textiles`

Unknown values deliberately remain `null`:

- budget
- maximum purchase price
- maximum shipping cost
- minimum expected margin
- maximum total exposure
- maximum sell-through time
- storage and pickup capacity
- pallet-handling capacity
- risk tolerance
- postal code and exact coordinates

No value is inferred from unrelated project data.

## Matching readiness

Buyer Profile V1 is not yet a matching or scoring engine. Its snapshot reports
whether the minimum buyer constraints needed by a later matching engine are
known.

The initial profile returns:

```text
BLOCKED_MISSING_CONSTRAINTS
```

until these fields are supplied explicitly:

```text
commercial_constraints.budget_nok
commercial_constraints.maximum_shipping_nok
commercial_constraints.minimum_expected_margin_ratio
risk_policy.risk_tolerance
```

This does not block discovery. It blocks only buyer-specific qualification and
prevents a general market opportunity from being presented as suitable for this
buyer without sufficient evidence.

## Safety boundary

Buyer Profile V1:

- does not calculate landed cost;
- does not rank opportunities;
- does not change `final_decision`;
- does not change Top 5 or alerts;
- does not contact sellers;
- does not place bids;
- does not purchase automatically.

Verified seller identity, an active listing, and a complete landed-cost estimate
remain required before future buyer-specific qualification.

## Validation

Generate an auditable snapshot with:

```bash
PYTHONPATH=src python scripts/build_buyer_profile.py
```

Default output:

```text
data/buyer_profile_mahmoud_namsos_v1.json
```

The snapshot is additive and is not wired into the production decision pipeline
in V1.
