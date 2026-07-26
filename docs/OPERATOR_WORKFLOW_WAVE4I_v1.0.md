# Operator Workflow Wave 4I — V2.7.2.4.3 External Evidence Execution Audit v1.0

**Status:** APPROVED — NEXT OPERATOR TASK  
**Scope:** coverage audit, preservation planning, and documentation only

## Prior accepted result

Wave 4H completed with result:

```text
NOT_READY
```

The historical V2.7.2.4.2 bootstrap integration workflow remains unchanged because current tests do not reproduce its complete live dataset, CLI/file, Brave cache/usage, and artifact contract.

## Selected candidate

```text
.github/workflows/v2.7.2.4.3-external-evidence-execution-audit.yml
```

## Why this candidate was selected

This is the next remaining historical-diagnostic candidate in the accepted cleanup plan because:

- it is manual-only through `workflow_dispatch`;
- it has no schedule and owns no continuous monitoring;
- it follows the already audited candidate-selection and bootstrap boundaries;
- it requires a configured Brave secret and explicitly audits external-evidence execution;
- it has bounded request, cache, report, and artifact behavior;
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
3. requires `BRAVE_API_KEY` and fails explicitly when absent;
4. prints only whether the secret is configured and must not disclose it;
5. creates `data/validation`, `data/investment_files`, and `data/evidence`;
6. generates a fresh opportunity dataset through `scripts/run_daily_pipeline.py` using `opportunity_limit`;
7. runs `scripts/run_external_execution_audit.py` using `research_threshold` and `selection_limit`;
8. writes `data/validation/v2.7.2.4.3-external-execution-audit.json`;
9. prints the report when present and emits an explicit message when absent;
10. uploads artifact `v2.7.2.4.3-external-evidence-execution-audit` with 14-day retention;
11. includes `data/validation/`, `data/todays_opportunities.json`, `data/investment_files/`, `data/evidence/`, `data/brave_cache/`, and `data/brave_usage.jsonl`;
12. uses `if-no-files-found: warn`;
13. configures `BRAVE_MAX_REQUESTS_PER_RUN=6`, `BRAVE_CACHE_TTL_HOURS=0`, and `EXTERNAL_RESEARCH_MAX_OPPORTUNITIES=0`.

## Objective

Determine whether current external-evidence, Brave transport, evidence persistence, comparable, buyer, bootstrap, and verified-financial tests reproduce the material behavior, secret boundary, request/cache limits, file outputs, and artifact contract of the historical V2.7.2.4.3 workflow. Define the exact evidence required before any later preservation-run or reversible-disablement proposal.

Wave 4I does not modify, run, disable, archive, rename, relocate, or delete the historical workflow.

## Required audit work

1. Inspect `.github/workflows/v2.7.2.4.3-external-evidence-execution-audit.yml`.
2. Inspect `scripts/run_external_execution_audit.py` and its implementation dependencies.
3. Inspect current external-evidence, Brave provider, evidence store, comparables, buyer-discovery, bootstrap, and V2.8–V2.10 boundary tests.
4. Document all three manual inputs and defaults.
5. Document the fresh daily-dataset boundary and all Brave-related environment configuration.
6. Map candidate threshold, ordering, selection limiting, execution gating, request accounting, cache behavior, evidence creation/update, comparables, buyers, and per-candidate error isolation.
7. Verify secret presence, explicit missing-secret failure, and non-disclosure behavior.
8. Determine the effective meaning of `EXTERNAL_RESEARCH_MAX_OPPORTUNITIES=0` in this execution-audit path.
9. Map CLI parsing, file reading, investment-file synchronization, JSON serialization, output creation, print behavior, and failure behavior.
10. Map the complete artifact name, inventory, retention, cache/usage evidence, and missing-file behavior.
11. Classify each material behavior as `COVERED`, `PARTIALLY_COVERED`, `NOT_COVERED`, or `MANUAL_VERIFICATION_REQUIRED`.
12. Classify the candidate as `READY_FOR_FINAL_PRESERVATION_RUN` or `NOT_READY`.
13. Define exact future preservation evidence and rollback.

## Required comparison boundaries

- `opportunity_limit` behavior;
- configurable `research_threshold` behavior;
- configurable `selection_limit` behavior;
- candidate score, eligibility, ranking, tie ordering, and truncation;
- Brave secret presence, missing-secret failure, and non-disclosure;
- request maximum `6` and cache TTL `0` behavior;
- effective `EXTERNAL_RESEARCH_MAX_OPPORTUNITIES=0` behavior;
- actual external-evidence execution versus disabled or skipped execution;
- evidence created and updated;
- comparables and buyer results;
- per-candidate failure isolation;
- live versus deterministic dataset behavior;
- investment-file synchronization and persistence;
- generated validation, evidence, cache, and usage files;
- artifact name, complete inventory, and 14-day retention;
- CLI, JSON, file, and GitHub Actions missing-file behavior.

## Permitted repository changes

- one focused coverage-audit document under `docs/`;
- one focused verification test for that document, if required;
- a project-status update after the audit is accepted.

## Prohibited changes

- Do not modify `.github/workflows/v2.7.2.4.3-external-evidence-execution-audit.yml`.
- Do not start a preservation run in the audit PR.
- Do not disable, archive, rename, relocate, or delete the workflow.
- Do not modify production code, scoring formulas, financial formulas, thresholds, persistence behavior, or domain scope.
- Do not execute external research during this documentation-only task.
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
- hosted cache continuity;
- Brave account quota and billing state.

## Success criteria

1. the historical external-evidence execution contract is documented accurately;
2. current coverage is mapped behavior by behavior;
3. secret, request, cache, execution, persistence, and artifact gaps are recorded honestly;
4. no secret value is exposed;
5. the candidate is classified `READY_FOR_FINAL_PRESERVATION_RUN` or `NOT_READY`;
6. exact future preservation evidence and rollback are documented;
7. unresolved external facts remain `MANUAL_VERIFICATION_REQUIRED`;
8. no workflow or production-code change occurs;
9. all repository checks pass for the audit PR.

## Next decision

Only after the Wave 4I coverage audit is accepted may a separate task propose a final preservation run. Disablement or archival remains unapproved until preservation evidence is captured and accepted.
