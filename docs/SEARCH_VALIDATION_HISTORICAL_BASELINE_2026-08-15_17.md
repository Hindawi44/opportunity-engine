# SEARCH VALIDATION HISTORICAL BASELINE — 2026-08-15 to 2026-08-17

## Evidence set

This baseline uses three already-completed **scheduled** Multi-Market Daily Operator Checkpoint runs. No new search was launched for this analysis.

| Date (UTC) | Workflow run | Run ID | Saved artifact ID |
|---|---:|---:|---:|
| 2026-08-15 | #141 | 31867450584 | 9242510435 |
| 2026-08-16 | #156 | 31929596808 | 9258951093 |
| 2026-08-17 | #190 | 31999200672 | 9278007503 |

All three workflow runs completed successfully. That execution success is treated only as evidence that the pipeline ran; it is not itself Search proof.

## Critical identity finding

Auksjonen contains one verified active clothing-inventory opportunity on all three days, but it is the **same opportunity** each time:

```text
object_id = 619341
Halv pall med Bauer jakker – assorterte modeller, farger og størrelser
current bid observed = 250 NOK
```

Therefore:

```text
verified_active_run_count = 3
distinct_verified_active_identity_count = 1
```

Under the V1.1 integrity correction, Auksjonen is **NOT_PROVEN**, not `PROVEN`. Re-observing one active lot across three days proves continuity, but not repeated discovery breadth.

## Core-source diagnosis

### Norway

- `Auksjonen Public API`: 3/3 productive runs and 3/3 verified-active runs, but only **1 distinct verified opportunity** -> `NOT_PROVEN`.
- `Brave Search market signal radar`: productive on all three runs, but **0 verified-active leads** -> `NOT_PROVEN`.
- Norway cross-source checkpoint: 3 runs, no accepted/verified actionable search lead -> `NOT_PROVEN`.

**NO market verdict: `NOT_PROVEN`.**

### Sweden

- `blinto.se`: present in all 3 runs; paid-request accounting = 24 requests; retrieval succeeded, but **0 strong verified-active leads** -> `NOT_PROVEN`.
- `Brave Search market signal radar`: signals flowed, but **0 verified-active leads** -> `NOT_PROVEN`.
- `psauction.se`: only 1 of the three scheduled evidence runs contains the direct daily source; 21 strong leads in that run, **0 confirmed active sales** -> `INSUFFICIENT_EVIDENCE`.
- `klaravik.se`: only 1 evidence run and 0 verified-active sales -> `INSUFFICIENT_EVIDENCE`.

**SE market verdict: `INSUFFICIENT_EVIDENCE`.**

### Germany

- `DEUTSCHE_PFANDVERWERTUNG_ACTIVE_AUCTIONS`: 3 runs, 0 productive/verified-active leads -> `NOT_PROVEN`.
- `RIEGERMANN_ACTIVE_AUCTIONS`: 3 runs, 0 productive/verified-active leads -> `NOT_PROVEN`.
- `VENTA_ACTIVE_AUCTIONS`: 3 runs, 0 productive/verified-active leads -> `NOT_PROVEN`.
- German Brave market-signal radar: productive signals, but 0 verified-active leads -> `NOT_PROVEN`.
- `sen-sen.de`: only 1 evidence run -> `INSUFFICIENT_EVIDENCE`.

**DE market verdict: `INSUFFICIENT_EVIDENCE`.**

## Overall Search verdict

With required core markets `NO / SE / DE`:

```text
NO = NOT_PROVEN
SE = INSUFFICIENT_EVIDENCE
DE = INSUFFICIENT_EVIDENCE

OVERALL = NOT_PROVEN
progression_gate_open = false
next_stage_authorized = null
```

This does **not** delete or invalidate downstream code. It means the Search/Discovery layer has not yet earned permission to justify new downstream development.

## Cost conclusion

This diagnosis reused saved artifacts only:

```text
new Brave requests = 0
new OpenAI requests = 0
new source-site requests for this analysis = 0
```

The next work should target the failing Search evidence itself, not Math, Language, or another downstream layer. Additional manual full-market runs are not required to reach this historical diagnosis.
