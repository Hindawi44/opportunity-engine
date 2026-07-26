# Operator Workflow Wave 4J — V2.7.2.4.4 Brave Transport & Response Audit v1.0

**Status:** APPROVED — NEXT OPERATOR TASK  
**Scope:** coverage audit, preservation planning, and documentation only

## Prior accepted result

Wave 4I completed with result `NOT_READY`. The historical V2.7.2.4.3 workflow remains unchanged.

## Selected candidate

```text
.github/workflows/v2.7.2.4.4-brave-transport-response-audit.yml
```

This is the next remaining historical diagnostic in the accepted cleanup plan. Wave 4 is therefore not complete.

## Historical workflow contract

The workflow is manual-only and exposes:

```text
opportunity_limit = 20
research_threshold = 25
selection_limit = 3
```

It requires `BRAVE_API_KEY`, fails explicitly when the secret is absent, and must not print the secret value. It configures:

```text
BRAVE_MAX_REQUESTS_PER_RUN = 4
BRAVE_CACHE_TTL_HOURS = 0
EXTERNAL_RESEARCH_MAX_OPPORTUNITIES = 0
```

It generates a fresh dataset, runs `scripts/run_brave_transport_audit.py`, writes `data/validation/v2.7.2.4.4-brave-transport-response-audit.json`, prints the report when present, and uploads artifact `v2.7.2.4.4-brave-transport-response-audit` with 14-day retention.

The artifact boundary includes:

- `data/validation/`
- `data/todays_opportunities.json`
- `data/investment_files/`
- `data/evidence/`
- `data/brave_usage.jsonl`

It uses `if-no-files-found: warn`.

## Objective

Determine whether current Brave provider, transport, response-shape, request-accounting, secret-handling, candidate-selection, and evidence tests reproduce the material behavior, file boundaries, and artifact contract of the historical workflow.

Wave 4J does not modify, run, disable, archive, rename, relocate, or delete the workflow.

## Required audit work

1. Inspect the workflow and `scripts/run_brave_transport_audit.py` with its implementation dependencies.
2. Inspect current Brave transport, provider, response, request-accounting, candidate-selection, and evidence tests.
3. Map all three manual inputs and defaults.
4. Map fresh dataset generation.
5. Verify secret presence, missing-secret failure, and non-disclosure coverage.
6. Map request maximum `4`, cache TTL `0`, transport execution, response counts, HTTPS/title/content boundaries, and provider errors.
7. Determine the effective meaning of `EXTERNAL_RESEARCH_MAX_OPPORTUNITIES=0` in this path.
8. Map CLI parsing, file reading, JSON serialization, output creation, print behavior, and failure behavior.
9. Map artifact name, inventory, retention, usage evidence, and missing-file behavior.
10. Classify every material behavior as `COVERED`, `PARTIALLY_COVERED`, `NOT_COVERED`, or `MANUAL_VERIFICATION_REQUIRED`.
11. Classify the candidate as `READY_FOR_FINAL_PRESERVATION_RUN` or `NOT_READY`.
12. Define exact future preservation evidence and rollback.

## Required comparison boundaries

- manual inputs and defaults;
- candidate threshold, ordering, selection, and truncation;
- secret presence, missing-secret failure, and non-disclosure;
- request limit `4` and cache TTL `0`;
- effective zero external-research limit;
- Brave request execution and accounting;
- response shape and result counts;
- provider and transport errors;
- live versus deterministic dataset behavior;
- generated validation and usage files;
- complete artifact contract and 14-day retention;
- CLI, JSON, file, and GitHub Actions missing-file behavior.

## Permitted repository changes

- one focused coverage-audit document under `docs/`;
- one focused verification test for that document, if required;
- a project-status update after the audit is accepted.

## Prohibited changes

- Do not modify or run the workflow.
- Do not disable, archive, rename, relocate, or delete it.
- Do not modify production code, formulas, thresholds, persistence, or domain scope.
- Do not execute external research.
- Do not expose any secret value.
- Do not select a second historical workflow.

## External facts

Unless directly verified, branch protection, external consumers, operator dependence, historical artifact links, repository-secret ownership, hosted cache continuity, and Brave quota/billing remain `MANUAL_VERIFICATION_REQUIRED`.

## Success criteria

The task succeeds only when the historical contract is documented accurately, current coverage is mapped honestly, the candidate receives one readiness classification, exact preservation evidence and rollback are defined, unresolved external facts remain manual-verification items, no workflow or production code changes occur, and all repository checks pass.

## Next decision

Only after the Wave 4J coverage audit is accepted may a separate task propose a final preservation run. Disablement or archival remains unapproved.
