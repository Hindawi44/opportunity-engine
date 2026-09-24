# Norway search recovery — 2026-09-22

Operator request: keep `Hindawi44/opportunity-engine`, stop non-Norwegian execution and recover existing Norwegian search, exact links, human review and learning where safe. Do not rebuild the project or discard history.

## Reuse, not replacement

- `scripts/run_cross_source_clothing_verification.py` — established free Norway cross-source route (Konkurs.app + Auksjonen, Vareauksjonen and Auksjoner.no). Already reconnected in #913. Its `live-clothing-top5.json` is a strict verified-sale subset, **not** the full discovery log; preserve source-level findings, unmatched leads, and failures separately. Clothing-focused, not all sectors.
- `scripts/run_norway_direct_sales.py` — existing Norway-only **all-assets** public Auksjonen search with exact individual item-page verification. Restore as a separate bounded read-only report. A direct active listing is a **research candidate**, not a confirmed bankruptcy estate, ownership, purchasable inventory or buying recommendation. The endpoint may fail; show failures and report incomplete coverage.
- `scripts/run_norway_insolvency_sample.py` and related September prototype — useful experimental event/entity evidence, but repeatedly failed to produce actionable sale links in a small sample. Pause its PR job to remove duplicated network requests; retain code, tests, commits and historical artifacts.
- Archived `docs/archive/legacy-six-market-checkpoint-20260919.yaml.txt` shows original Norway Exa Exact-Lot, Auksjonen, FINN Gmail, cross-source verification, search-success learning, reviews and SQLite restoration. Those implementations remain in the repository. The operator clarified on 2026-09-24 that Gmail and paid/model tools were never meant to be disabled; the restriction is geographic. Exa, bounded Brave fallback, FINN Gmail intake and bounded OpenAI hunt analysis are therefore restored only inside the Norwegian route. Norway-only SQLite continuity remains the durable state path; foreign databases and old cross-market learning overlays are not restored into the active Norway cycle. History is not deleted or reset.

## Current safe execution and limits

Pull requests verify the bounded search and review cycle without spending paid search/model budget. Production runs execute once daily at 06:47 Europe/Oslo, and may also be manually dispatched. The active Norway route combines the existing all-asset Auksjonen direct collector with the original Auksjonen clothing path, Exa Exact-Lot search for `--market NO`, its bounded Brave fallback, read-only FINN Gmail intake, the free Norway cross-source verifier, SQLite review memory, and bounded OpenAI hunt analysis. No foreign-market execution, contacts, bids, purchases or automatic commercial decisions are allowed. Retain raw artifacts per source and distinguish direct candidates from verified bankruptcy-linked sales; do not convert an API/source failure into a claim of no opportunities. This is **not** comprehensive coverage of Norway.

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


## Norway-only tool restoration — 2026-09-24

The operator clarified the intended simplification: **stop foreign markets, not useful tools**.

- **Exa:** reuse the existing Exact-Lot runner with `--market NO` only and `--results-per-query 5`. Its Norwegian query pack remains the existing one; no SE/DE/FR/IT/NL invocation is present in the active workflow.
- **Brave:** remains the existing fallback inside the Exa route, with the runner's hard Norway-market fallback cap of one query / one outbound attempt when fresh Exa coverage is weak. Push/manual cost guards are explicitly enabled only in this Norway job.
- **FINN via Gmail:** restore the existing read-only Gmail bridge, bounded to 20 messages and the query `newer_than:14d from:agent@finn.no`. The resulting FINN records can now be persisted into the existing `no-finn-email/opportunity_engine.db` so human STUDY/DELETE/LATER review can survive later checkpoints.
- **OpenAI:** reuse the existing hunt-case enrichment, but feed it only current records from `no-auksjonen`, `no-exa-exact-lot`, and `no-finn-email`. The adapter fails closed if any record has a market other than `NO`. The production limit is two OpenAI requests and an estimated-cost guard of USD 0.08 per run.
- **Auksjonen:** keep both the broader all-assets direct collector and the original bounded clothing path; the latter supplies canonical persistence and FINN/Auksjonen cross-channel evidence.
- **Cross-source public verification:** keep the existing Konkurs.app/Auksjonen/Vareauksjonen/Auksjoner.no verifier active as a separate evidence path.
- **Human authority:** all of these tools may discover, verify, connect evidence, or propose follow-up research. None may automatically contact a seller, bid, reserve, purchase, pay, or convert OpenAI/Brave output into an operator decision.
