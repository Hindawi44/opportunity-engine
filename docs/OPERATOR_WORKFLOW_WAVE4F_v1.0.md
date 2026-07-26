# Operator Workflow Wave 4F — V2.7.2.2 Internal Score Audit v1.0

**Status:** APPROVED — NEXT OPERATOR TASK  
**Scope:** coverage audit, preservation planning, and documentation only

## Prior accepted result

Wave 4E completed with result:

```text
NOT_READY
```

The historical V2.7.2.3 score-engine trace workflow remains unchanged. Current tests cover its core in-memory parser and calculations but do not reproduce the complete manual live-data, file, CLI, and artifact contract.

## Selected candidate

```text
.github/workflows/v2.7.2.2-internal-score-audit.yml
```

## Why this candidate was selected

This is the next bounded historical-diagnostic candidate because:

- it is manual-only through `workflow_dispatch`;
- it has no schedule and owns no production monitoring;
- it audits a defined internal-score and external-research eligibility threshold contract;
- it produces a bounded validation report and artifact bundle;
- the first step can remain documentation-only and reversible.

Its Brave secret and live dataset dependency increase risk, so selection does not imply readiness for a preservation run or disablement.

## Objective

Determine whether current score, eligibility, and verified-financial tests reproduce the material behavior and artifact contract of the historical V2.7.2.2 workflow. Define the exact evidence required before any later preservation-run or reversible-disablement proposal.

Wave 4F does not modify, run, disable, archive, rename, relocate, or delete the historical workflow.

## Required audit work

1. Inspect `.github/workflows/v2.7.2.2-internal-score-audit.yml`.
2. Inspect `scripts/run_internal_score_audit.py` and its implementation dependencies.
3. Document both manual inputs: `opportunity_limit` and `required_score`.
4. Document the live daily-dataset generation boundary and Brave-related configuration.
5. Map each material score, threshold, eligibility, missing-evidence, and serialization behavior to current tests or retained workflows.
6. Classify each behavior as `COVERED`, `PARTIALLY_COVERED`, `NOT_COVERED`, or `MANUAL_VERIFICATION_REQUIRED`.
7. Identify unique historical execution, output-file, and artifact behavior.
8. Classify the candidate as `READY_FOR_FINAL_PRESERVATION_RUN` or `NOT_READY`.
9. Define the exact future preservation evidence and rollback approach.

## Required comparison boundaries

- opportunity-limit behavior;
- configurable `required_score` threshold behavior;
- internal-score field selection and calculation assumptions;
- external-research eligibility decision;
- missing score or incomplete evidence handling;
- live versus deterministic dataset behavior;
- Brave secret presence and non-disclosure;
- generated validation files;
- `todays_opportunities.json`, scored opportunities, economic evaluation queue, and investment-file inclusion;
- artifact name and complete inventory;
- CLI and file failure behavior;
- GitHub Actions behavior when expected files are absent.

## Permitted repository changes

- one focused coverage-audit document under `docs/`;
- one focused verification test for that document, if required;
- a project-status update after the audit is accepted.

## Prohibited changes

- Do not modify `.github/workflows/v2.7.2.2-internal-score-audit.yml`.
- Do not start a preservation run in the audit PR.
- Do not disable, archive, rename, relocate, or delete the workflow.
- Do not modify production code, score formulas, financial formulas, thresholds, persistence behavior, or domain scope.
- Do not add purchase, bid, contact, alert, recommendation, or ranking behavior.
- Do not select a second historical workflow during this task.

## External facts

Unless directly verified, the following remain:

```text
MANUAL_VERIFICATION_REQUIRED
```

- branch-protection dependence;
- external consumers;
- operator dependence;
- historical artifact links;
- repository-secret availability and ownership.

## Success criteria

1. the historical workflow and internal-score audit contract are documented accurately;
2. current coverage is mapped behavior by behavior;
3. gaps and unique historical behavior are recorded honestly;
4. the candidate is classified `READY_FOR_FINAL_PRESERVATION_RUN` or `NOT_READY`;
5. the exact future preservation evidence and rollback approach are documented;
6. unresolved external facts remain `MANUAL_VERIFICATION_REQUIRED`;
7. no workflow or production-code change occurs;
8. all repository checks pass for the audit PR.

## Next decision

Only after the Wave 4F coverage audit is accepted may a separate task propose a final preservation run. Disablement remains unapproved until preservation evidence is captured and accepted.
