# Wave 4B Preservation Evidence

**Status:** ACCEPTED — COMPLETE  
**Execution date:** 2026-07-25  
**Scope:** V2.6.6 final manual preservation run only

## Workflow execution

- Workflow: `V2.6.6 Live Dry Run`
- Trigger: manual
- Run ID: `30175512518`
- Run number: `#4`
- Run URL: `https://github.com/Hindawi44/opportunity-engine/actions/runs/30175512518`
- Branch: `main`
- Commit SHA: `ae24a49875aa754eb0f9d90c2629aca5c6919d2f`
- Conclusion: `SUCCESS`
- Job name: `live-dry-run`
- Input: `opportunity_limit=2`
- Job execution started at approximately `2026-07-25T21:22:39Z`
- Artifact created at `2026-07-25T21:23:14Z`

## Artifact preservation

- Artifact name: `v2.6.6-live-dry-run`
- Artifact ID: `8624093715`
- Downloaded archive name: `v2.6.6-live-dry-run.zip`
- Download confirmed: yes
- Artifact size: `8493 bytes`
- Artifact created at: `2026-07-25T21:23:14Z`
- Artifact expires at: `2026-08-08T21:23:13Z`
- Artifact expired: `false`
- Artifact digest:

```text
sha256:57cc918d719a1aafa6720bff486035daf157a5e09e641f6e61214b6c8ff89420
```

## Verified artifact inventory

The downloaded archive was opened and the complete inventory was verified:

1. `dry_run_first.json`
2. `dry_run_second.json`
3. `investment_files/unified-auksjonen-614199.json`
4. `investment_files/unified-auksjonen-614284.json`
5. `production_readiness.json`
6. `production_readiness_final.json`
7. `smart_alerts.json`
8. `todays_opportunities.json`

## Production-readiness evidence

The preserved `production_readiness.json` and `production_readiness_final.json` were inspected.

Verified readiness checks include:

- Brave secret presence
- request-budget validity
- cache-TTL validity
- daily pipeline script presence
- investment-directory writability
- usage-log-parent writability

The final readiness file showed:

```text
ready: true
```

The final readiness file also contained `dry_run_comparison` and recorded the repeat-protection result honestly as observed in the preserved evidence.

The second dry-run summary showed:

- `fetched_count = 74`
- `extracted_count = 49`
- `deduplicated_count = 49`
- `duplicate_count = 0`
- `buy_count = 0`
- `monitor_count = 49`
- `reject_count = 0`
- `investment_files_created = 0`
- `investment_files_updated = 0`
- `investment_files_unchanged = 2`
- `alert_count = 0`

## Job verification

GitHub Actions job data confirmed:

- Job ID: `89723551444`
- Job name: `live-dry-run`
- Status: `completed`
- Conclusion: `success`
- All workflow steps completed successfully, including:
  - `First guarded daily run`
  - `Second guarded daily run`
  - `Verify cache and repeat protection`
  - `Upload dry-run evidence`

## Secret-safety statement

No secret value was copied into this evidence document. GitHub Actions logs masked the Brave API key and recorded only whether the configuration check passed.

## Repository-safety statement

Wave 4B made no change to:

- `.github/workflows/v2.6.6-live-dry-run.yml`
- production code
- financial formulas
- domain scope
- purchase, bid, contact, or alert behavior

## External facts that remain manually verifiable

The following repository-setting or external-consumer facts remain outside tracked repository evidence and retain the status:

```text
MANUAL_VERIFICATION_REQUIRED
```

- branch-protection dependence on the workflow or job name;
- operators relying on the Actions entry;
- external links to historical artifacts;
- dashboards, APIs, notifications, or compliance consumers outside tracked files.

These unresolved external facts do not invalidate the preserved final-run evidence.

## Conclusion

The final manual V2.6.6 preservation run completed successfully. Its run metadata, job result, artifact metadata, digest, complete file inventory, readiness evidence, and repeat-protection evidence were preserved without exposing secrets or modifying production behavior.

Wave 4B is accepted as complete. Any later disablement action must occur in a separate reversible Wave 4C change. Deletion is not approved.
