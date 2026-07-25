# Workflow Wave 3A — V3.7 Schedule Prerequisite Audit Report v1.0

**Audit date:** 2026-07-25  
**Scope:** documentation and verification only  
**Workflow behavior changed:** none

## 1. Audited workflow identity

| Field | Verified value |
|---|---|
| File | `.github/workflows/v3.7-production-pilot.yml` |
| Display name | `2 — Review One Opportunity End to End` |
| Job identifier | `production-pilot` |
| Runner | `ubuntu-latest` |
| Python | `3.11` |
| Dependency install | `pip install pytest` |
| Explicit permissions | none declared; repository/default token permissions apply |
| Workflow inputs | none |
| Secrets | none referenced |
| Environment variables | `PYTHONPATH=src:repository` on test, summary generation, and regression steps |

## 2. Current triggers and schedule

V3.7 currently runs on all three trigger classes:

1. `pull_request` with no branch or path restriction;
2. `workflow_dispatch` with no inputs;
3. hourly schedule `17 * * * *`.

The schedule is UTC under GitHub Actions semantics.

## 3. Exact schedule collision

`.github/workflows/v3.2-continuous-opportunity-monitoring.yml` also uses:

```text
17 * * * *
```

Therefore V3.2 and V3.7 are both scheduled at minute 17 of every hour. This is a confirmed trigger collision, not merely a similar cadence.

Other tracked schedules are outside this audit and remain unchanged.

## 4. Commands, outputs, and artifacts

V3.7 executes, in order:

1. focused acceptance test:
   `pytest tests/test_v37_production_pilot.py -q`;
2. deterministic summary generator:
   `python scripts/run_v37_production_pilot_acceptance.py`;
3. duplicated complete regression:
   `pytest -q`;
4. summary print:
   `cat artifacts/v3.7-production-pilot-summary.json`;
5. artifact upload named:
   `v3.7-production-pilot-summary`.

Generated tracked-path contract:

```text
artifacts/v3.7-production-pilot-summary.json
```

The acceptance script uses deterministic in-memory fixture snapshots and writes one JSON summary. It does not fetch live data, read secrets, persist cross-run state, send email, contact sellers, bid, or purchase.

## 5. Dependency map

### V3.6 ingestion — confirmed code dependency

`run_production_cycle()` imports and calls `merge_snapshots()` from `opportunity_engine.source_ingestion.multisource`.

Dependency status: `CONFIRMED_CODE_CONTRACT`.

V3.7 does not consume an artifact or state file produced by the V3.6 workflow. It composes the same underlying contract directly in-process.

### V3.5 review queue — confirmed code dependency

`run_production_cycle()` imports and calls `update_review_queue()` from `opportunity_engine.opportunity_review_queue`.

Dependency status: `CONFIRMED_CODE_CONTRACT`.

V3.7 does not consume an artifact produced by the V3.5 workflow.

### V3.2 monitoring — no direct code or artifact dependency found

The V3.2 workflow restores and saves:

```text
data/monitoring/v3.2-seen-state.json
```

and uploads:

```text
data/validation/v3.2-continuous-monitoring.json
```

V3.7 references neither path and does not call the V3.2 monitoring script.

Dependency status: `NO_DIRECT_TRACKED_DEPENDENCY_FOUND`.

Operational ownership or an external process that expects V3.2 and V3.7 to run together remains `MANUAL_VERIFICATION_REQUIRED`.

## 6. Automatic-run consumers

| Potential consumer | Tracked evidence status |
|---|---|
| Another workflow consuming the V3.7 artifact | `NO_DIRECT_TRACKED_DEPENDENCY_FOUND` |
| A tracked script reading `artifacts/v3.7-production-pilot-summary.json` after a scheduled run | `NO_DIRECT_TRACKED_DEPENDENCY_FOUND` |
| External dashboard, notification, API, or human process relying on hourly runs | `MANUAL_VERIFICATION_REQUIRED` |
| Branch protection requiring the V3.7 PR check | `MANUAL_VERIFICATION_REQUIRED` |
| Repository ruleset requiring the displayed check name | `MANUAL_VERIFICATION_REQUIRED` |

No external-consumer absence may be inferred from repository files alone.

## 7. Manual-dispatch completeness

The current `workflow_dispatch` trigger launches the same single `production-pilot` job as pull requests and schedules. The job contains no event-specific condition and requires no inputs or secrets.

Tracked evidence therefore confirms that manual dispatch can execute:

- the focused V3.7 acceptance test;
- the deterministic two-cycle production-pilot summary;
- the complete regression step;
- summary printing;
- artifact upload.

Status: `CONFIRMED_FROM_TRACKED_WORKFLOW`.

This proves manual execution completeness for the deterministic acceptance pilot, not for any untracked live production process.

## 8. Exact future manual-only proposal

A later implementation PR may modify only `.github/workflows/v3.7-production-pilot.yml` and a focused verification test.

Approved future change proposal:

- retain display name `2 — Review One Opportunity End to End`;
- retain `workflow_dispatch` unchanged;
- retain job identifier, Python version, dependency command, focused test, summary command, output path, and artifact name;
- remove the broad `pull_request` trigger;
- remove schedule `17 * * * *`;
- remove the duplicated complete `pytest -q` step only if `.github/workflows/tests.yml` runs and passes the full suite on the same commit;
- add no inputs, secrets, permissions, state, notifications, live sources, purchase, bid, or contact behavior.

This proposal is not yet implemented.

## 9. Risk assessment

Overall future implementation risk: `HIGH` until manual checks are completed.

Primary risks:

- an external consumer may rely on the hourly artifact;
- branch protection may require the current V3.7 check;
- removing the PR trigger may reduce a unique end-to-end boundary if `tests.yml` or focused tests do not cover it;
- a manual-only workflow can be forgotten operationally;
- the current schedule collision may be intentional despite no tracked evidence.

## 10. Required manual verification before implementation merge

1. Inspect repository branch protection and rulesets for the V3.7 workflow/check name.
2. Confirm no external dashboard, notification, API, cron, or operator routine relies on hourly V3.7 runs.
3. Confirm no artifact consumer relies on `v3.7-production-pilot-summary` appearing hourly.
4. Run V3.7 manually once and verify the JSON artifact is produced.
5. Confirm `.github/workflows/tests.yml` runs and passes the complete suite on the implementation commit.
6. Confirm V3.2 remains scheduled at minute 17 and still owns continuous monitoring.

## 11. Rollback

Rollback is a direct revert restoring the exact pre-change V3.7 YAML blob SHA:

```text
3e6c65449e093e7051f980ef4b1b04af3470a443
```

The restored workflow must include:

- broad `pull_request`;
- `workflow_dispatch`;
- hourly schedule `17 * * * *`;
- focused V3.7 test;
- deterministic summary generation;
- complete `pytest -q` regression;
- summary print and artifact upload.

## 12. Implementation verification bundle

The future implementation PR must prove:

- valid YAML;
- only the approved workflow and focused verification test changed;
- manual dispatch remains available;
- the focused V3.7 test remains unchanged and passes;
- summary generation still creates valid JSON;
- artifact name and path remain unchanged;
- `tests.yml` passes the complete repository suite on the same commit;
- V3.2, V3.5, V3.6, and all other workflows remain byte-for-byte unchanged;
- no automatic purchase, bid, contact, or invented financial value is introduced.

## Conclusion

Tracked evidence supports a later conversion of V3.7 to a deterministic manual operator review workflow and confirms the minute-17 collision with V3.2. The conversion is not authorized until repository settings and external consumers are manually verified. No workflow changed in this audit.