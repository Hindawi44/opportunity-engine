# Operator Workflow Wave 4K — V2.7.2.4.5 Brave Response Content Audit v1.0

**Status:** APPROVED — NEXT OPERATOR TASK  
**Scope:** coverage audit, preservation planning, and documentation only

## Prior accepted result

Wave 4J completed with result:

```text
NOT_READY
```

The historical V2.7.2.4.4 Brave transport workflow remains unchanged because current tracked coverage does not reproduce its complete live-input, secret, request-limit, CLI/file, usage-log, and artifact contract.

## Selected candidate

```text
.github/workflows/v2.7.2.4.5-brave-response-content-audit.yml
```

This is the next remaining historical diagnostic in the accepted cleanup plan. Wave 4 is therefore not complete.

## Why this candidate was selected

This workflow is the next bounded historical diagnostic because:

- it is manual-only through `workflow_dispatch`;
- it has no schedule and owns no continuous monitoring;
- it follows the already audited Brave transport boundary;
- it inspects the content and structure returned by Brave before downstream evidence acceptance;
- it writes both a structured report and raw-response evidence;
- it can be audited without executing or changing the workflow.

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
4. prints only whether the secret is configured and must not disclose its value;
5. creates `data/validation`, `data/investment_files`, and `data/evidence`;
6. generates a fresh opportunity dataset using `opportunity_limit`;
7. runs `scripts/run_brave_response_content_audit.py` using `research_threshold` and `selection_limit`;
8. writes `data/validation/v2.7.2.4.5-brave-response-content-audit.json`;
9. writes raw-response evidence under `data/validation/v2.7.2.4.5-brave-raw-responses`;
10. prints the report when present and emits an explicit message when absent;
11. uploads artifact `v2.7.2.4.5-brave-response-content-audit` with 14-day retention;
12. includes `data/validation/`, `data/todays_opportunities.json`, `data/investment_files/`, and `data/evidence/`;
13. uses `if-no-files-found: warn`;
14. configures `BRAVE_MAX_REQUESTS_PER_RUN=8`, `BRAVE_CACHE_TTL_HOURS=0`, and `EXTERNAL_RESEARCH_MAX_OPPORTUNITIES=0`.

## Objective

Determine whether current Brave provider, response-content, parser, candidate-selection, evidence, raw-response, secret-handling, request-accounting, CLI/file, and artifact tests reproduce the material behavior and evidence boundary of the historical V2.7.2.4.5 workflow.

Wave 4K does not modify, run, disable, archive, rename, relocate, or delete the historical workflow.

## Required audit work

1. Inspect `.github/workflows/v2.7.2.4.5-brave-response-content-audit.yml`.
2. Inspect `scripts/run_brave_response_content_audit.py` and its implementation dependencies.
3. Inspect current Brave response parsing, content inspection, raw-response, provider, candidate-selection, evidence, and CLI tests.
4. Document all three manual inputs and defaults.
5. Document fresh daily-dataset generation and all Brave environment configuration.
6. Map threshold comparison, ranking, tie ordering, selection limiting, and missing-score handling.
7. Map request limit `8`, cache TTL `0`, response status/content type/body structure, result extraction, missing fields, and provider errors.
8. Verify secret presence, explicit missing-secret failure, and non-disclosure behavior.
9. Determine the effective meaning of `EXTERNAL_RESEARCH_MAX_OPPORTUNITIES=0` in this path.
10. Map raw-response creation, naming, sanitization, truncation, persistence, and failure behavior.
11. Map CLI parsing, file reading, JSON serialization, output creation, print behavior, and malformed-input behavior.
12. Map the complete artifact name, inventory, retention, raw-response evidence, and missing-file behavior.
13. Classify each material behavior as `COVERED`, `PARTIALLY_COVERED`, `NOT_COVERED`, or `MANUAL_VERIFICATION_REQUIRED`.
14. Classify the candidate as `READY_FOR_FINAL_PRESERVATION_RUN` or `NOT_READY`.
15. Define exact future preservation evidence and rollback.

## Required comparison boundaries

- `opportunity_limit`, `research_threshold`, and `selection_limit`;
- candidate eligibility, ranking, deterministic ordering, and truncation;
- Brave secret presence, failure, and non-disclosure;
- request maximum `8` and cache TTL `0`;
- effective zero external-research limit;
- live versus deterministic dataset behavior;
- HTTP response metadata and parsed response structure;
- result counts, titles, URLs, snippets, and missing-field behavior;
- raw-response file generation and safe content boundaries;
- generated validation, investment, and evidence files;
- artifact name, complete inventory, and 14-day retention;
- CLI, JSON, file, provider, and GitHub Actions missing-file behavior.

## Permitted repository changes

- one focused coverage-audit document under `docs/`;
- one focused verification test for that document, if required;
- a project-status update after the audit is accepted.

## Prohibited changes

- Do not modify or run `.github/workflows/v2.7.2.4.5-brave-response-content-audit.yml`.
- Do not start a preservation run in the audit PR.
- Do not disable, archive, rename, relocate, or delete the workflow.
- Do not modify production code, scoring formulas, financial formulas, thresholds, persistence behavior, or domain scope.
- Do not execute external research.
- Do not expose any secret or unsafe raw-response content.
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
- Brave account quota and billing state;
- hosted cache continuity;
- privacy or retention requirements for raw external responses.

## Success criteria

1. the historical response-content workflow contract is documented accurately;
2. current coverage is mapped behavior by behavior;
3. secret, request, response, raw-file, CLI, and artifact gaps are recorded honestly;
4. no secret or unsafe raw content is exposed;
5. the candidate is classified `READY_FOR_FINAL_PRESERVATION_RUN` or `NOT_READY`;
6. exact future preservation evidence and rollback are documented;
7. unresolved external facts remain `MANUAL_VERIFICATION_REQUIRED`;
8. no workflow or production-code change occurs;
9. all repository checks pass for the audit PR.

## Next decision

Only after the Wave 4K coverage audit is accepted may a separate task propose a final preservation run. Disablement or archival remains unapproved until preservation evidence is captured and accepted.
