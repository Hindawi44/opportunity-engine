# Commercial Foothold — Source of Truth

**Permanent entrypoint for the commercial-learning phase.**

Any new session or operator working on post-search commercial learning must start here instead of rebuilding the method from memory or conversation history.

## Current phase

```text
Search Engine V1: FROZEN
Commercial phase: HUMAN-LED LEARNING
Operating mode: RESEARCH-ONLY
Automation level: NONE for commercial BUY/REJECT
Trading / purchasing: DISABLED
Buyer/seller outreach: DISABLED unless the user explicitly changes phase
Financial commitment: DISABLED
```

Search Engine V1 is not reopened unless there is a proven regression or a proven Exact-Lot miss.

The current goal is to build commercial knowledge and discover a repeatable foothold from real public evidence and accumulated cases. The project is **not yet in trading mode**.

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

During RESEARCH-ONLY mode, this sequence is analytical. It does not authorize purchase, bidding, contacting a seller, requesting a quote, reserving stock, or committing money.

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

During RESEARCH-ONLY mode, public evidence may move a hypothesis through NONE / WEAK / EMERGING / REPEATED, but it must not be promoted to operational trading readiness.

A later PROVEN commercial state requires explicit phase change by the user plus our own quote, reservation, repeat inquiry, or transaction evidence.

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

## Research-only guardrail

Until the user explicitly says the project is ready to move from research into commercial execution:

- do not contact sellers;
- do not contact buyers;
- do not request private quotations;
- do not bid in auctions;
- do not reserve inventory;
- do not negotiate a purchase;
- do not commit money;
- do not interpret a case as permission to trade;
- use public/historical/current market evidence to learn the market instead.

The output of a case in this phase is **knowledge**, not a transaction.

## Session-start rule

Before studying any new opportunity:

1. Read this file.
2. Read `docs/COMMERCIAL_FOOTHOLD_LEARNING_LOOP_V0.md`.
3. Read the latest entries in `docs/COMMERCIAL_FOOTHOLD_CASE_LEDGER_V0.md`.
4. Continue with the next case number.
5. Reuse previous buyer, price, friction and foothold lessons unless new evidence contradicts them.
6. Stay in RESEARCH-ONLY mode unless the user explicitly changes phase.

## Current first case

Case 001 is the approximately 3,600-pair footwear stock in Norway.

Its purpose is not to force a purchase decision or seller contact. It is the first live research case used to test whether a repeatable downstream foothold emerges from public evidence.

## Guardrail

Do not build a larger commercial engine, scoring system, runtime, automated buying logic, or execute commercial actions until repeated real cases show a stable foothold worth further development and the user explicitly changes phase.
