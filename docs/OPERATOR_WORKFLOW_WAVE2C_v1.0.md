# Operator Workflow Wave 2C — Primary Discovery Workflow Cleanup v1.0

**Status:** APPROVED — NEXT IMPLEMENTATION TASK  
**Scope:** one primary Discovery operator workflow only

## Accepted prerequisite

PR #218 completed Wave 2B successfully:

- the two Discovery acceptance workflows received exact pull-request path scopes;
- manual dispatch and focused tests were retained;
- duplicated complete `pytest -q` steps were removed from those two workflows only;
- `.github/workflows/tests.yml` remained unchanged and passed the complete regression suite.

## Objective

Apply the next reversible Discovery cleanup slice to:

```text
.github/workflows/discovery-v1.2-live-pilot.yml
```

## Approved changes

- retain the displayed operator name: `1 — Discover Clothing Inventory Opportunities`;
- retain `workflow_dispatch`;
- retain job identifiers `contract-tests` and `live-pilot`;
- retain all focused Discovery quality tests;
- retain the manual Brave live-pilot job, secret usage, commands, reports, and artifact name;
- add an exact pull-request `paths` scope covering the owned Discovery quality, filtering, pilot script, tests, and this workflow file;
- remove only the duplicated complete `pytest -q` regression step from `contract-tests`;
- rely on `.github/workflows/tests.yml` for the repository-wide regression suite on the same pull request.

## Proposed path scope

```text
.github/workflows/discovery-v1.2-live-pilot.yml
src/opportunity_engine/discovery/models.py
src/opportunity_engine/discovery/quality_engine.py
src/opportunity_engine/discovery/result_filter.py
src/opportunity_engine/discovery/live_search.py
src/opportunity_engine/discovery/query_builder.py
src/opportunity_engine/discovery/search_provider.py
scripts/run_discovery_v12_live_pilot.py
tests/test_discovery_v12_live_pilot.py
tests/test_discovery_v15_result_filter.py
tests/test_discovery_v16_quality_engine.py
```

## Safety constraints

Do not change:

- workflow display name;
- job identifiers;
- Python version;
- focused test commands;
- manual live-pilot command or inputs;
- `BRAVE_SEARCH_API_KEY` usage;
- report paths or artifact name;
- permissions, schedules, production code, financial formulas, domains, purchase, bidding, or contact behavior;
- any other workflow.

## Verification

Wave 2C succeeds only when:

1. YAML syntax is valid;
2. manual dispatch remains available;
3. the three focused Discovery test files remain executed;
4. the live-pilot job remains manual-only;
5. the duplicated complete regression step is absent only from this workflow;
6. `tests.yml` runs and passes the complete regression suite on the same commit;
7. phone and JSON artifact behavior remains unchanged;
8. no file outside this workflow and a focused verification test changes.

## Rollback

Rollback is a direct revert restoring the exact pre-change workflow blob, broad pull-request trigger, and duplicated regression step.

## Gate

Do not begin Wave 3 scheduled-workflow changes or Wave 4 diagnostic archival until Wave 2C is merged and accepted.
