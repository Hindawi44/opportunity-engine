# Operator Workflow Wave 4D — V2.7.2.5 Financial Final-Score Audit v1.0

**Status:** APPROVED — NEXT OPERATOR TASK
**Scope:** coverage audit, preservation planning, and documentation only

## Selected candidate

```text
.github/workflows/v2.7.2.5-external-financial-final-score.yml
```

## Why this candidate was selected

The cleanup plan classifies this workflow as a historical diagnostic and proposes archival or disablement only after the V2.10 verified financial gate is confirmed authoritative.

This candidate is selected before the remaining Wave 4 workflows because:

- V2.10 is already retained in the repository architecture as the authoritative verified-financial integration and decision gate;
- the historical workflow is manual-only and therefore has no routine schedule to remove;
- the candidate has a focused financial/final-score artifact contract that can be compared directly with current V2.10 tests and workflow outputs;
- the first implementation step can remain documentation-only and reversible.

## Objective

Determine whether current V2.10 tests and workflows provide equivalent coverage for the historical V2.7.2.5 financial/final-score behavior, and define the exact preservation bundle required before any disablement proposal.

Wave 4D does not disable, archive, rename, relocate, or modify the historical workflow.

## Required audit work

1. Inspect the historical workflow, its scripts, generated files, artifact name, cache behavior, and inputs.
2. Map each material behavior to current V2.10 tests and the authoritative V2.10 workflow.
3. Record coverage as one of:
   - `COVERED`
   - `PARTIALLY_COVERED`
   - `NOT_COVERED`
   - `MANUAL_VERIFICATION_REQUIRED`
4. Identify any unique historical behavior not reproduced by V2.10, including persistence, external evidence generation, normalization, or artifact composition.
5. Define the final manual-run evidence bundle required before a later reversible-disablement PR.
6. Record external consumers, operator dependence, branch-protection use, and historical links as `MANUAL_VERIFICATION_REQUIRED` unless verified directly.

## Required comparison boundaries

The audit must compare at least:

- verified evidence acceptance;
- financial-score construction;
- final recommendation gating;
- incomplete-economics normalization to an evidence-required outcome;
- prohibition on unsupported BUY decisions;
- persistence of evidence and investment files;
- artifact files and names;
- secret non-disclosure;
- input and threshold behavior.

## Permitted repository changes

Wave 4D may add only:

- one focused coverage-audit document under `docs/`;
- one focused verification test for that document, if needed;
- a project-status update after the audit is accepted.

## Prohibited changes

- Do not modify `.github/workflows/v2.7.2.5-external-financial-final-score.yml`.
- Do not run a disablement or archival change in the audit PR.
- Do not modify production code, financial formulas, scoring thresholds, persistence behavior, or domain scope.
- Do not add purchase, bid, contact, alert, or ranking behavior.
- Do not select a second historical workflow during this task.

## Success criteria

Wave 4D succeeds only when:

1. the V2.7.2.5 workflow contract is documented accurately;
2. current V2.10 coverage is mapped behavior by behavior;
3. gaps and unique historical behavior are recorded honestly;
4. the candidate is classified `READY_FOR_FINAL_PRESERVATION_RUN` or `NOT_READY`;
5. the required final-run evidence bundle and rollback approach are documented;
6. unresolved external facts remain `MANUAL_VERIFICATION_REQUIRED`;
7. no workflow or production-code change occurs;
8. all repository checks pass for the audit PR.

## Next decision

Only after the Wave 4D coverage audit is accepted may a separate task propose a final preservation run. Disablement remains unapproved until preservation evidence is captured and accepted.
