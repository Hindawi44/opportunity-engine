# Operator Workflow Wave 4G — V2.7.2.4.1 Research Candidate Audit v1.0

**Status:** APPROVED — NEXT OPERATOR TASK  
**Scope:** coverage audit, preservation planning, and documentation only

## Post-Wave 4F reconciliation result

The accepted cleanup inventory was reconciled against completed Wave 4 work.

Already handled candidates are excluded:

- `v2.6.6-live-dry-run.yml` — preservation evidence accepted and reversibly made non-routine;
- `v2.7.2.5-external-financial-final-score.yml` — Wave 4D result `NOT_READY`;
- `v2.7.2.3-score-engine-trace-audit.yml` — Wave 4E result `NOT_READY`;
- `v2.7.2.2-internal-score-audit.yml` — Wave 4F result `NOT_READY`.

The next remaining historical-diagnostic candidate in the accepted file-by-file cleanup plan is selected below. Wave 4 is therefore not yet complete.

## Selected candidate

```text
.github/workflows/v2.7.2.4.1-research-candidate-audit.yml
```

## Why this candidate was selected

This is the next bounded historical-diagnostic candidate because:

- it is manual-only through `workflow_dispatch`;
- it has no schedule and does not own continuous production monitoring;
- the accepted cleanup plan places it immediately after the already handled V2.7.2.2 and V2.7.2.3 candidates;
- it audits a defined preliminary research-candidate threshold and selection-limit contract;
- it produces a bounded validation report and artifact bundle;
- the first step can remain documentation-only and reversible.

Selection does not imply readiness for a preservation run, disablement, archival, relocation, rename, or deletion.

## Historical workflow contract to audit

The workflow exposes three required manual inputs:

```text
opportunity_limit = 20
research_threshold = 25
selection_limit = 3
```

It:

1. checks out the repository;
2. installs Python 3.11 dependencies;
3. verifies the project import;
4. creates `data/validation` and `data/investment_files`;
5. runs `scripts/run_daily_pipeline.py` against a fresh real dataset using `opportunity_limit`;
6. runs `scripts/run_research_candidate_audit.py` with `research_threshold` and `selection_limit`;
7. writes `data/validation/v2.7.2.4.1-research-candidates.json`;
8. prints the report when present and emits an explicit message when absent;
9. uploads artifact `v2.7.2.4.1-research-candidate-audit` with 14-day retention;
10. includes `data/validation/`, `data/todays_opportunities.json`, and `data/investment_files/` in the artifact boundary;
11. uses `if-no-files-found: warn`;
12. sets `EXTERNAL_RESEARCH_MAX_OPPORTUNITIES=0`, so the workflow audits candidate selection without executing external research.

## Objective

Determine whether current external-research candidate-selection tests or retained workflows reproduce the material behavior, file boundaries, and artifact contract of the historical V2.7.2.4.1 workflow. Define the exact evidence required before any later preservation-run or reversible-disablement proposal.

Wave 4G does not modify, run, disable, archive, rename, relocate, or delete the historical workflow.

## Required audit work

1. Inspect `.github/workflows/v2.7.2.4.1-research-candidate-audit.yml`.
2. Inspect `scripts/run_research_candidate_audit.py` and its implementation dependencies.
3. Inspect current external-research candidate-selection tests and retained workflows.
4. Document all three manual inputs and their defaults.
5. Document the fresh daily-dataset generation boundary.
6. Map threshold comparison, ranking, deterministic ordering, selection limiting, missing-score behavior, and eligibility behavior to current coverage.
7. Confirm that candidate auditing remains separate from external-research execution.
8. Map CLI parsing, file reading, JSON serialization, output creation, print behavior, and failure behavior.
9. Map the complete artifact name, inventory, retention, and missing-file behavior.
10. Classify each material behavior as `COVERED`, `PARTIALLY_COVERED`, `NOT_COVERED`, or `MANUAL_VERIFICATION_REQUIRED`.
11. Classify the candidate as `READY_FOR_FINAL_PRESERVATION_RUN` or `NOT_READY`.
12. Define the exact future preservation evidence and rollback approach.

## Required comparison boundaries

- `opportunity_limit` behavior;
- configurable `research_threshold` behavior;
- configurable `selection_limit` behavior;
- candidate score-field selection and numeric assumptions;
- threshold inclusivity or exclusivity;
- candidate ranking and tie ordering;
- truncation to the requested selection limit;
- missing, invalid, or incomplete score handling;
- live versus deterministic dataset behavior;
- separation between selection and external-research execution;
- generated validation files;
- `todays_opportunities.json` and investment-file inclusion;
- artifact name and complete inventory;
- CLI and file failure behavior;
- GitHub Actions behavior when expected files are absent.

## Permitted repository changes

- one focused coverage-audit document under `docs/`;
- one focused verification test for that document, if required;
- a project-status update after the audit is accepted.

## Prohibited changes

- Do not modify `.github/workflows/v2.7.2.4.1-research-candidate-audit.yml`.
- Do not start a preservation run in the audit PR.
- Do not disable, archive, rename, relocate, or delete the workflow.
- Do not modify production code, scoring formulas, financial formulas, thresholds, persistence behavior, or domain scope.
- Do not enable or execute external research.
- Do not add purchase, bid, contact, alert, recommendation, or investment-ranking behavior.
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
- repository-setting dependencies;
- ownership of any external-research operational process.

## Success criteria

1. the historical workflow and research-candidate audit contract are documented accurately;
2. current coverage is mapped behavior by behavior;
3. gaps and unique historical behavior are recorded honestly;
4. selection remains distinct from external-research execution;
5. the candidate is classified `READY_FOR_FINAL_PRESERVATION_RUN` or `NOT_READY`;
6. exact future preservation evidence and rollback are documented;
7. unresolved external facts remain `MANUAL_VERIFICATION_REQUIRED`;
8. no workflow or production-code change occurs;
9. all repository checks pass for the audit PR.

## Next decision

Only after the Wave 4G coverage audit is accepted may a separate task propose a final preservation run. Disablement or archival remains unapproved until preservation evidence is captured and accepted.