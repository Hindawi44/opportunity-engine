# Search Provenance Integrity V1

This change closes reporting/learning provenance gaps without changing discovery behavior.

## Invariants

- Search requests added: **0**
- Page fetches added: **0**
- Providers added: **0**
- Sources added: **0**
- Markets added: **0**
- Runtime/agent added: **0**
- Exact-Lot evidence rules changed: **No**
- Top5 eligibility/order changed: **No**

## Truth contract

Every strict clothing Exact-Lot keeps two independent facts:

1. `search_provider = EXA`
2. `retrieval_provenance` is one of:
   - `DIRECT_SEARCH_RESULT`
   - `MULTI_HOP`
   - `PROVEN_ROUTE_RECOVERY`

`PROVEN_ROUTE_RECOVERY` means a remembered URL was used only as navigation memory and the public page was freshly fetched and passed the unchanged strict Exact-Lot evidence gate. It is not counted as a direct current-search discovery and receives no query/anchor success credit.

Search reports separately expose:

- `current_exa_discovery_strict_exact_lot_count`
- `freshly_reverified_recovery_exact_lot_count`
- `strict_exact_lot_count` as the verified total

The maturity gate requires the two provenance counts to be present and to sum exactly to the verified total for every fixed clothing market.

Manual Cost Guard skips remain `SKIPPED_COST_GUARD` in the six-market ledger when no source actually ran; they are never represented as a valid zero search.
