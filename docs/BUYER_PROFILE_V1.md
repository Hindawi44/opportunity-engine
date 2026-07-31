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

## Independent readiness stages

Buyer Profile V1 does not treat missing commercial limits as a global block.
The snapshot reports three independent readiness stages.

### Discovery

```text
DISCOVERY_READY
```

The confirmed categories and markets are enough to continue collecting,
classifying, and displaying relevant opportunities.

### Cost-estimation input

```text
COST_ESTIMATION_READY
```

The confirmed country, city (`Namsos`), and settlement currency are enough for a
future city-level estimate. The mode is explicitly:

```text
CITY_LEVEL_INPUT_ONLY
```

Missing postal code or coordinates reduce precision but do not stop discovery.
This status does not mean a landed-cost engine is enabled or that a transport
quote has been calculated.

### Personal qualification

The initial profile returns:

```text
PERSONAL_QUALIFICATION_PENDING
```

until these fields are supplied explicitly:

```text
commercial_constraints.budget_nok
commercial_constraints.maximum_shipping_nok
commercial_constraints.minimum_expected_margin_ratio
risk_policy.risk_tolerance
```

When all four are present, the status becomes:

```text
QUALIFICATION_READY
```

Missing values prevent only the final buyer-specific claim that an opportunity
fits Mahmoud's budget and risk policy. They do not reject the opportunity and do
not stop discovery or city-level cost-estimation inputs.

## Compatibility

The snapshot keeps `matching_readiness` as a compatibility view of the personal
qualification stage. Its pending status is
`PERSONAL_QUALIFICATION_PENDING`, not a global blocked state.

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
