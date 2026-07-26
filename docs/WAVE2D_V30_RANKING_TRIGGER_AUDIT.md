# Wave 2D — V3.0 Ranking Trigger and Regression Audit

**Result:** `READY_FOR_PATH_SCOPING`  
**Scope:** documentation-only prerequisite audit  
**Workflow:** `.github/workflows/v30-multi-opportunity-ranking.yml`

## Executive conclusion

The V3.0 ranking acceptance workflow is ready for a separate, reversible trigger-scoping implementation task.

The current workflow already preserves the material V3.0 acceptance boundary:

- manual execution through `workflow_dispatch`;
- one focused V3.0 E2E test;
- one deterministic acceptance-report generator;
- one report artifact;
- no repository-wide `pytest -q` regression step;
- no search, evidence inference, financial recalculation, purchase, bid, or contact action.

The only bounded cleanup issue is the broad, unscoped `pull_request` trigger.

## Current workflow contract

The workflow:

1. runs on every pull request and on manual dispatch;
2. uses Python 3.11;
3. installs `pytest` and repository requirements;
4. runs `tests/test_v30_multi_opportunity_ranking_e2e.py`;
5. runs `scripts/run_v30_multi_opportunity_ranking_acceptance.py`;
6. prints the generated report when present;
7. uploads artifact `v3.0-multi-opportunity-ranking-acceptance`;
8. uploads `data/validation/v3.0-multi-opportunity-ranking-acceptance.json`;
9. uses `if-no-files-found: warn`;
10. has no explicit artifact-retention value and therefore relies on the repository/default GitHub retention policy.

## Dependency trace

The focused test and deterministic report generator both import only:

```text
src/opportunity_engine/multi_opportunity_ranking.py
```

The implementation module uses only Python standard-library modules:

- `dataclasses`
- `datetime`
- `typing`

No fixture file, external provider, secret, persisted dataset, financial engine module, or source adapter is imported by this acceptance path.

## Material behavior preserved by the focused test

The focused test proves:

- only `READY_FOR_FINANCIAL_REVIEW` records can be ranked;
- incomplete evidence is excluded;
- fewer than three verified comparables is excluded;
- fewer than six verified cost components is excluded;
- missing profit or ROI is excluded;
- automatic purchase decisions remain prohibited;
- ranking order is deterministic;
- ranking order uses existing ROI, expected profit, evidence completeness, comparable quality, and opportunity ID;
- excluded records remain visible in the report;
- no eligible records produce `NO_ELIGIBLE_OPPORTUNITIES` rather than an unsafe promotion.

The deterministic report generator independently verifies the expected order, processed count, eligible count, excluded count, and the prohibition on automatic purchase decisions.

## Proposed minimal pull-request path scope

A future implementation task may safely replace the broad pull-request trigger with:

```yaml
pull_request:
  paths:
    - ".github/workflows/v30-multi-opportunity-ranking.yml"
    - "src/opportunity_engine/multi_opportunity_ranking.py"
    - "tests/test_v30_multi_opportunity_ranking_e2e.py"
    - "scripts/run_v30_multi_opportunity_ranking_acceptance.py"
```

This is the exact owned-file boundary visible in tracked code.

`workflow_dispatch` must remain unchanged so an operator can still run the acceptance workflow intentionally.

## Canonical regression ownership

This workflow does not run a broad repository regression. It runs only the focused V3.0 test and deterministic report.

Repository-wide regression remains owned by:

```text
.github/workflows/tests.yml
```

Changes outside the four-file V3.0 ownership boundary should therefore rely on the canonical regression workflow rather than triggering this focused acceptance workflow.

## Artifact contract

| Item | Current contract | Decision |
|---|---|---|
| Artifact name | `v3.0-multi-opportunity-ranking-acceptance` | Preserve unchanged |
| Report path | `data/validation/v3.0-multi-opportunity-ranking-acceptance.json` | Preserve unchanged |
| Missing file | `warn` | Preserve unchanged |
| Retention | No workflow-specific value | Preserve unchanged unless a separate retention decision is approved |
| Print behavior | Prints report only when present | Preserve unchanged |

## External facts

The following remain `MANUAL_VERIFICATION_REQUIRED` because they are not established by tracked repository files:

- whether the current V3.0 check name is required by branch protection;
- whether an external consumer depends on the check running for every pull request;
- whether operators rely on the current broad trigger;
- whether historical artifact links are consumed externally;
- the effective repository-level artifact-retention setting.

These facts do not block the documentation classification, but they must be checked before merging the separate workflow-change PR.

## Rollback

Rollback for a future path-scoping implementation is an exact revert of that implementation commit, restoring the current workflow blob and its broad:

```yaml
pull_request:
```

trigger.

No ranking formula, test expectation, report field, artifact name, manual trigger, or production module should change in that implementation.

## Classification

```text
READY_FOR_PATH_SCOPING
```

## Exact next implementation boundary

A separate task may modify only:

```text
.github/workflows/v30-multi-opportunity-ranking.yml
```

The permitted change is limited to adding the four documented `pull_request.paths` entries while preserving every other workflow property.

Before merging that implementation, verify branch-protection/check-name dependence, validate YAML, run the focused V3.0 acceptance workflow and canonical `tests.yml` on the same commit, and confirm the report artifact remains produced.
