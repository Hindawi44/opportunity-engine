# SEARCH VALIDATION GATE V1.1 — INTEGRITY CORRECTION

## Why this correction exists

The first replay over saved daily checkpoint artifacts exposed two proof-integrity loopholes in V1. Neither requires a new live search to diagnose.

### 1. Legacy query diagnostics

Older source adapters such as Blinto, Klaravik and PS Auction record per-query fields such as `raw_hits`, `accepted_hits` and `rejected_hits`, but do not always write an explicit `status=SUCCESS` field.

V1 interpreted those rows as attempted-but-unsuccessful queries. V1.1 counts a legacy row as successful only when:

- there is no explicit error; and
- the row contains numeric retrieval evidence.

Explicit `SUCCESS` / `PASS` remains authoritative. Explicit errors still fail closed.

### 2. Repeated identical opportunity is not independent proof

The Aug 15, Aug 16 and Aug 17 scheduled artifacts all contain the same Auksjonen clothing opportunity:

```text
object_id = 619341
Halv pall med Bauer jakker – assorterte modeller, farger og størrelser
```

The listing was active in all three saved runs. V1 could therefore count three verified-active runs and mark the source `PROVEN`, even though the evidence represented only one unique opportunity observed repeatedly.

That is not sufficient proof that the search layer repeatedly discovers new opportunities.

V1.1 therefore adds one pre-declared integrity requirement:

```text
min_distinct_verified_active_leads = 2
```

A source still needs the existing V1 conditions:

1. at least 3 independent live runs;
2. retrieval success rate >= 80%;
3. productive-run rate >= 50%;
4. verified-active evidence on at least 2 runs;
5. complete paid-request accounting for paid search;
6. at least 2 distinct verified-active opportunity identities.

The sixth rule is an identity-integrity correction, not a commercial-score adjustment. The same listing repeated across days counts toward continuity, but it cannot alone prove discovery breadth.

## Identity evidence

The correction reads identity only from saved source artifacts. It prefers stable IDs and falls back to canonical public URLs. For current Auksjonen artifacts, `object_id` is available directly.

If a source claims verified-active leads but the saved artifacts contain no stable identity evidence, the source is marked `INSUFFICIENT_EVIDENCE` rather than guessing an identity.

## Cost and safety

V1.1 remains fully offline:

```text
external_api_calls = false
brave_requests = 0
```

It does not call Brave, OpenAI, source websites, or browser automation. It does not modify Top 5, scoring, verification, bidding, purchasing, payment, or seller contact.
