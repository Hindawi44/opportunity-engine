# Existing Norway search engine recovery — 2026-09-21

This is **not** a new engine. The archived original operator workflow is retained at `docs/archive/legacy-six-market-checkpoint-20260919.yaml.txt` and the underlying Norwegian code remains in the repository. It previously ran the Norwegian Exa Exact-Lot search, Auksjonen native inventory listings, FINN email intake, and the Konkurs.app/Auksjonen/Vareauksjonen/Auksjoner.no cross-source verifier; separate stages handled search-success learning and historical SQLite state.

The September 20–21 insolvency-first pilot is only a limited diagnostic. Its zero sale count is not the old engine's yield and not evidence that the Norwegian market is empty.

## Recovery in this change

Put the pre-existing `scripts/run_cross_source_clothing_verification.py` back into the PR-only Norway workflow with bounded Norway-specific parameters and preserve its native multi-source evidence. It uses no paid search or AI and does not mutate SQLite. Its incomplete scans/errors remain explicit; never convert an error to a claimed zero opportunity. Keep the newer official registry experiment separately as a supplementary diagnostic, not the replacement for the original sources. No cron or other countries.

## Retained but not yet reactivated

The original Exa/Brave search needs explicit cost controls before resuming; FINN Gmail needs safe credential/authorization validation. Learning and SQLite state writes require proof of a restorable historical backup. The existing original cross-source runner is **clothing-focused**, not all-sector coverage: wider Norwegian sectors should reuse existing provider/verifier interfaces after measuring the recovered baseline instead of creating another engine. Never treat a marketplace's bankruptcy claim as proof of company ownership, actual inventory, or an open sale. No contacting sellers, bids, purchases or business decisions.
