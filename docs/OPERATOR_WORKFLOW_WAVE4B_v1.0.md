# Operator Workflow Wave 4B — V2.6.6 Final Preservation Run v1.0

**Status:** APPROVED — NEXT OPERATOR TASK  
**Scope:** manual execution, evidence capture, and documentation only

## Accepted prerequisite

Wave 4A completed the repository audit of:

```text
.github/workflows/v2.6.6-live-dry-run.yml
```

The accepted decision is:

```text
FINAL_MANUAL_RUN_THEN_DISABLE_IN_SEPARATE_PR
```

## Objective

Run the historical V2.6.6 workflow manually one final time from `main`, preserve its evidence before the 14-day artifact expiry, and record enough metadata to support a later reversible disablement decision.

## Required operator action

1. Open GitHub Actions.
2. Select `V2.6.6 Live Dry Run`.
3. Choose `Run workflow` on `main`.
4. Keep `opportunity_limit` at the default value `2`, unless another value is explicitly recorded.
5. Wait for the run to complete.
6. Do not treat a failed run or a false repeat-protection result as success.

## Evidence that must be preserved

Record all of the following:

- workflow run ID and URL;
- triggering commit SHA;
- workflow blob SHA if still available;
- input value;
- start and completion times;
- conclusion and job name;
- artifact name `v2.6.6-live-dry-run`;
- artifact ID and expiry date;
- downloaded archive checksum;
- archive file inventory;
- whether both dry-run summaries are valid JSON;
- whether `production_readiness_final.json` contains `dry_run_comparison`;
- the honest value of `repeat_protection_observed`;
- any missing optional files or live-source errors;
- confirmation that no secret value appears in preserved evidence.

## Expected artifact paths

```text
data/production_readiness*.json
data/dry_run_*.json
data/todays_opportunities.json
data/smart_alerts.json
data/investment_files/
data/brave_usage.jsonl
```

Because the workflow uses `if-no-files-found: warn`, workflow success alone is not sufficient. The downloaded archive must be inspected.

## Permitted repository changes

Wave 4B may add only:

- one preservation-evidence document under `docs/` after the manual run;
- one focused verification test for that document, if needed;
- a status update after the evidence is accepted.

## Prohibited changes

Do not modify, disable, rename, relocate, archive, or delete the V2.6.6 workflow in Wave 4B.

Do not modify production code, scripts, financial formulas, domain scope, or purchase, bid, contact, and alert behavior.

## External checks

The following remain `MANUAL_VERIFICATION_REQUIRED` before later disablement:

- branch-protection dependence on the workflow or job name;
- operators relying on the Actions entry;
- external links to historical artifacts;
- dashboards, APIs, notifications, or compliance consumers outside tracked files;
- availability and permission of `BRAVE_API_KEY`.

## Success criteria

Wave 4B succeeds only when:

1. the final manual run is completed honestly;
2. run metadata and the artifact are preserved before expiry;
3. archive checksum and file inventory are recorded;
4. the dry-run comparison result is recorded without alteration;
5. secret values are not exposed;
6. unresolved external facts remain `MANUAL_VERIFICATION_REQUIRED`;
7. no workflow or production-code change occurs;
8. all repository checks pass for the evidence PR.

## Next decision

Only after Wave 4B evidence is accepted may a separate Wave 4C PR propose a reversible disablement of the historical workflow. Deletion is not approved.