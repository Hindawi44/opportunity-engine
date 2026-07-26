# Operator Workflow Wave 4H — V2.7.2.4.2 Bootstrap Pipeline Integration v1.0

**Status:** APPROVED — NEXT OPERATOR TASK  
**Scope:** coverage audit, preservation planning, and documentation only

## Prior accepted result

Wave 4G completed with result:

```text
NOT_READY
```

The historical V2.7.2.4.1 research-candidate workflow remains unchanged because current tests do not reproduce its complete live dataset, CLI/file, and artifact contract.

## Selected candidate

```text
.github/workflows/v2.7.2.4.2-bootstrap-pipeline-integration.yml
```

## Why this candidate was selected

This is the next remaining historical-diagnostic candidate in the accepted cleanup plan because:

- it is manual-only through `workflow_dispatch`;
- it has no schedule and owns no continuous monitoring;
- it follows the already audited V2.7.2.4.1 candidate-selection boundary;
- it integrates fresh opportunity generation with bootstrap external-research queue preparation;
- external research execution remains disabled through `EXTERNAL_RESEARCH_MAX_OPPORTUNITIES=0`;
- it produces a bounded report and artifact bundle;
- the first step can remain documentation-only and reversible.

Selection does not imply readiness for a preservation run, disablement, archival, relocation, rename, or deletion.

## Historical workflow contract to audit

The workflow exposes three required manual inputs:

```text
opportunity_limit = 20
research_threshold = 25
selection_limit = 3
```

It also:

1. checks out the repository;
2. installs Python 3.11 dependencies;
3. verifies the project import;
4. creates `data/validation`, `data/investment_files`, and `data/evidence`;
5. generates a fresh real dataset through `scripts/run_daily_pipeline.py` using `opportunity_limit`;
6. runs `scripts/run_research_bootstrap.py` using `research_threshold` and `selection_limit`;
7. writes `data/validation/v2.7.2.4.2-bootstrap-report.json`;
8. prints the report when present and emits an explicit message when absent;
9. uploads artifact `v2.7.2.4.2-bootstrap-pipeline-integration` with 14-day retention;
10. includes `data/validation/`, `data/todays_opportunities.json`, `data/investment_files/`, `data/evidence/`, `data/brave_cache/`, and `data/brave_usage.jsonl`;
11. uses `if-no-files-found: warn`;
12. configures `BRAVE_API_KEY`, request limit `4`, cache TTL `24`, and disables external-research execution with `EXTERNAL_RESEARCH_MAX_OPPORTUNITIES=0`.

## Objective

Determine whether current bootstrap, candidate-selection, external-research, evidence, and verified-financial tests reproduce the material behavior, file boundaries, secret handling, and artifact contract of the historical V2.7.2.4.2 workflow. Define the exact evidence required before any later preservation-run or reversible-disablement proposal.

Wave 4H does not modify, run, disable, archive, rename, relocate, or delete the historical workflow.

## Required audit work

1. Inspect `.github/workflows/v2.7.2.4.2-bootstrap-pipeline-integration.yml`.
2. Inspect `scripts/run_research_bootstrap.py` and its implementation dependencies.
3. Inspect current bootstrap, candidate-selection, external-research, evidence, and V2.8–V2.10 boundary tests.
4. Document all three manual inputs and defaults.
5. Document fresh daily-dataset generation and Brave configuration.
6. Map threshold comparison, deterministic ordering, selection limiting, queue construction, missing-score behavior, and evidence placeholders to current coverage.
7. Confirm that external-research execution remains disabled in this historical workflow.
8. Map CLI parsing, file reading, JSON serialization, output creation, print behavior, and failure behavior.
9. Map the complete artifact name, inventory, retention, cache/usage evidence, and missing-file behavior.
10. Classify each material behavior as `COVERED`, `PARTIALLY_COVERED`, `NOT_COVERED`, or `MANUAL_VERIFICATION_REQUIRED`.
11. Classify the candidate as `READY_FOR_FINAL_PRESERVATION_RUN` or `NOT_READY`.
12. Define exact future preservation evidence and rollback.

## Required comparison boundaries

- `opportunity_limit` behavior;
- configurable `research_threshold` behavior;
- configurable `selection_limit` behavior;
- candidate score and eligibility assumptions;
- ranking and tie ordering;
- truncation to the selection limit;
- bootstrap queue schema and serialization;
- missing, invalid, or incomplete input handling;
- live versus deterministic dataset behavior;
- Brave secret presence and non-disclosure;
- request-limit and cache-TTL configuration;
- disabled external-research execution;
- generated validation and evidence files;
- `todays_opportunities.json`, investment files, evidence directory, Brave cache, and usage-log inclusion;
- artifact name and complete inventory;
- CLI and file failure behavior;
- GitHub Actions behavior when expected files are absent.

## Permitted repository changes

- one focused coverage-audit document under `docs/`;
- one focused verification test for that document, if required;
- a project-status update after the audit is accepted.

## Prohibited changes

- Do not modify `.github/workflows/v2.7.2.4.2-bootstrap-pipeline-integration.yml`.
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
- repository-secret availability and ownership;
- ownership of external-research operations;
- hosted cache continuity.

## Success criteria

1. the historical bootstrap workflow contract is documented accurately;
2. current coverage is mapped behavior by behavior;
3. gaps and unique historical behavior are recorded honestly;
4. external-research execution remains disabled and distinct from queue preparation;
5. the candidate is classified `READY_FOR_FINAL_PRESERVATION_RUN` or `NOT_READY`;
6. exact future preservation evidence and rollback are documented;
7. unresolved external facts remain `MANUAL_VERIFICATION_REQUIRED`;
8. no workflow or production-code change occurs;
9. all repository checks pass for the audit PR.

## Next decision

Only after the Wave 4H coverage audit is accepted may a separate task propose a final preservation run. Disablement or archival remains unapproved until preservation evidence is captured and accepted.
