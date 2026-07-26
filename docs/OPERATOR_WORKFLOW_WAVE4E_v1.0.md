# Operator Workflow Wave 4E — V2.7.2.3 Score Engine Trace Audit v1.0

**Status:** APPROVED — NEXT OPERATOR TASK
**Scope:** coverage audit, trace-preservation planning, and documentation only

## Selected candidate

```text
.github/workflows/v2.7.2.3-score-engine-trace-audit.yml
```

## Why this candidate was selected

This candidate is the lowest-risk remaining Wave 4 historical diagnostic because:

- it is manual-only through `workflow_dispatch`;
- it has no Brave secret or external-provider requirement;
- it does not own production scheduling, alerts, purchasing, bidding, contact, or financial formulas;
- its unique contract is bounded: generate a dataset, produce one score-engine trace report, and upload a trace artifact bundle;
- the first implementation step can remain documentation-only and fully reversible.

## Objective

Determine whether current score-engine tests and retained acceptance workflows reproduce the material behavior and trace contract of the historical V2.7.2.3 workflow, and define the exact evidence bundle required before any later preservation-run or disablement proposal.

Wave 4E does not modify, disable, archive, rename, relocate, or delete the historical workflow.

## Required audit work

1. Inspect the historical workflow and `scripts/run_score_engine_trace_audit.py`.
2. Document the trace schema, inputs, generated files, artifact name, and failure behavior.
3. Map every material trace field and score-engine boundary to current tests and retained workflows.
4. Classify each behavior as `COVERED`, `PARTIALLY_COVERED`, `NOT_COVERED`, or `MANUAL_VERIFICATION_REQUIRED`.
5. Identify unique historical trace behavior not reproduced by current tests.
6. Define the final manual-run evidence bundle required before any later reversible-disablement proposal.
7. Keep external consumers, operator dependence, branch protection, and historical links as `MANUAL_VERIFICATION_REQUIRED` unless verified directly.

## Required comparison boundaries

- opportunity input and limit behavior;
- score component calculation traceability;
- ordering and ranking behavior;
- missing-evidence handling;
- recommendation and decision trace fields;
- deterministic versus live-data behavior;
- generated validation files;
- artifact name and complete artifact inventory;
- secret non-disclosure;
- failure behavior when expected files are absent.

## Permitted repository changes

- one focused coverage-audit document under `docs/`;
- one focused verification test for that document, if needed;
- a project-status update after the audit is accepted.

## Prohibited changes

- Do not modify `.github/workflows/v2.7.2.3-score-engine-trace-audit.yml`.
- Do not run a preservation, disablement, or archival change in the audit PR.
- Do not modify production code, score formulas, financial formulas, thresholds, persistence behavior, or domain scope.
- Do not add purchase, bid, contact, alert, or ranking behavior.
- Do not select a second historical workflow during this task.

## Success criteria

1. the V2.7.2.3 workflow and trace contract are documented accurately;
2. current coverage is mapped field by field and behavior by behavior;
3. gaps and unique historical trace behavior are recorded honestly;
4. the candidate is classified `READY_FOR_FINAL_PRESERVATION_RUN` or `NOT_READY`;
5. the exact future preservation evidence and rollback approach are documented;
6. unresolved external facts remain `MANUAL_VERIFICATION_REQUIRED`;
7. no workflow or production-code change occurs;
8. all repository checks pass for the audit PR.

## Next decision

Only after the Wave 4E coverage audit is accepted may a separate task propose a final preservation run. Disablement remains unapproved until preservation evidence is captured and accepted.
