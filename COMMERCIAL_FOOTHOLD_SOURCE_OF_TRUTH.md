# Commercial Foothold — Source of Truth

**Permanent entrypoint for the commercial-learning phase.**

Any new session or operator working on post-search commercial learning must start here instead of rebuilding the method from memory or conversation history.

## Current phase

```text
Search Engine V1: FROZEN
Commercial phase: HUMAN-LED LEARNING
Automation level: NONE for commercial BUY/REJECT
```

Search Engine V1 is not reopened unless there is a proven regression or a proven Exact-Lot miss.

## Mandatory commercial sequence

```text
Find Deal
→ Identify Exit Routes
→ Identify Downstream Buyers
→ Estimate Absorbable Quantity
→ Gather Price Evidence
→ Measure Friction
→ CONTINUE / NEED_EVIDENCE / STOP
→ Record Commercial Lesson
→ Update Foothold Hypothesis
```

## Canonical files

1. Method / rules:
   `docs/COMMERCIAL_FOOTHOLD_LEARNING_LOOP_V0.md`

2. Persistent case history:
   `docs/COMMERCIAL_FOOTHOLD_CASE_LEDGER_V0.md`

The ledger is append-only in spirit: do not restart case numbering, discard previous lessons, or replace unknowns with assumptions.

## Foothold states

```text
NONE
WEAK
EMERGING
REPEATED
PROVEN
```

A foothold is not PROVEN from web research alone. PROVEN requires our own quote, reservation, repeat inquiry, or transaction evidence.

## Evidence rule

```text
E0 — assumption only
E1 — buyer claim
E2 — quantified buyer / stated conditions
E3 — operational evidence
E4 — published transaction evidence
E5 — our own quote / transaction evidence
```

A normal shop is not a buyer merely because it exists.
An asking price is not a clearing price.
Unknown remains `UNKNOWN`.

## Session-start rule

Before studying any new opportunity:

1. Read this file.
2. Read `docs/COMMERCIAL_FOOTHOLD_LEARNING_LOOP_V0.md`.
3. Read the latest entries in `docs/COMMERCIAL_FOOTHOLD_CASE_LEDGER_V0.md`.
4. Continue with the next case number.
5. Reuse previous buyer, price, friction and foothold lessons unless new evidence contradicts them.

## Current first case

Case 001 is the approximately 3,600-pair footwear stock in Norway.

Its purpose is not to force a purchase decision. It is the first live case used to test whether a repeatable downstream foothold emerges.

## Guardrail

Do not build a larger commercial engine, scoring system, runtime, or automated buying logic until repeated real cases show a stable foothold worth automating.
