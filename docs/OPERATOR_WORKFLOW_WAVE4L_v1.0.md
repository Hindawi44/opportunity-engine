# Operator Workflow Wave 4L — V2.7.2.4.7 Comparable Acceptance Audit v1.0

**Status:** APPROVED — NEXT OPERATOR TASK  
**Scope:** coverage audit, preservation planning, and documentation only

## Post-Wave 4K checkpoint result

The accepted cleanup plan contains ten workflows classified as `HISTORICAL_DIAGNOSTIC`.

Nine have already been handled through Wave 4K:

- `v2.6.6-live-dry-run.yml`
- `v2.7.2.2-internal-score-audit.yml`
- `v2.7.2.3-score-engine-trace-audit.yml`
- `v2.7.2.4.1-research-candidate-audit.yml`
- `v2.7.2.4.2-bootstrap-pipeline-integration.yml`
- `v2.7.2.4.3-external-evidence-execution-audit.yml`
- `v2.7.2.4.4-brave-transport-response-audit.yml`
- `v2.7.2.4.5-brave-response-content-audit.yml`
- `v2.7.2.5-external-financial-final-score.yml`

Exactly one historical diagnostic remains:

```text
.github/workflows/v2.7.2.4.7-comparable-acceptance-audit.yml
```

Wave 4 is therefore not complete. This workflow is selected as the one and only next candidate.

## Why this candidate was selected

The accepted cleanup plan assigns this workflow to Wave 4 and proposes archival only after equivalence with V2.8.2 and V2.8.2B comparable-acceptance coverage is verified.

It is bounded because:

- it is manual-only through `workflow_dispatch`;
- it has no schedule and owns no continuous monitoring;
- it evaluates the historical comparable-acceptance boundary immediately before the retained V2.8 comparable workflows;
- it can be audited without executing or changing the workflow.

Selection does not imply readiness for a preservation run, disablement, archival, relocation, rename, or deletion.

## Historical workflow contract to audit

The workflow exposes four required manual inputs:

```text
opportunity_limit = 20
research_threshold = 25
selection_limit = 3
row_limit = 20
```

It also:

1. checks out the repository;
2. installs Python 3.11 dependencies;
3. requires `BRAVE_API_KEY` and fails explicitly when absent;
4. prints only whether the secret is configured and must not disclose its value;
5. creates `data/validation`, `data/investment_files`, and `data/evidence`;
6. generates a fresh opportunity dataset using `opportunity_limit`;
7. runs `scripts/run_comparable_acceptance_audit.py` using `research_threshold`, `selection_limit`, and `row_limit`;
8. writes `data/validation/v2.7.2.4.7-comparable-acceptance-audit.json`;
9. prints the report when present and emits an explicit message when absent;
10. uploads artifact `v2.7.2.4.7-comparable-acceptance-audit` with 14-day retention;
11. includes `data/validation/`, `data/todays_opportunities.json`, `data/investment_files/`, `data/evidence/`, and `data/brave_usage.jsonl`;
12. uses `if-no-files-found: warn`;
13. configures `BRAVE_MAX_REQUESTS_PER_RUN=8`, `BRAVE_CACHE_TTL_HOURS=0`, and `EXTERNAL_RESEARCH_MAX_OPPORTUNITIES=0`.

## Objective

Determine whether current comparable extraction, candidate selection, evidence acceptance, row limiting, Brave request accounting, CLI/file behavior, V2.8.2/V2.8.2B tests, secret handling, and artifact coverage reproduce the material behavior and evidence boundary of the historical V2.7.2.4.7 workflow.

Wave 4L does not modify, run, disable, archive, rename, relocate, or delete the historical workflow.

## Required audit work

1. Inspect `.github/workflows/v2.7.2.4.7-comparable-acceptance-audit.yml`.
2. Inspect `scripts/run_comparable_acceptance_audit.py` and its implementation dependencies.
3. Inspect current comparable extraction, comparable evidence, candidate-selection, acceptance, provider, CLI, and V2.8.2/V2.8.2B tests.
4. Document all four manual inputs and defaults.
5. Document fresh daily-dataset generation and all Brave environment configuration.
6. Map threshold comparison, ranking, deterministic ordering, selection limiting, missing-score handling, and `row_limit` enforcement.
7. Map comparable acceptance criteria, accepted/rejected rows, missing fields, duplicates, malformed rows, evidence creation or update, and downstream file synchronization.
8. Verify secret presence, explicit missing-secret failure, and non-disclosure behavior.
9. Determine the effective meaning of `EXTERNAL_RESEARCH_MAX_OPPORTUNITIES=0` in this path.
10. Map request maximum `8`, cache TTL `0`, Brave usage-log generation, and provider failure behavior.
11. Map CLI parsing, dataset/file reading, JSON serialization, output creation, print behavior, and malformed-input behavior.
12. Compare the historical contract with retained V2.8.2 and V2.8.2B acceptance coverage without changing those workflows.
13. Map the complete artifact name, inventory, retention, and missing-file behavior.
14. Classify each material behavior as `COVERED`, `PARTIALLY_COVERED`, `NOT_COVERED`, or `MANUAL_VERIFICATION_REQUIRED`.
15. Classify the candidate as `READY_FOR_FINAL_PRESERVATION_RUN` or `NOT_READY`.
16. Define exact future preservation evidence and rollback.

## Required comparison boundaries

- `opportunity_limit`, `research_threshold`, `selection_limit`, and `row_limit`;
- candidate eligibility, ranking, deterministic ordering, and truncation;
- comparable extraction, normalization, acceptance, rejection, duplication, and missing-field behavior;
- Brave secret presence, missing-secret failure, and non-disclosure;
- request maximum `8`, cache TTL `0`, usage logging, and effective zero external-research limit;
- live versus deterministic dataset behavior;
- generated validation, investment, evidence, and usage files;
- equivalence with V2.8.2 and V2.8.2B comparable-acceptance boundaries;
- artifact name, complete inventory, 14-day retention, and missing-file behavior;
- CLI, JSON, file, provider, and GitHub Actions failure behavior.

## Permitted repository changes

- one focused coverage-audit result document under `docs/`;
- one focused verification test for that document, if required;
- a project-status update after the audit is accepted.

## Prohibited changes

- Do not modify or run `.github/workflows/v2.7.2.4.7-comparable-acceptance-audit.yml`.
- Do not start a preservation run in the audit PR.
- Do not disable, archive, rename, relocate, or delete the workflow.
- Do not modify V2.8.2 or V2.8.2B workflows.
- Do not modify production code, scoring formulas, financial formulas, thresholds, persistence behavior, or domain scope.
- Do not execute external research.
- Do not expose any secret or unsafe external response.
- Do not select a second workflow during this task.

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
- Brave account quota and billing state;
- hosted cache continuity;
- privacy or retention requirements for external evidence and usage logs.

## Success criteria

1. the historical comparable-acceptance workflow contract is documented accurately;
2. current coverage is mapped behavior by behavior;
3. V2.8.2/V2.8.2B equivalence and all material gaps are recorded honestly;
4. no secret or unsafe external content is exposed;
5. the candidate is classified `READY_FOR_FINAL_PRESERVATION_RUN` or `NOT_READY`;
6. exact future preservation evidence and rollback are documented;
7. unresolved external facts remain `MANUAL_VERIFICATION_REQUIRED`;
8. no workflow or production-code change occurs;
9. all repository checks pass for the audit PR.

## Next decision

Only after the Wave 4L coverage audit is accepted may a separate task decide whether a final preservation run is justified. If Wave 4L is completed and no new historical diagnostic is introduced by an accepted plan change, the subsequent checkpoint may formally close Wave 4.