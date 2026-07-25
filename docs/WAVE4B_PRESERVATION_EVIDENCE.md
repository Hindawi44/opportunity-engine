# Wave 4B Preservation Evidence

**Status:** EVIDENCE CAPTURED — PENDING ACCEPTANCE  
**Execution date:** 2026-07-25  
**Scope:** V2.6.6 final manual preservation run only

## Workflow execution

- Workflow: `V2.6.6 Live Dry Run`
- Trigger: manual
- Branch: `main`
- Commit shown in the completed run: `ae24a49`
- Conclusion: `SUCCESS`
- Duration shown in the completed run: `34 seconds`
- Input: `opportunity_limit=2`

## Artifact preservation

- Artifact name: `v2.6.6-live-dry-run`
- Downloaded archive name: `v2.6.6-live-dry-run.zip`
- Download confirmed: yes
- Archive size shown on the operator device: approximately `8.5 KB`

## Verified artifact inventory

The downloaded archive was opened on the operator device. The visible inventory included:

- `production_readiness.json`
- `production_readiness_final.json`
- `todays_opportunities.json`
- `smart_alerts.json`
- `unified-auksjonen-614284.json`

The archive view showed eight files in total. Some filenames were not fully legible in the captured mobile screenshots and are therefore not invented here.

## Production-readiness evidence

The preserved `production_readiness.json` was inspected on the operator device and showed successful checks for:

- Brave secret presence
- request-budget validity
- cache-TTL validity
- daily pipeline script presence
- investment-directory writability
- usage-log-parent writability

The file showed:

```text
ready: true
```

## Evidence not yet independently verified from repository-accessible artifact bytes

The following facts remain unresolved and must not be invented:

- exact workflow run ID and canonical run URL
- workflow blob SHA
- exact start and completion timestamps
- job name
- artifact ID and expiry timestamp
- archive cryptographic checksum
- complete eight-file archive inventory
- JSON validation result for both dry-run summaries
- exact `dry_run_comparison` payload in `production_readiness_final.json`
- exact value of `repeat_protection_observed`
- missing optional files or live-source errors

Status for these facts:

```text
MANUAL_VERIFICATION_REQUIRED
```

## Secret-safety statement

No secret value was copied into this evidence document. The evidence records only whether configuration checks passed.

## Repository-safety statement

Wave 4B made no change to:

- `.github/workflows/v2.6.6-live-dry-run.yml`
- production code
- financial formulas
- domain scope
- purchase, bid, contact, or alert behavior

The historical workflow must not be disabled, archived, renamed, relocated, or deleted in this Wave 4B evidence PR.

## Honest conclusion

The final manual V2.6.6 run completed successfully and its artifact was downloaded and inspected on the operator device. Production-readiness evidence showed `ready: true`.

Wave 4B is not declared fully accepted by this document alone because several required metadata, checksum, complete-inventory, and repeat-protection facts remain `MANUAL_VERIFICATION_REQUIRED`. A later acceptance update may mark Wave 4B complete only after those facts are verified honestly.
