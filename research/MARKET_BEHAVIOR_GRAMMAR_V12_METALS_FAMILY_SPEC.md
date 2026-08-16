# MARKET BEHAVIOR GRAMMAR V12 — METALS FAMILY-SPECIFIC GRAMMAR

Status: FROZEN SPECIFICATION BEFORE RESULTS
Date: 2026-08-16

## Research boundary
This test continues from V10/V11/V11B. It does not reopen V1–V10 and does not attempt to rescue the failed universal S0 -> 12h continuation rule by excluding assets after observing Forward OOS results.

## Family under test
- GOLD
- SILVER

Equal asset weight: 50% GOLD / 50% SILVER.

## Frozen inputs
1. Reuse the exact V10 state definitions S0–S5.
2. Reuse the exact causal state assignment rules from V10.
3. Reuse the exact V11B 12h response definition and execution/measurement convention.
4. Do not re-cluster, re-label, alter thresholds, or change the response horizon after seeing results.
5. The already-observed Forward OOS interval 2026-04-26 through 2026-08-16 is development evidence now and cannot be reused as a fresh final OOS test.

## Hypothesis
For at least one V10 state S_i, the conditional 12h response distribution within Metals is more informative and temporally stable than the Metals family baseline.

P(Response_12h | S_i, Metals) != P(Response_12h | Metals)

The goal is not to find the best state after inspection. All S0–S5 are evaluated as one predeclared family of hypotheses.

## Estimation
For each state S0–S5 and each asset:
- count observations
- estimate the 12h response distribution using Bayesian smoothing
- compare against that asset/family baseline
- compute effect size and predictive score

Family aggregation is equal-weight across GOLD and SILVER, not observation-weighted.

## Primary score
Out-of-sample predictive skill versus the Metals family baseline using log-loss / cross-entropy improvement.

Secondary diagnostics:
- mean directional response
- posterior probability of positive effect
- per-asset effect
- temporal-window consistency
- sample support

## Minimum support / backoff
If a state lacks adequate support under the pre-existing V10/V11B support convention, it is not promoted. It backs off to the Metals family baseline. No state is rescued by lowering support after inspection.

## Multiplicity
S0–S5 are one hypothesis family. Apply a family-wise multiplicity correction (Holm or the same correction convention used by the preceding grammar research). A state cannot be declared qualified from an unadjusted p-value alone.

## Qualification gates
A Metals state rule qualifies only if ALL are true:
1. sample-support gate passes under the frozen support convention
2. equal-weight family predictive skill is positive
3. GOLD predictive skill is positive
4. SILVER predictive skill is positive
5. temporal stability gate passes
6. multiplicity-adjusted significance/evidence gate passes
7. effect direction is not dependent on one asset dominating observation count

Otherwise the state is classified as NOT_STABLE / NOT_SUPPORTED.

## Anti-overfitting locks
Forbidden after results:
- deleting GOLD or SILVER
- testing only the better metal
- changing S0–S5 definitions
- changing 12h to another horizon
- changing thresholds
- choosing only the best temporal window
- redefining the baseline
- calling the previously observed 2026-04-26 to 2026-08-16 interval fresh OOS

## Decision labels
- METALS_FAMILY_GRAMMAR_SUPPORTED_V12
- METALS_FAMILY_GRAMMAR_PARTIAL_V12
- NO_STABLE_METALS_FAMILY_GRAMMAR_V12

"PARTIAL" is diagnostic only and is not a production rule.

## Next independent test if V12 produces a survivor
Freeze the surviving Metals rule(s), then replicate on genuinely unseen older history that has not been used to choose states, horizons, thresholds, or family membership.

## Next family after Metals
US Indices:
- US100 / NAS100
- US30

Reuse the exact same V10 state definitions and V11B response convention before seeing index-family results.
