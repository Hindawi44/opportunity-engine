# Workflow Wave 3C — V3.2 Continuous Monitoring Ownership Audit Report v1.0

**Audit date:** 2026-07-25  
**Scope:** documentation and verification only  
**Workflow behavior changed:** none

## 1. Audited workflow identity

| Field | Verified value |
|---|---|
| File | `.github/workflows/v3.2-continuous-opportunity-monitoring.yml` |
| Display name | `V3.2 Continuous Opportunity Monitoring` |
| Job identifier | `continuous-monitoring` |
| Runner | `ubuntu-latest` |
| Python | `3.11` |
| Dependency install | `pip install pytest` |
| Environment | `PYTHONPATH=${{ github.workspace }}/src:${{ github.workspace }}` |
| Secrets | none referenced |
| Explicit permissions | none declared; repository/default token permissions apply |

## 2. Current triggers and schedule

V3.2 currently runs through:

1. `pull_request` targeting `main`;
2. `workflow_dispatch`;
3. hourly schedule `17 * * * *`.

The schedule is UTC under GitHub Actions semantics.

## 3. Schedule ownership and collision status

Wave 3B removed the minute-17 schedule from `.github/workflows/v3.7-production-pilot.yml`.

Tracked workflow evidence now shows:

- V3.2 remains scheduled hourly at minute 17;
- V3.3 remains scheduled hourly at minute 12;
- V3.7 is manual-only.

Therefore the former direct V3.2/V3.7 minute-17 collision is resolved. V3.2 is the only tracked hourly workflow still using minute 17 among those three audited contracts.

Other six-hour schedules are outside this audit. Whether any external scheduler also invokes V3.2 at minute 17 remains `MANUAL_VERIFICATION_REQUIRED`.

## 4. Complete workflow contract

The job executes in this order:

1. checkout with `actions/checkout@v4`;
2. Python 3.11 setup with `actions/setup-python@v5`;
3. install `pytest`;
4. restore `data/monitoring/v3.2-seen-state.json` with `actions/cache/restore@v4`;
5. run focused test `pytest tests/test_v32_continuous_opportunity_monitoring.py -q`;
6. run `python scripts/run_v32_continuous_opportunity_monitoring.py`;
7. save the state file with `actions/cache/save@v4`;
8. print `data/validation/v3.2-continuous-monitoring.json` even after failure;
9. upload artifact `v3.2-continuous-monitoring` even after failure.

No complete repository `pytest -q` regression step exists in this workflow.

## 5. State path, cache keys, and continuity

### State path

```text
data/monitoring/v3.2-seen-state.json
```

### V3.2 cache contract

```text
save key:    v3.2-monitoring-state-${{ github.run_id }}
restore key: v3.2-monitoring-state-
```

Each run writes an immutable run-specific cache key. Later V3.2 runs use the prefix restore key to recover a previous compatible cache.

GitHub cache selection order and retention are platform behavior. Confirmation that the newest intended cache is always restored in production remains `MANUAL_VERIFICATION_REQUIRED`.

### Shared-state observation

V3.3 also restores and saves the same state path, but under a different cache-key namespace:

```text
v3.3-auksjonen-seen-${{ runner.os }}-${{ github.run_id }}
```

Tracked evidence therefore proves a shared file contract but separate cache namespaces. A V3.2 run does not directly restore a V3.3 cache, and a V3.3 run does not directly restore a V3.2 cache.

Consequences:

- the two workflows can advance independent cached copies of the same logical state path;
- filesystem path equality does not create cross-workflow cache continuity;
- intended ownership of the shared state across V3.2 and V3.3 requires explicit future design approval.

Status: `SHARED_PATH_SEPARATE_CACHE_NAMESPACES`.

## 6. State producer and consumer map

### Confirmed producers

- `scripts/run_v32_continuous_opportunity_monitoring.py` writes the normalized next state after every run;
- `.github/workflows/v3.2-continuous-opportunity-monitoring.yml` saves that file to the V3.2 cache namespace;
- V3.3 ingestion also writes/saves the same path through its own script and cache namespace.

### Confirmed consumers

- `scripts/run_v32_continuous_opportunity_monitoring.py` reads the state before duplicate detection;
- the V3.2 workflow restores it before executing the monitor;
- V3.3 reads/restores the same path through its own namespace;
- V3.4 references the same state contract as input to persistent-state processing.

### Unconfirmed consumers

External dashboards, operators, scheduled jobs, APIs, or local scripts relying on the cached state remain `MANUAL_VERIFICATION_REQUIRED`.

## 7. Duplicate-protection behavior

The focused V3.2 test proves deterministic two-run behavior using the same batch:

- first run observes four opportunities and identifies all four as new;
- the returned state contains their fingerprints;
- second run with that state identifies zero new opportunities;
- second run reports four previously seen opportunities;
- no automatic purchase decision is made;
- state fingerprints remain stable.

The monitoring script evaluates only unseen records, writes the next state, and returns `NO_NEW_OPPORTUNITIES` when no unseen record exists.

Status: `CONFIRMED_IN_PROCESS_CONTRACT`.

This proves duplicate protection when the prior state is successfully supplied. It does not independently prove cache restoration continuity across hosted runs.

## 8. Report and artifact contract

### Report path

```text
data/validation/v3.2-continuous-monitoring.json
```

The report records observed, new, previously seen, and rejected counts; new opportunity IDs; evaluation and ranking outputs; state advancement; errors; and status. It hard-codes:

```text
automatic_purchase_decision: false
```

### Artifact

```text
name: v3.2-continuous-monitoring
path: data/validation/v3.2-continuous-monitoring.json
```

### Tracked consumers

V3.3 uploads the V3.2 monitoring report as part of its broader source-ingestion artifact bundle. No direct tracked workflow dependency consumes the V3.2 artifact by artifact name.

External artifact consumers and operator routines remain `MANUAL_VERIFICATION_REQUIRED`.

## 9. Monitoring ownership conclusion

Tracked evidence supports V3.2 as the current dedicated continuous-monitoring contract because it uniquely combines:

- an hourly schedule;
- restoration and advancement of seen-state;
- unseen-record detection;
- focused two-run duplicate-protection verification;
- a monitoring-specific report and artifact.

V3.3 is a live source-ingestion and snapshot-refresh workflow. It shares the state file path but has a separate source-ingestion role and separate cache namespace.

Ownership status: `V3_2_PRIMARY_MONITORING_OWNER_FROM_TRACKED_EVIDENCE`.

External operational ownership remains `MANUAL_VERIFICATION_REQUIRED`.

## 10. Pull-request trigger assessment

The broad PR trigger causes V3.2 to execute for every pull request targeting `main`, regardless of changed paths. Its focused test and deterministic script provide useful acceptance coverage, but repository-wide regression is already owned by `tests.yml`.

A future implementation PR may remove the broad PR trigger or replace it with exact path scopes. The lower-risk proposal is path-scoping first.

Proposed future PR paths:

```text
.github/workflows/v3.2-continuous-opportunity-monitoring.yml
scripts/run_v32_continuous_opportunity_monitoring.py
src/opportunity_engine/continuous_opportunity_monitoring.py
scripts/run_v31_live_batch_validation.py
tests/test_v32_continuous_opportunity_monitoring.py
data/live_validation/v3.1-auksjonen-live-batch.json
```

Before implementation, required-check and ruleset dependence on the current V3.2 PR check remains `MANUAL_VERIFICATION_REQUIRED`.

## 11. Schedule proposal

Tracked evidence supports retaining:

```text
17 * * * *
```

because:

- the direct collision with V3.7 is resolved;
- V3.2 is the tracked primary continuous-monitoring owner;
- stateful duplicate detection benefits from recurring execution;
- no tracked replacement scheduler exists.

No schedule change is approved by this audit.

## 12. Risk assessment

Overall future trigger-cleanup risk: `MEDIUM`.

Primary risks:

- branch protection may require the current V3.2 check;
- exact path scopes may omit a real dependency;
- V3.2 and V3.3 can diverge because they use separate cache namespaces for one state path;
- cache eviction or restore ordering can break continuity;
- external consumers may depend on hourly reports or artifacts;
- removing PR execution could reduce early detection of state-contract defects.

## 13. Required manual verification before implementation merge

1. Inspect branch protection and repository rulesets for the V3.2 workflow/check name.
2. Confirm no external process requires V3.2 on every pull request.
3. Confirm no external dashboard or operator expects an hourly artifact under the current name.
4. Inspect recent scheduled runs to confirm state restoration and advancement across at least two runs.
5. Decide whether V3.2 or V3.3 owns the canonical cache namespace for the shared state path.
6. Confirm `tests.yml` passes the complete suite on the implementation commit.

## 14. Exact future implementation scope

A later PR may modify only:

```text
.github/workflows/v3.2-continuous-opportunity-monitoring.yml
tests/test_workflow_wave3c_v32_trigger_cleanup.py
```

It may:

- retain `workflow_dispatch`;
- retain schedule `17 * * * *`;
- retain the job, environment, cache paths and keys, focused test, monitor command, report, and artifact;
- replace broad PR execution with the approved exact path scopes, subject to manual required-check verification.

It must not change V3.3, state semantics, production code, report schema, artifact name, purchase, bid, contact, or financial behavior.

## 15. Rollback

Rollback is a direct revert restoring the exact pre-change workflow blob SHA:

```text
8a89b08b284461957789c8370db7375b1272597f
```

The restored workflow must include broad `pull_request` on `main`, manual dispatch, minute-17 hourly schedule, existing cache contract, focused test, monitor command, report print, and artifact upload.

## 16. Verification bundle for a future implementation PR

The future implementation PR must prove:

- valid YAML;
- schedule and manual dispatch remain unchanged;
- exact approved PR path scopes are present;
- cache path, keys, and restore prefix remain unchanged;
- focused two-run duplicate test passes;
- the monitor creates valid state and report JSON;
- report and artifact names remain unchanged;
- `tests.yml` passes the complete suite on the same commit;
- V3.3, V3.7, and all production files remain unchanged;
- no automatic purchase, bid, contact, or invented financial value is introduced.

## Conclusion

V3.2 is the primary continuous-monitoring owner supported by tracked repository evidence. Its hourly minute-17 schedule is now collision-free relative to V3.7 and should remain. Its broad pull-request trigger is a candidate for a later exact path-scoping PR, but only after branch-protection and external-consumer checks are completed. No workflow changed in this audit.
