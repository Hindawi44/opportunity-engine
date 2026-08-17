# Sweden Search Foundation — CURRENT-FIRST V2

Status: **OFFLINE VALIDATED**. Sweden is still **NOT PROVEN** until independent live/scheduled evidence passes the frozen Search Validation Gate.

This file keeps its historical V1 filename so the project has one Sweden current-first reference instead of duplicate documents.

## Evidence that motivated V1

Saved scheduled Run #190 showed stale-index dominance:

- Blinto: 8 requests, 61 raw hits, 7 unique candidates reaching verification, all 7 ended/historical, 0 ACTIVE.
- Klaravik: 8 requests, 80 raw hits, 16 unique candidates reaching verification, all 16 ended/historical, 0 ACTIVE.
- PS Auction stale-index verification-budget allocation was separately corrected in PR #555.

V1 therefore moved two current-window queries to the front of the same bounded query pack.

## V1 live-proof flaw discovered

Post-fix live proof #561 exposed a second problem. Klaravik found a candidate from a current-window query, V1 treated that search provenance as enough to defer unrelated generic candidates, and exact-page verification then proved the supposed current candidate was **ENDED**.

That ordering was unsafe because a search-index snippet is never lifecycle authority. A current-query hit may be stale and must not suppress other identities before the public source page proves ACTIVE state.

## V2 repair

Blinto and Klaravik now use `SWEDEN_CURRENT_FIRST_V2_VERIFY_BEFORE_SUPPRESS`:

1. The total query budget remains exactly 8 per targeted source.
2. The first two slots remain current-window discovery hints.
3. Those two queries now target Swedish retail-liquidation language instead of mainly workwear/status snippets: `klädbutik`, `modebutik`, `butikslager`, `utförsäljning`, `avveckling`, `konkurs`, `restlager`, plus clothing/shoes/accessories terms.
4. The current month is expressed in Swedish page language, e.g. `augusti 2026`, rather than relying on `2026-08`.
5. Search queries no longer require phrases such as `Auktionen avslutas`, `Högsta bud`, or `Nuvarande bud`; indexed copies of those phrases can be stale.
6. Current-query identities are exposed first, but unrelated fallback identities remain available for verification.
7. Only an exact duplicate source identity is collapsed across the query pack.
8. Search provenance is explicitly **not ACTIVE proof**. Exact public source-page verification remains authoritative for ACTIVE/ENDED state.

## Identity integrity

- Blinto identity uses auction `occurrence_id` (or slug fallback), not only `object_id`, so a relisted object is not collapsed into old history.
- Klaravik identity uses its exact product-auction slug.

## Cost and safety

- Brave request budget: unchanged at 8 per targeted source.
- Verification budget: unchanged.
- Offline implementation/tests make no paid search calls.
- No bid, contact, purchase, payment, or automated commercial action is added.
- No Norway, Germany, Italy, or other-country logic is changed.

## Offline validation

PR #562 full repository pytest before this documentation-only update: **1899 passed, 0 failed** (1 unrelated deprecation warning). Live market jobs were skipped. No Brave request was used for the V2 implementation validation.

## Proof discipline

V2 repairs the Search mechanism; it does not declare Sweden PROVEN. Sweden still needs independent live evidence satisfying the frozen Search Validation Gate before the country can be closed.
