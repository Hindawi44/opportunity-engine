# Sweden Search Foundation — CURRENT-FIRST V1

Status: **OFFLINE VALIDATED**. Sweden is still **NOT PROVEN** until independent live/scheduled evidence passes the frozen Search Validation Gate.

## Evidence that motivated the repair
Saved scheduled Run #190 showed:

- Blinto: 8 requests, 61 raw hits, 7 unique candidates reaching verification, all 7 ended/historical, 0 ACTIVE.
- Klaravik: 8 requests, 80 raw hits, 16 unique candidates reaching verification, all 16 ended/historical, 0 ACTIVE.
- PS Auction: stale-index verification-budget allocation was separately corrected in PR #555 while retaining the same 8-request discovery budget and exact-page lifecycle authority.

The failure pattern is stale-index dominance: broad indexed historical auction pages consume bounded candidate/verification capacity before current opportunities can be checked.

## Repair

Blinto and Klaravik now use one shared `SWEDEN_CURRENT_FIRST_V1` retrieval policy:

1. Two current-window/current-month queries occupy the first two slots.
2. The total query budget remains exactly 8.
3. Existing inventory queries remain bounded fallback coverage.
4. The underlying source prefetch still performs its global historical veto.
5. If a current-window candidate survives the source gate, unrelated generic indexed candidates are deferred for that run.
6. If current-window retrieval finds nothing, generic fallback remains available.
7. Duplicate exact source identities are exposed only once.
8. A current-window hit is **not** ACTIVE proof; exact public source-page verification remains authoritative.

## Identity integrity

- Blinto identity uses auction `occurrence_id` (or slug fallback), not only `object_id`, so a relisted object is not collapsed into an old occurrence.
- Klaravik identity uses its exact product-auction slug.

## Cost and safety

- Brave request budget: unchanged at 8 per targeted source.
- Verification budget: unchanged.
- Direct-source Brave freshness remains disabled; exact-page status is authoritative.
- Offline implementation/tests make no paid search calls.
- No bid, contact, purchase, payment, or automated commercial action is added.
- No Norway, Germany, Italy, or other-country logic is changed.

## Offline validation result

- Full repository pytest: **1899 passed, 0 failed** (1 unrelated deprecation warning).
- Pull-request live market jobs: skipped.
- Paid Sweden search used for implementation validation: **0**.

## Proof discipline

This repair does not declare Sweden PROVEN. Sweden still requires the frozen Search Validation Gate evidence from independent live/scheduled runs before the country can be closed.
