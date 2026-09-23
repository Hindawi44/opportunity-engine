# Norway search recovery — 2026-09-22

Operator request: keep `Hindawi44/opportunity-engine`, stop non-Norwegian execution and recover existing Norwegian search, exact links, human review and learning where safe. Do not rebuild the project or discard history.

## Reuse, not replacement

- `scripts/run_cross_source_clothing_verification.py` — established free Norway cross-source route (Konkurs.app + Auksjonen, Vareauksjonen and Auksjoner.no). Already reconnected in #913. Its `live-clothing-top5.json` is a strict verified-sale subset, **not** the full discovery log; preserve source-level findings, unmatched leads, and failures separately. Clothing-focused, not all sectors.
- `scripts/run_norway_direct_sales.py` — existing Norway-only **all-assets** public Auksjonen search with exact individual item-page verification. Restore as a separate bounded read-only report. A direct active listing is a **research candidate**, not a confirmed bankruptcy estate, ownership, purchasable inventory or buying recommendation. The endpoint may fail; show failures and report incomplete coverage.
- `scripts/run_norway_insolvency_sample.py` and related September prototype — useful experimental event/entity evidence, but repeatedly failed to produce actionable sale links in a small sample. Pause its PR job to remove duplicated network requests; retain code, tests, commits and historical artifacts.
- Archived `docs/archive/legacy-six-market-checkpoint-20260919.yaml.txt` shows original Norway Exa Exact-Lot, Auksjonen, FINN Gmail, cross-source verification, search-success learning, reviews and SQLite restoration. Those implementations remain in the repository. Exa/Brave/OpenAI and Gmail remain paused. Norway-only SQLite continuity is restored through the existing checkpoint mechanism after backup/integrity verification; foreign databases and old cross-market learning overlays are not restored into the active Norway cycle. History is not deleted or reset.

## Current safe execution and limits

Pull requests verify the bounded search and review cycle. A main-branch push for the relevant Norway review/search files also creates the next durable checkpoint; there is still no daily schedule. Run the existing Norway all-asset direct item search (maximum two API pages and ten item cards) and keep the bounded cross-source verifier separate. No foreign-market execution, paid API keys, Gmail reads, contacts, bids, purchases or automatic commercial decisions. Retain raw artifacts per source and distinguish `direct_candidates` from `verified_bankruptcy_sales`; do not convert an API failure into a claim of no opportunities. This is **not** comprehensive coverage of Norway.

## Review, SQLite and learning continuity — verified 2026-09-23

- Reuse the existing `operator_listing_decisions` contract for explicit **STUDY / DELETE / LATER** actions. The event bridge requires `EXPLICIT_USER`, an exact persisted opportunity identity and the exact persisted source URL before it commits anything.
- Restore only allow-listed `no-*` SQLite databases from the prior durable checkpoint. The verified recovery restored `no-auksjonen`, `no-finn-email` and `no-exa-exact-lot`; zero foreign databases and zero cross-market learning overlays were restored.
- Persist today's verified direct Auksjonen item links into the existing `no-auksjonen/opportunity_engine.db` through the canonical unified persistence path before review-memory reconciliation.
- Keep legacy `human_review_outcomes` unchanged and separate from STUDY/LATER semantics. Two historical Norway review rows were preserved in the verified recovery. They are not silently converted into new operator decisions.
- Filter the Git-tracked review-event file for the Norway cycle rather than deleting foreign history. The verified run saw five existing foreign events, ingested none of them, and preserved them in repository history.
- Export review memory from SQLite and build the human review queue with the existing logic: exact DELETE suppresses only that review identity, STUDY remains bookmarked, and LATER remains deferred. Only explicit persisted decisions are learning evidence.
- Learning is restored in **review-only** form: transparent STUDY/DELETE counts and patterns may be emitted, but they cannot automatically activate queries, providers, source exclusions or paid search. With no explicit Norway STUDY/DELETE/LATER event yet, the verified memory correctly reports zero current Norway decisions.
- SQLite integrity is checked during the cycle. The verified recovery reported `PRAGMA quick_check = ok` for all three restored Norway databases.

The first end-to-end human feedback proof after this recovery is therefore one explicit Norway listing decision followed by the next checkpoint, where the same decision must still be present in SQLite and reflected in the review queue without changing unrelated source history.
