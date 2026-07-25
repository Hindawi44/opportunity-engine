# Operator Workflow Wave 3D — V3.2 Pull-Request Trigger Scoping v1.0

**Status:** APPROVED — NEXT IMPLEMENTATION TASK  
**Scope:** one reversible GitHub Actions trigger cleanup

## Accepted prerequisite

Wave 3C established from tracked repository evidence that:

- `.github/workflows/v3.2-continuous-opportunity-monitoring.yml` is the primary continuous-monitoring owner;
- its hourly schedule `17 * * * *` is now collision-free relative to V3.7 and should remain;
- `workflow_dispatch`, the focused V3.2 test, state/cache contract, report, and artifact must remain;
- duplicate protection is confirmed when prior state is supplied;
- branch-protection, external-consumer, and hosted-cache continuity facts remain `MANUAL_VERIFICATION_REQUIRED`.

## Objective

Replace the broad pull-request trigger in:

```text
.github/workflows/v3.2-continuous-opportunity-monitoring.yml
```

with exact approved path scopes, while preserving all scheduled monitoring behavior.

## Permitted workflow change

The `pull_request` trigger may be scoped to these paths only:

```text
.github/workflows/v3.2-continuous-opportunity-monitoring.yml
scripts/run_v32_continuous_opportunity_monitoring.py
src/opportunity_engine/continuous_opportunity_monitoring.py
scripts/run_v31_live_batch_validation.py
tests/test_v32_continuous_opportunity_monitoring.py
data/live_validation/v3.1-auksjonen-live-batch.json
```

## Required preservation

The implementation must retain unchanged:

- display name `V3.2 Continuous Opportunity Monitoring`;
- job identifier `continuous-monitoring`;
- `workflow_dispatch`;
- schedule `17 * * * *`;
- Python 3.11 and `PYTHONPATH`;
- state path `data/monitoring/v3.2-seen-state.json`;
- cache actions, keys, and restore prefix;
- focused test `pytest tests/test_v32_continuous_opportunity_monitoring.py -q`;
- monitor command;
- report print behavior;
- artifact name `v3.2-continuous-monitoring` and report path;
- `if: always()` and `if-no-files-found: warn` behavior.

## Approved files

The implementation PR may modify only:

```text
.github/workflows/v3.2-continuous-opportunity-monitoring.yml
tests/test_workflow_wave3d_v32_trigger_scoping.py
```

## Prohibited changes

Do not change:

- V3.2 schedule, state semantics, cache namespace, report schema, or artifact contract;
- V3.3, V3.7, `scheduled-agent.yml`, or `daily-opportunity-pipeline.yml`;
- production code or financial formulas;
- domain scope;
- purchase, bid, or contact behavior.

## Manual verification gate

Before merge, repository rules and branch protection must be checked for dependence on the existing V3.2 pull-request check. Any unverified external consumer remains `MANUAL_VERIFICATION_REQUIRED`.

## Verification bundle

Wave 3D succeeds only when:

1. YAML syntax is valid;
2. the exact six path scopes are present;
3. manual dispatch and hourly minute-17 schedule remain unchanged;
4. state/cache/report/artifact contracts remain unchanged;
5. the focused two-run V3.2 test passes;
6. `tests.yml` passes the complete suite on the same commit;
7. no file outside the approved scope changes;
8. rollback is a direct revert restoring workflow blob `8a89b08b284461957789c8370db7375b1272597f`.
