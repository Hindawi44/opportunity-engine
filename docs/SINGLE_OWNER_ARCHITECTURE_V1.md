# Single-Owner Architecture V1

## Canonical chain

```text
Evidence -> Fact -> Lifecycle State/Eligibility -> Value -> Decision -> Observers
```

Every stage has one owner of truth. A downstream stage may consume, validate,
rank, explain, persist, or render upstream truth, but it must not reconstruct,
override, resurrect, or silently choose a conflicting truth owned by another stage.

## Ownership matrix

| Layer | Canonical owner | Owns | Must not do |
|---|---|---|---|
| Evidence | `SourceDocument` identity + `deduplicate_source_documents` | source-local evidence identity, exact duplicate collapse, contradiction detection | discard a different source because its local document ID collides |
| Fact | `UnifiedOpportunityExtractor` + `UnifiedMultiSourceEngine` | normalized facts, compatible multi-source consolidation, provenance, canonical fact identity | silently select a winner when material evidence conflicts |
| Lifecycle | lifecycle/unified report | workflow state, evaluation state, eligibility, lifecycle reason | let checkpoint/integration infer or resurrect state/eligibility from local flags |
| Value | `OpportunityValueEngine` | profit, ROI, margin, conservative cost/purchase ceilings | issue BUY/WATCH/REJECT |
| Decision | `OpportunityProfitDecisionEngine` | final BUY/WATCH/REJECT plus commercial constraints | recompute Value or delegate final recommendation downstream |
| Observers | scoring, intelligence, discovery, reporting, alerts | ranking, explanation, display, event notification | replace the canonical decision or recreate upstream truth |

## Fail-closed rules

1. Same evidence identity with contradictory payloads is an integrity error.
2. Duplicate source evidence with contradictory material facts is an integrity error.
3. Missing, incomplete, or conflicting canonical lifecycle truth is an integrity error.
4. Decision accepts canonical Value rather than market/cost inputs.
5. Intelligence mirrors canonical Decision exactly.

## Compatibility rules

- Existing single-source opportunity IDs remain unchanged when there is no real
  cross-source document-ID collision.
- Multi-source Fact consolidation preserves source IDs and provenance.
- No automatic contact, bid, purchase, reservation, or payment behavior is added
  by this architecture refactor.

## Promotion discipline

Architecture changes follow:

```text
Freeze -> Test -> Verdict -> Promote/Reject
```

The regression contract in
`tests/test_single_owner_architecture_contract_v1.py` guards the dependency and
ownership boundaries above.
