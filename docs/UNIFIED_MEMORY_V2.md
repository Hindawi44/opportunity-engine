# UNIFIED_MEMORY_V2

## Purpose

`UNIFIED_MEMORY_V2` is the persistent memory layer above `Unified Learning Spine V1`.

The Spine answers what evidence exists in the current run in one canonical contract. Memory V2 answers across daily checkpoints:

- What did we search?
- What did we find?
- What succeeded?
- What failed?
- Why did it fail?
- Which route repeated successfully?
- Which evidence is genuinely new?
- Which pattern is now repeated or proven?
- Has that pattern been converted into an explicit fixed rule?
- Does this pattern still need AI assistance?

It does not rebuild collectors, search providers, the Market Intelligence River, or the Spine.

## Runtime position

```text
Sources
→ Discovery
→ Verification
→ Unified Market Intelligence River
→ same-run bounded learning
→ Unified Learning Spine V1
→ UNIFIED MEMORY V2
→ Learning Layer review
```

The existing Spine atexit handler writes the Spine first and then Memory V2. The Learning Layer handler remains the final review plane.

## Persistent state

The durable file is:

```text
artifacts/multi-market-inputs/learning/unified-memory-v2.json
```

It is uploaded inside the existing daily checkpoint artifact and explicitly allow-listed for restoration on the next scheduled/manual checkpoint. No repository file is mutated during daily learning.

## Inputs

Memory V2 reads:

```text
checkpoint/unified-learning-spine.json
inputs/learning/unified-memory-v2.json
config/learning/unified-memory-rule-registry-v2.json
```

The prior memory is optional on the first run.

## Evidence memory

Every canonical Spine record is remembered by `learning_evidence_id` with its market, project domain, source/provider, query, URL, outcome, miss reason, route, source identity, first/last checkpoint run, bounded run observations, supporting run ids, and latest metadata.

The same checkpoint run is idempotent: replaying the same run id does not create another independent observation.

## Query memory

Queries are grouped by:

```text
market + provider + exact query
```

The memory retains routes, source identities, observed outcomes, and checkpoint-run counts. This is the deterministic answer to “what did we search?”

## Pattern memory

V2 derives three conservative deterministic pattern types.

### ROUTE_SUCCESS

Identity:

```text
market + project domain + provider + route + source identity
```

Example:

```text
FR → CLOTHING_INVENTORY → Exa → AGGREGATE_CHILD → friptadium.com
```

A route is `PROVEN` only when Search Success already marks it `REPLICATED_FOR_REVIEW` or independent supporting runs reach the replication threshold. Memory V2 does not weaken the existing Search Success proof gate.

### MISS_REASON

Identity:

```text
market + project domain + miss reason
```

A miss pattern is `PROVEN` only when at least two distinct missed-evidence cases span at least two checkpoint runs. One old case merely surviving across days is not enough.

### SOURCE_OUTCOME

Identity:

```text
market + project domain + source + result type + outcome
```

A source/outcome pattern is `PROVEN` only when at least two distinct evidence items span at least two checkpoint runs. This remains evidence for review, not automatic source promotion.

## New evidence

Each checkpoint records:

```text
new_evidence_count
new_evidence_ids
reobserved_evidence_count
reobserved_evidence_ids
```

“New” means the evidence id was first seen in the current checkpoint run.

## Fixed-rule conversion

Pattern recognition and code/rule conversion are deliberately separate. Memory V2 never edits code.

The explicit registry is:

```text
config/learning/unified-memory-rule-registry-v2.json
```

Only an `ACTIVE` registry entry with a matching `pattern_key` marks a pattern:

```text
converted_to_rule: true
rule_review_status: FIXED_RULE_ACTIVE
```

Without that explicit mapping, a proven pattern remains:

```text
converted_to_rule: false
rule_review_status: READY_FOR_RULE_REVIEW
```

The intended progression is:

```text
novel evidence
→ repeated pattern
→ proven pattern
→ reviewed rule design
→ explicit deterministic rule
→ registry marks conversion
```

There is no automatic code change.

## AI-dependence state

Memory V2 does not call OpenAI or any other model. It records only the role still needed for a pattern:

```text
AI_USEFUL_FOR_NOVEL_OR_UNPROVEN_CASE
AI_OPTIONAL_FOR_RULE_DESIGN
FIXED_RULE_HANDLES_PATTERN
```

The corresponding boolean is `ai_still_needed`. It becomes false only when an explicit active fixed-rule registry entry exists.

This supports the long-term project goal: use AI as a temporary teacher for new/complex cases, then move repeated proven reasoning into deterministic code.

## Safety boundary

Memory V2 requires Spine domain gating and retains only:

```text
CLOTHING_INVENTORY
FABRIC_PROCUREMENT
```

The following remain false:

```text
automatic_query_activation
automatic_provider_activation
automatic_source_promotion
automatic_code_change
production_query_mutation
production_mutation
automatic_contact
automatic_bid
automatic_reservation
automatic_purchase
automatic_payment
```

If the current Spine violates these invariants, Memory V2 fails closed and does not overwrite durable memory.

## Output summary

The operator checkpoint receives `unified-memory-v2-summary.json`, and compact Memory V2 fields are attached to `domain-market-intelligence-brief.json` and `multi-market-phone-summary.txt`.

The summary exposes memory run count, remembered evidence, new evidence, proven patterns, repeated successful routes, rule-review candidates, fixed-rule patterns, and patterns that still need AI assistance.

## Non-goals

V2 does not add markets/providers/sources, change production queries, promote sources, contact sellers, bid, reserve, purchase, pay, call AI, or modify code automatically.
