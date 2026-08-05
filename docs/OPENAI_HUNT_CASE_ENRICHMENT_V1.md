# OPENAI_HUNT_CASE_ENRICHMENT_V1

## Product purpose

Add a bounded reasoning layer above the existing market-signal radar for clothing inventory, store closure, warehouse surplus, auction, insolvency, and liquidation signals in Norway, Sweden, and Germany.

This change does not rebuild the engine. It reuses the current `MarketSignalRecord`, domain market-intelligence bulletin, SQLite signal continuity, direct collectors, Brave radar, Gmail intake, lifecycle classifier, human review, and one-opportunity analysis path.

## Bounded flow

1. Select at most 10 active early signals from the existing bulletin.
2. Use `gpt-5.6-luna` once to propose candidate hunt cases.
3. Validate every proposed link against exact source fields already present in the signals.
4. Use `gpt-5.6-terra` for at most the two highest-priority cases.
5. Write a JSON artifact and an Arabic operator summary.
6. Attach a compact advisory summary to the existing domain bulletin.

The maximum is three OpenAI API requests per checkpoint run.

## Strict Structured Outputs compatibility

Pydantic fields with defaults are optional in its generated JSON Schema. OpenAI strict Structured Outputs require every object property to be listed in `required` and require `additionalProperties: false` for each object. The checkpoint normalizes the two hunt-case schemas before sending them to the Responses API, removes Pydantic-only `default` and `title` metadata, and keeps Pydantic validation after the response returns.

This correction addresses the first live run's HTTP 400 schema rejection without changing signal selection, lifecycle state, opportunity promotion, or automatic-action safety.

## Trust boundary

OpenAI output is advisory and is never a source of truth. The model cannot:

- create or promote an opportunity;
- make an item Top 5 or analysis eligible;
- verify an organisation number that is absent from source evidence;
- claim a sale, liquidator, warehouse, auction, quantity, or price without evidence;
- contact, bid, buy, reserve, or pay.

Exact organisation-number matches, exact normalized legal-name matches, same legal name and location, and exact related-opportunity identifiers remain programmatic checks.

## Cost boundary

Default environment policy:

```text
OPENAI_HUNT_TRIAGE_MODEL=gpt-5.6-luna
OPENAI_HUNT_DEEP_MODEL=gpt-5.6-terra
OPENAI_HUNT_MAX_SIGNALS=10
OPENAI_HUNT_MAX_DEEP_CASES=2
OPENAI_HUNT_MAX_API_REQUESTS=3
OPENAI_HUNT_MAX_ESTIMATED_COST_USD=0.16
```

The per-run ceiling is designed around a 5 USD monthly target when the checkpoint runs at most once per UTC day. The artifact records token usage and an estimated standard-price cost. OpenAI Platform billing remains the source of truth.

## Failure behavior

- Missing `OPENAI_API_KEY`: `SKIPPED_NO_API_KEY` and the existing bulletin still succeeds.
- No eligible early signals: `NO_ELIGIBLE_SIGNALS` and zero API calls.
- Projected request exceeds the cost guard: `SKIPPED_BUDGET_GUARD`.
- Triage API or schema failure: `FAILED`, with a sanitized error artifact; existing collectors and bulletin remain available.
- One deep-analysis failure: only that case is marked `FAILED`; the triage result remains.

## Artifacts

```text
openai-hunt-case-enrichment.json
openai-hunt-case-enrichment.txt
domain-market-intelligence-brief.json  # includes compact hunt_case_intelligence
```

No prompt includes API keys. Responses are sent with `store: false` and strict JSON Schema Structured Outputs.
