# Live Shadow Run 001 — 2026-08-18

## Purpose

First real-market validation after the Single-Owner Architecture V1 promotion.

Canonical chain under observation:

`Evidence -> Fact -> Lifecycle State/Eligibility -> Value -> Decision -> Observers`

This run is read-only learning/monitoring. It does not contact sellers, place bids,
purchase, reserve, or pay.

## Search scope

Norwegian FINN marketplace, with priority on clothing-store liquidation/closure
inventory and transportable store fixtures suitable for resale around Namsos.

Large, heavy, technical, vehicle, and impractical lots are excluded before Value.

## Ranked candidate

| Listing | Source | Current price | Expected total cost | Conservative resale value | Potential profit | Ease of sale | Risk | Maximum safe bid | Decision |
|---|---|---:|---:|---:|---:|---|---|---:|---|
| 2 round metal clothing racks on wheels, FINN 455975035 | FINN | 1,000 NOK for both | Unknown until Namsos logistics is quoted | 1,700 NOK | Unknown | Medium | High logistics uncertainty | Not actionable while transport is missing | MONITOR |

Only one listing had enough source detail in this first capture to justify a
financial shadow test. Other seen listings were either too heavy/large for the
Namsos resale profile or did not expose enough item-level evidence to promote
beyond Evidence review.

## Evidence — FINN 455975035

Observed listing facts:

- title: `2 stk. klesstativ rundt på hjul metall`
- asking price: 1,000 NOK for both together
- condition: `Pent brukt - I god stand`
- quantity: 2
- construction: round metal clothing racks on wheels
- approximate diameter: 80–90 cm each
- height: adjustable
- location: 1722 Sarpsborg
- seller statement: pickup/delivery in the Sarpsborg area
- FINN page offers a request-for-shipping action, but shipping to Namsos is not an explicit seller fact
- VAT treatment is not stated in the captured listing evidence
- transport to Namsos is not quoted

Source URL:

`https://www.finn.no/recommerce/forsale/item/455975035`

## Used-market comparisons

The same FINN page displayed these nearby asking-price references:

- round solid clothing rack: 1,000 NOK each
- round rack with wheels: 2,300 NOK each
- metal display/clothing rack: 750 NOK each

For pair-normalized comparison this gives 2,000 / 4,600 / 1,500 NOK.
The median pair ask is 2,000 NOK. The project Value convention uses a conservative
85% median anchor, giving 1,700 NOK. Because the spread is wide, confidence is LOW.

## Value / Decision observations

### Case A — transport unknown

Known purchase price is 1,000 NOK, but Namsos transport is missing.

Expected canonical behavior:

- Value carries `cost:transport_nok` as a blocker
- Decision = MONITOR
- `is_actionable = False`

This is the primary live verdict.

### Case B — artificial best case: zero logistics

This is a sensitivity bound, not a factual logistics quote.

- total cost: 1,000 NOK
- conservative resale: 1,700 NOK
- expected profit: 700 NOK
- ROI: 70%
- market confidence: LOW

Even under this unrealistic best case, canonical Decision must not become BUY,
because confidence is low and the project minimum-profit gate is not satisfied.
Expected result: MONITOR.

### Case C — 750 NOK extra-cost sensitivity

This is a sensitivity bound, not a transport estimate.

- total cost: 1,750 NOK
- conservative resale: 1,700 NOK
- expected profit: -50 NOK
- ROI: -2.86%

Expected result: REJECT.

The raw break-even room before any required profit/risk margin is only 700 NOK
(1,700 resale minus 1,000 purchase). Therefore a long-distance Namsos logistics
quote can invalidate the lot very quickly.

## Excluded example

A complete modern shop-fitting listing in Kristiansand was excluded before ranking:

- asking price around 49,000 NOK
- stated total weight: 1,105 kg
- intended for roughly 80–100 m² store/warehouse

It violates this monitoring profile's transport/storage simplicity requirement.

## Verdict

`LIVE_SHADOW_001 = PASS_SYSTEM_BEHAVIOR / NO_ACTIONABLE_OPPORTUNITY`

What the run proved:

1. Missing logistics remains missing; it is not converted to zero.
2. Value stays canonical and auditable.
3. Decision fails closed to MONITOR while a material cost is unknown.
4. A low acquisition price alone does not create a BUY.
5. Heavy remote fixtures are filtered before economic enthusiasm can promote them.

No policy or strategy change is justified from one live sample. Continue collecting
shadow cases before considering threshold calibration.
