# Workflow Wave 4A — V2.6.6 Historical Diagnostic Audit Report v1.0

**Status:** COMPLETE — AUDIT ONLY  
**Audited workflow:** `.github/workflows/v2.6.6-live-dry-run.yml`  
**Exact pre-change repository commit:** `6cb22262a18950c045ba8deb4ae70dbc2cc6811e`  
**Workflow blob SHA at audit:** `a7af4f99e3c6e5b299c2248e8ea2fa3713e057e7`

## 1. Executive conclusion

V2.6.6 is a manual historical production-readiness diagnostic. It validates that the Brave secret and request limits are configured, executes the legacy daily pipeline twice, compares the two summaries for cache/repeat-protection evidence, and uploads the generated evidence bundle.

The workflow is not scheduled, does not run on pull requests, and does not purchase, bid, contact, or invent missing financial evidence.

Current unit tests cover the readiness auditor, secret non-disclosure, missing-secret failure, and dry-run comparison logic. Current workflows exercise newer monitoring, source-ingestion, and repository regression boundaries, but no tracked workflow reproduces the exact V2.6.6 live two-run evidence bundle with the same artifact name and files.

**Recommendation:** keep it manual for one final verified evidence run, preserve the resulting artifact and metadata, then disable it in a separate reversible PR. Do not delete it in the first cleanup pass. Archival or relocation should occur only after repository-setting and external-consumer checks are completed.

## 2. Workflow contract

### Trigger and permissions

- Trigger: `workflow_dispatch` only.
- Required input: `opportunity_limit`, default `'2'`.
- Permission: `contents: read`.
- Job: `live-dry-run`.
- Runner: `ubuntu-latest`.
- Timeout: 20 minutes.
- Python: 3.11 with pip cache.

### Environment and secret contract

- `PYTHONPATH=${{ github.workspace }}/src`
- `BRAVE_API_KEY=${{ secrets.BRAVE_API_KEY }}`
- `BRAVE_MAX_REQUESTS_PER_RUN='4'`
- `BRAVE_CACHE_TTL_HOURS='24'`
- `EXTERNAL_RESEARCH_MAX_OPPORTUNITIES=${{ inputs.opportunity_limit }}`

The only directly referenced secret is `BRAVE_API_KEY`. Whether it is configured in repository or environment settings is `MANUAL_VERIFICATION_REQUIRED`.

### Commands

1. Install `requirements.txt`.
2. Verify `opportunity_engine` imports.
3. Run `scripts/run_production_readiness.py --output data/production_readiness.json`.
4. Run `scripts/run_daily_pipeline.py` twice with the selected opportunity limit, writing:
   - `data/dry_run_first.json`
   - `data/dry_run_second.json`
5. Run the readiness auditor again with both summaries, writing:
   - `data/production_readiness_final.json`
6. Upload the evidence artifact.

## 3. Direct dependency map

### Scripts and production modules

- `scripts/run_production_readiness.py`
  - invokes `opportunity_engine.production_readiness.ProductionReadinessAuditor`;
  - writes readiness JSON;
  - exits non-zero if required readiness checks fail;
  - can compare two dry-run summaries.
- `src/opportunity_engine/production_readiness.py`
  - checks secret presence without exposing its value;
  - checks Brave request budget and cache TTL;
  - verifies the daily pipeline script and writable output directories;
  - compares first/second run search and cache counters.
- `scripts/run_daily_pipeline.py`
  - runs the legacy multi-source daily pipeline;
  - writes `data/todays_opportunities.json` and `data/smart_alerts.json`;
  - synchronizes `data/investment_files/`;
  - may write `data/brave_usage.jsonl` through the research transport;
  - accepts optional FINN and feed credentials from the runtime environment, but V2.6.6 directly injects only the Brave secret.

### Tests

- `tests/test_production_readiness.py` verifies:
  - readiness succeeds with safe limits and a configured secret;
  - secret values are not exposed;
  - missing live secret blocks readiness;
  - dry-run comparison detects repeat protection.

### Fixtures

The workflow references no fixed fixture. It is a live manual diagnostic and therefore depends on runtime source availability.

## 4. Report and artifact contract

Artifact name:

```text
v2.6.6-live-dry-run
```

Retention: 14 days.

Artifact paths:

- `data/production_readiness*.json`
- `data/dry_run_*.json`
- `data/todays_opportunities.json`
- `data/smart_alerts.json`
- `data/investment_files/`
- `data/brave_usage.jsonl`

`if-no-files-found: warn` means a partial evidence bundle can still be uploaded. A final preservation run must therefore verify the expected files inside the downloaded archive rather than relying only on workflow success.

## 5. Equivalent current coverage

### Demonstrated equivalent logic

- `tests/test_production_readiness.py` covers the readiness and repeat-protection algorithm directly.
- `tests.yml` provides the canonical full repository regression gate.
- Newer V3.2 and V3.3 workflows cover stateful duplicate protection and source ingestion through current architecture.

### Coverage not fully equivalent

No tracked current workflow duplicates all of these together:

- live Brave readiness validation;
- two consecutive executions of `scripts/run_daily_pipeline.py`;
- comparison of both live summaries;
- the exact artifact name `v2.6.6-live-dry-run`;
- the complete historical evidence path set.

Therefore the workflow must not be deleted based on unit-test coverage alone. One final manual preservation run is required before disablement.

## 6. Consumers

### Tracked consumers

Repository search found no tracked workflow or script that consumes the artifact name `v2.6.6-live-dry-run` or the generated `dry_run_first.json`, `dry_run_second.json`, and `production_readiness_final.json` files after the run.

The production modules and scripts remain used independently and must not be removed as part of workflow cleanup.

### External and repository-setting consumers

The following remain `MANUAL_VERIFICATION_REQUIRED`:

- branch-protection or required-check dependencies on the workflow/job name;
- operators relying on the Actions entry;
- downloaded artifact links in external records;
- API, dashboard, notification, or compliance consumers outside tracked files;
- actual availability and permissions of `BRAVE_API_KEY`.

## 7. Required final preservation evidence

Before a later disablement PR:

1. Run V2.6.6 manually from commit `6cb22262a18950c045ba8deb4ae70dbc2cc6811e` or a later main commit whose workflow blob remains `a7af4f99e3c6e5b299c2248e8ea2fa3713e057e7`.
2. Use the default limit `2`, unless the operator records another explicit value.
3. Record workflow run ID, run URL, triggering commit SHA, input value, start/end time, conclusion, and job name.
4. Download artifact `v2.6.6-live-dry-run` before its 14-day expiry.
5. Record archive checksum and file inventory.
6. Verify both dry-run summaries parse as JSON.
7. Verify `production_readiness_final.json` contains `dry_run_comparison` and does not expose secret values.
8. Verify `repeat_protection_observed` honestly; do not convert a false result into a pass.
9. Preserve logs sufficient to explain missing optional files or live-source failures.

## 8. Options and recommendation

### Keep unchanged

Use only if operators still require the historical live bundle. Cost: another manual Actions entry and continuing secret dependency.

### Disable after final run — recommended

Remove or neutralize the manual trigger in a dedicated PR while retaining the file history and audit documentation. This reduces operator clutter and is directly reversible.

### Archive or relocate later

Consider only after one release with the workflow disabled and after external-consumer checks. Never delete in the first cleanup pass.

## 9. Future implementation guardrails

A later disablement PR must:

- change only the historical workflow and its focused verification;
- record the then-current commit and workflow blob SHAs;
- preserve the final artifact metadata and checksum in documentation;
- leave `scripts/run_production_readiness.py`, `scripts/run_daily_pipeline.py`, production modules, tests, and financial formulas unchanged;
- keep `tests.yml` green;
- validate YAML;
- confirm branch protection and external consumers manually;
- provide a direct rollback restoring the exact prior workflow blob.

## 10. Rollback

Rollback is a direct revert of the later implementation commit, restoring `.github/workflows/v2.6.6-live-dry-run.yml` byte-for-byte from blob `a7af4f99e3c6e5b299c2248e8ea2fa3713e057e7` or from the implementation PR's recorded pre-change blob if main changes before implementation.

## 11. Wave 4A decision

Wave 4A changes no workflow. The approved next decision is:

```text
FINAL_MANUAL_RUN_THEN_DISABLE_IN_SEPARATE_PR
```

Actual disablement remains blocked until preservation evidence and all `MANUAL_VERIFICATION_REQUIRED` items are resolved or explicitly accepted.