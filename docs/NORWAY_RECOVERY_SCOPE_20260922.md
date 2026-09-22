# Norway search recovery — 2026-09-22

Operator request: keep `Hindawi44/opportunity-engine`, stop non-Norwegian execution and recover existing Norwegian search, exact links, human review and learning where safe. Do not rebuild the project or discard history.

## Reuse, not replacement

- `scripts/run_cross_source_clothing_verification.py` — established free Norway cross-source route (Konkurs.app + Auksjonen, Vareauksjonen and Auksjoner.no). Already reconnected in #913. Its `live-clothing-top5.json` is a strict verified-sale subset, **not** the full discovery log; preserve source-level findings, unmatched leads, and failures separately. Clothing-focused, not all sectors.
- `scripts/run_norway_direct_sales.py` — existing Norway-only **all-assets** public Auksjonen search with exact individual item-page verification. Restore as a separate bounded read-only report. A direct active listing is a **research candidate**, not a confirmed bankruptcy estate, ownership, purchasable inventory or buying recommendation. The endpoint may fail; show failures and report incomplete coverage.
- `scripts/run_norway_insolvency_sample.py` and related September prototype — useful experimental event/entity evidence, but repeatedly failed to produce actionable sale links in a small sample. Pause its PR job to remove duplicated network requests; retain code, tests, commits and historical artifacts.
- Archived `docs/archive/legacy-six-market-checkpoint-20260919.yaml.txt` shows original Norway Exa Exact-Lot, Auksjonen, FINN Gmail, cross-source verification, search-success learning, reviews and SQLite restoration. Those implementations remain in the repository. Exa/Brave/OpenAI, Gmail and persisted memory/SQLite are **not** silently re-enabled: first verify credential permissions, budgets, backups and the NO-only routing contracts. History is not deleted or reset.

## Current safe execution and limits

Only pull-request verification, no schedule. Run the existing Norway all-asset direct item search (maximum two API pages and ten item cards) and the existing bounded Norway cross-source verifier separately. No foreign markets, paid API keys, Gmail reads, SQLite writes, contacts, bids, purchases or automatic decisions. Retain raw artifacts per source and distinguish `direct_candidates` from `verified_bankruptcy_sales`; do not convert an API failure into a claim of no opportunities. This is **not** comprehensive coverage of Norway, and automated learning is **not** restored by this PR.
