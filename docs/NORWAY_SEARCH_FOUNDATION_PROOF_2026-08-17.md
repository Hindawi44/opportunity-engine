# Norway Search Foundation Proof — 2026-08-17

## Decision

**NORWAY SEARCH = PROVEN**

This proof closes the Norway search-foundation stage only. It does not assert that every day must contain a commercial opportunity, and it does not authorize automatic contact, bidding, purchasing, or payment.

## Governing validation policy

The proof uses the Search Validation Gate integrity rules already in the repository:

- minimum live runs: 3
- minimum retrieval success rate: 80%
- minimum productive run rate: 50%
- minimum verified ACTIVE runs: 2
- minimum distinct verified ACTIVE identities: 2
- the same listing repeated across days cannot count as distinct proof

PR #556 (`Fix Norway official-source search validation`) was merged before this proof so that the Gate can also read the existing Vareauksjonen and Auksjoner.no canonical artifacts. Merge commit: `d34938dae67176a2b5c0c64b4b64ff5b2701eb34`.

## Auksjonen live evidence

Ten independent scheduled production artifacts from 2026-08-08 through 2026-08-17 were replayed offline. The source artifact was `auksjonen-live-clothing-listings.json` in each run.

| Date | Workflow run | Items received | Verified ACTIVE inventory lots |
|---|---:|---:|---:|
| 2026-08-08 | 31242766793 | 62 | 3 |
| 2026-08-09 | 31297775094 | 63 | 3 |
| 2026-08-10 | 31361688367 | 40 | 2 |
| 2026-08-11 | 31463704518 | 50 | 1 |
| 2026-08-12 | 31570931890 | 57 | 0 |
| 2026-08-13 | 31674926935 | 67 | 0 |
| 2026-08-14 | 31777136255 | 66 | 1 |
| 2026-08-15 | 31867450584 | 69 | 1 |
| 2026-08-16 | 31929596808 | 65 | 1 |
| 2026-08-17 | 31999200672 | 59 | 1 |

All ten Auksjonen artifacts completed retrieval without source errors.

## Distinct verified ACTIVE identities

The replay produced four distinct object identities that were ACTIVE inventory lots at the time of their live run:

1. `528194` — 10 stk GSA multinorm arbeidsplagg — 9 kjeledresser + 1 jakke — Str. 62 (2XL)
2. `574647` — Parti Björnkläder arbeidsklær og varselklær
3. `574794` — Parti med Blåkläder varselgensere og Clique T-skjorter
4. `619341` — Halv pall med Bauer jakker — assorterte modeller, farger og størrelser

The Bauer object is repeated across several later runs but is counted only once as a distinct identity.

## Gate metrics

- live run count: **10**
- retrieval success rate: **100%**
- productive run count: **8/10**
- productive run rate: **80%**
- verified ACTIVE run count: **8**
- distinct verified ACTIVE identity count: **4**
- paid Brave requests used for this proof replay: **0**

Every required threshold passes. Therefore the Auksjonen source verdict is **PROVEN**, which makes the Norway market Search verdict **PROVEN** under the current Gate rules.

## Independent current sanity check

A temporary diagnostic PR #557 ran the existing public Auksjonen scanner once on 2026-08-17 with no Brave or OpenAI secrets. Workflow run `32033285995` completed successfully and again returned current object `619341` (Bauer). The temporary PR was closed without merge, so no diagnostic workflow was added to `main`.

## Other Norway sources

The saved 2026-08-15 through 2026-08-17 artifacts for Vareauksjonen and Auksjoner.no completed their bounded scans but contained no qualifying ACTIVE clothing inventory lot during those runs. This does not invalidate Norway Search proof because Auksjonen independently passes every source-level proof threshold.

FINN saved-search intake also contained no qualifying records in the reviewed window; no FINN result was used to manufacture this verdict.

## Closure rule

Norway Search Foundation is closed as **PROVEN**. Do not reopen or rebuild Norway merely because a future daily run legitimately returns zero opportunities. Reopen the foundation only for a demonstrated regression such as retrieval failure, broken canonical ACTIVE verification, identity-accounting failure, or a material source-contract change.

The next country must be handled as a separate factory and must earn its own proof before progression.
