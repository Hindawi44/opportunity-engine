# UNIFIED_LEARNING_SPINE_V1

## Purpose

Give every operated market and learning subsystem one common, read-only evidence
contract without rebuilding existing collectors.

The project already has `Unified Market Intelligence River V1`, which unifies
current source artifacts for operator decisions.  This spine intentionally sits
above that river and adds learning context:

```text
source collectors
→ Unified Market Intelligence River
→ same-run bounded learning
→ UNIFIED LEARNING SPINE
→ Learning Layer review
→ future persistent memory / AI analysis
```

V1 is the contract layer only.  It does **not** add persistent unified memory yet.

## Inputs

The daily spine reads existing artifacts:

```text
checkpoint/unified-intelligence-items.json
inputs/learning/search-success-memory.json
inputs/learning/missed-opportunities.json
checkpoint/daily-learning-cycle.json
```

No page fetch, paid search request or OpenAI call is added.

## Common evidence contract

Each retained record has the same core fields regardless of market/source:

```text
learning_evidence_id
evidence_kind
market_code
project_domain
source_name
provider
query
url
result_type
outcome
miss_reason
route
source_identity
observed_at
supporting_run_ids
metadata
```

Evidence kinds in V1:

- `MARKET_OBSERVATION`
- `SEARCH_ROUTE_SUCCESS`
- `MISSED_OPPORTUNITY`

This means France, Netherlands, Italy, Norway, Sweden and Germany can be compared
without erasing their market identity.  A future memory layer can consume this
single contract instead of learning every upstream artifact schema separately.

## Domain boundary

The authoritative `project_domain_boundary` is applied again at the spine.
Only these domains may enter:

```text
CLOTHING_INVENTORY
FABRIC_PROCUREMENT
```

Anything else is excluded and reported through:

```text
out_of_domain_excluded_count
out_of_domain_excluded_ids
```

Generic liquidation/stock vocabulary never establishes project-domain evidence.

## Search-success boundary

A Search Success route enters the spine only when:

- its status is `CANDIDATE` or `REPLICATED_FOR_REVIEW`;
- it has at least one verified exact-lot URL/count;
- its query evidence classifies inside the project domain.

Provider superiority remains separate.  A replicated Exa route is evidence about
that route; it is not automatic proof that Exa is globally better than Brave.

## Miss boundary

Durable missed-opportunity cases are reclassified using their structured
`opportunity_type` plus `learning_evidence_text`.  Old out-of-domain misses do not
re-enter the spine even if an older artifact still contains them.

## Output

The daily checkpoint gains:

```text
unified-learning-spine.json
```

A compact summary is attached to:

```text
domain-market-intelligence-brief.json
multi-market-phone-summary.txt
```

## Runtime ordering

The atexit registration order is deliberately:

```text
Learning Layer
→ Unified Learning Spine
→ daily learner
→ Unified Market Intelligence River
```

Because Python executes atexit handlers LIFO, runtime is:

```text
River
→ daily learner
→ Spine
→ Learning Layer
```

The spine therefore sees same-run market observations plus same-run clean
learning memory.

## Safety

```text
project_domain_gate_enforced: true
automatic_query_activation: false
automatic_provider_activation: false
automatic_source_promotion: false
automatic_code_change: false
production_query_mutation: false
production_mutation: false
automatic_contact: false
automatic_bid: false
automatic_reservation: false
automatic_purchase: false
automatic_payment: false
```

## Deferred deliberately

V1 does not persist this unified contract across runs.  That is the next memory
step after the live daily spine proves that the contract is stable and useful.
A future AI/Agent layer should read the unified evidence/memory and remain
advisory; repeated proven reasoning can later be converted into deterministic
project rules so AI dependence can decrease over time.
