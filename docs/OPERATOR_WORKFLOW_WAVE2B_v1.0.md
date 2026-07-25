# Operator Workflow Wave 2B — Discovery Acceptance Cleanup v1.0

**Status:** APPROVED — NEXT IMPLEMENTATION TASK  
**Scope:** two Discovery acceptance workflows only

## Objective

Apply the first reversible Wave 2 implementation slice after the accepted Wave 2A audit.

## Approved files

Only these workflow files may change:

```text
.github/workflows/discovery-v1-clothing-inventory.yml
.github/workflows/discovery-v1.1-live-search.yml
```

## Approved changes

For both workflows:

- retain `workflow_dispatch`;
- retain the existing focused Discovery tests;
- add pull-request `paths` filters limited to owned Discovery files and tests;
- remove the duplicated complete `pytest -q` regression step;
- rely on `.github/workflows/tests.yml` for repository-wide regression on the same pull request.

## Exact path scopes

### Clothing Inventory acceptance

```text
.github/workflows/discovery-v1-clothing-inventory.yml
src/opportunity_engine/discovery/models.py
src/opportunity_engine/discovery/opportunity_maps.py
src/opportunity_engine/discovery/classifier.py
tests/test_discovery_opportunity_maps.py
tests/test_discovery_classifier.py
```

### Live Search adapter acceptance

```text
.github/workflows/discovery-v1.1-live-search.yml
src/opportunity_engine/discovery/brave_search.py
src/opportunity_engine/discovery/live_search.py
src/opportunity_engine/discovery/search_provider.py
src/opportunity_engine/discovery/query_builder.py
src/opportunity_engine/discovery/result_filter.py
tests/test_discovery_v11_live_search.py
```

## Safety constraints

Do not change:

- workflow display names;
- job identifiers;
- Python versions;
- dependency installation commands;
- focused test commands;
- permissions, secrets, schedules, artifacts, or environment variables;
- production code;
- financial formulas;
- domains or source adapters.

## Verification

The implementation PR must prove:

1. both YAML files remain valid;
2. both manual workflows remain dispatchable;
3. focused Discovery tests pass;
4. `tests.yml` runs and passes the complete regression suite on the same commit;
5. the `pytest-output` artifact remains produced by `tests.yml`;
6. no workflow outside the two approved files changes;
7. no automatic purchase, bid, or contact behavior is introduced.

## Rollback

Rollback is an exact revert of the implementation commit, restoring:

- the previous broad pull-request triggers;
- the duplicated complete regression steps;
- the exact pre-change YAML blobs.

## Gate

Do not begin Wave 3 schedules or Wave 4 diagnostics until this slice is merged and accepted.