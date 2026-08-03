# Lifecycle Checkpoint Integration V1

This change connects the deterministic opportunity lifecycle and append-only SQLite
history to the existing three-market daily operator checkpoint.

## Runtime order

1. Restore allow-listed SQLite databases from the latest successful checkpoint
   artifact when one exists.
2. Run the existing Norway, Sweden, and Germany source paths without changing their
   discovery contracts.
3. Persist canonical records and append lifecycle events only for meaningful state
   vector changes.
4. Build the existing multi-market checkpoint.
5. Enrich the checkpoint with lifecycle stage counts, current-run transitions,
   promotions, terminal transitions, SQLite continuity, and exactly one human action.

## Truthful continuity

- `SINCE_PREVIOUS_SUCCESSFUL_CHECKPOINT` is reported only when at least one current
  persistence source successfully restored its prior SQLite database.
- `CURRENT_RUN_INITIALIZATION` is reported on a first run or when prior state cannot
  be restored.
- Initial snapshots are separated from real transitions.
- A missing or unavailable previous artifact does not fabricate history and does not
  stop the bounded discovery run.

## Safety

The integration does not contact a seller, bid, buy, reserve, pay, change scoring,
change Top 5 selection, rebuild a market, or add a fourth market.
