# Quote-to-Job Standardizer — Real Market Experiment

This is the first real MIND FORGE V2 market experiment for idea `idea-open-f68386fa98a3ff10`.

## Goal

Test whether small Norwegian businesses have recurring quote/scope ambiguity **and** whether that pain creates concrete action, not just positive comments.

## Sample

Use exactly five independent businesses. Suggested mix: plumber, electrician, painter, car repair, and cleaning company. Replace a category if needed, but keep five independent businesses.

For each contact, record three booleans in `experiment_outcome.json`:

- `problem_confirmed`: the business confirms recurring quote/scope ambiguity or equivalent operational pain.
- `concrete_commitment`: the business takes a real next step such as sending an anonymized real request, testing a pilot, booking a follow-up, giving a referral, sharing data, or expressing willingness to pay.
- `fatal_objection`: a regulatory, operational, trust, workflow, or economics blocker makes the proposed outcome impractical.

`notes` must contain the real observation. Do not count compliments as demand.

## Finalize

After all five contacts are complete, change `status` from `PENDING` to `COMPLETE` and replace the `lesson` placeholder.

Run:

```bash
python scripts/mind_forge_v2_experiment_outcome.py \
  experiments/quote_to_job_standardizer/experiment_outcome.json \
  --output experiments/quote_to_job_standardizer/learning_outcome.json
```

The script calculates the result automatically:

- PASS: at least 3 problem confirmations, at least 2 concrete commitments, and 0 fatal objections.
- FAIL: anything else.

The generated `learning_outcome.json` is directly compatible with `scripts/mind_forge_v2_learning_memory.py`.
