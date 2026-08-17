# MATHEMATICAL LOGIC SHADOW V1

## Purpose

Freeze the current opportunity-engine output as Baseline V0 and represent it mathematically before adding linguistic reasoning or choosing any probability law.

The sequence is intentionally strict:

`CURRENT PROJECT V0 -> MATH V1 -> LIVE VALIDATION -> LANGUAGE (only if Math succeeds) -> LAW/PROBABILITY DISCOVERY (only later)`

V1 is **descriptive and read-only**, not predictive. It must first show whether a mathematical representation improves our ability to understand the commercial funnel without changing production decisions.

## Input

The main case matrix is built from the existing:

- `unified-market-cases.json`

The existing expansion sidecars are also measured numerically from their current artifacts:

- Italy: Discovery -> Memory -> Follow-Up -> Exact Lot -> Qualification -> Financial-ready
- Netherlands: Discovery -> Memory -> Follow-Up
- France: Discovery -> Memory -> Follow-Up

This preserves the current architecture:

- Core opportunity markets: `NO / SE / DE`
- Expansion sidecars: `IT / NL / FR`
- Fabric procurement remains a separate segment.

## Mathematical representation

Each unified case receives a deterministic numeric feature row containing existing counts such as:

- item count
- evidence count
- evidence per item
- independent source count
- source URL count
- country count
- missing-information count
- risk-flag count
- quantity observations
- price observations
- required verification evidence count
- missing verification evidence count

V1 also defines one **unweighted six-dimensional readiness vector**:

1. source reference present
2. market identity present
3. evidence present
4. quantity present
5. price present
6. verification gate passed

From that vector it calculates only arithmetic facts:

- `known_dimension_count`
- `completeness_fraction = known / 6`
- `decision_distance = 6 - known`

These are not a probability and not a commercial score.

## What V1 deliberately does NOT do

- no LLM or linguistic interpretation
- no external API calls
- no feature weights
- no Bayesian/logistic/survival model
- no probability law selected
- no profit prediction
- no Top-5 change
- no primary human-action change
- no market-scope change
- no automatic contact, bid, reservation, purchase, or payment

The artifact explicitly records `decision_influence = NONE`.

## Baseline preservation

The artifact copies existing baseline fields for comparison only:

- priority class
- decision lane
- case status
- actionability score
- commercial strength
- source strength
- verification-gate result

Math V1 never writes them back to the project.

## Expansion-market funnels

For IT/NL/FR the shadow records stage counts and exact arithmetic conversion ratios. A ratio is `null` when its denominator is zero; V1 never invents a denominator or smooths a zero-result market.

## Success discipline

Merging V1 means only that the representation is technically valid. It does **not** mean the mathematical hypothesis succeeded commercially.

Before Language V2 is allowed, repeated live runs must provide evidence that Math V1 is useful for identifying where commercial conversion is lost and for separating cases nearer/farther from complete evidence without increasing false confidence.

If it does not add measurable value, Math V1 remains a disposable shadow and Baseline V0 stays authoritative.
