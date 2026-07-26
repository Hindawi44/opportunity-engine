# Wave 4F — V2.7.2.2 Internal Score Coverage Audit

**Candidate:** `.github/workflows/v2.7.2.2-internal-score-audit.yml`  
**Result:** `NOT_READY`  
**Scope:** documentation-only coverage audit and preservation planning

## Executive conclusion

Current tests reproduce the core in-memory behavior of `InternalScoreAuditor`, including threshold comparison, score-gap calculation, component totals, missing-score handling, evidence-gate diagnoses, and component/final-score mismatch detection.

They do not reproduce the complete historical workflow contract. The historical workflow still has unique manual inputs, fresh live dataset generation, Brave-secret configuration, CLI/file behavior, versioned validation outputs, and a multi-file GitHub Actions artifact bundle. Therefore the candidate is not ready for a final preservation run or reversible disablement.

## Historical workflow contract

The workflow is manual-only through `workflow_dispatch` and accepts:

- `opportunity_limit`, default `20`;
- `required_score`, default `60`.

It configures:

- `BRAVE_API_KEY` from repository secrets;
- `BRAVE_MAX_REQUESTS_PER_RUN=4`;
- `BRAVE_CACHE_TTL_HOURS=24`;
- `EXTERNAL_RESEARCH_MAX_OPPORTUNITIES=0`.

It then:

1. generates a fresh dataset through `scripts/run_daily_pipeline.py --limit ...`;
2. writes the pipeline summary to `data/validation/v2.7.2.2-daily-pipeline-run.json`;
3. runs `scripts/run_internal_score_audit.py` against `data/todays_opportunities.json`;
4. writes `data/validation/v2.7.2.2-internal-score-audit.json`;
5. prints the report when present;
6. uploads artifact `v2.7.2.2-internal-score-audit` with validation files, today’s opportunities, scored opportunities, the economic-evaluation queue, and investment files.

## Auditor schema and behavior

The report records:

- generated timestamp and dataset path;
- configured `required_score`;
- per-opportunity ID, title, total score, score gap, components, component total, score reasons, upstream decision, missing-evidence count, diagnoses, and eligibility;
- report-level eligible, below-threshold, missing-score, and component-mismatch counts;
- schema version `2.7.2.2`.

Score selection order is `opportunity_score`, then `internal_score`, then `score`. Eligibility is true only when a numeric score exists and is greater than or equal to `required_score`.

## Coverage matrix

| Boundary | Classification | Evidence |
|---|---|---|
| Configurable `required_score` in the auditor | `COVERED` | Unit test uses `required_score=60` and verifies score gap and ineligibility. |
| Score-field fallback assumptions | `PARTIALLY_COVERED` | Implementation supports three fields; tests exercise `opportunity_score` and `score`, but not every fallback and precedence combination. |
| Component-total calculation | `COVERED` | Unit tests verify matching and mismatching component totals. |
| External-research eligibility threshold | `COVERED` in memory | Unit test verifies below-threshold behavior; workflow input wiring is not tested. |
| Missing score preserved as unknown | `COVERED` | Unit test verifies `None`, no fabricated gap, and missing-score diagnosis. |
| Missing evidence and upstream gate diagnoses | `COVERED` | Unit test verifies evidence-related diagnoses and blocked upstream decision. |
| Opportunity-limit input and daily-pipeline forwarding | `NOT_COVERED` | No focused test reproduces workflow input forwarding to the live pipeline. |
| Fresh live dataset generation | `NOT_COVERED` | Unit tests use deterministic in-memory payloads. |
| Brave secret presence, availability, and non-disclosure | `NOT_COVERED` / `MANUAL_VERIFICATION_REQUIRED` | Repository tests do not reproduce this workflow’s secret-backed environment or repository-secret ownership. |
| CLI defaults and argument parsing | `NOT_COVERED` | No focused CLI test for dataset, output, or required-score arguments. |
| File reading and JSON failure behavior | `NOT_COVERED` | Tests call `audit_payload`; missing files and malformed JSON are not exercised. |
| Report file writing and serialized schema | `NOT_COVERED` | `write_report` is not covered by the focused tests. |
| Versioned daily-pipeline summary file | `NOT_COVERED` | Unique workflow output. |
| Versioned internal-score report file | `NOT_COVERED` as an execution boundary | In-memory report fields are covered, but file creation is not. |
| `scored_opportunities.json` and `economic_evaluation_queue.json` inclusion | `NOT_COVERED` | Unique artifact inventory behavior. |
| Investment-file inclusion | `NOT_COVERED` | Unique artifact inventory behavior. |
| GitHub Actions artifact upload and `if-no-files-found: warn` | `NOT_COVERED` | No current test reproduces Actions upload semantics. |
| Branch protection, external consumers, operator dependence, old artifact links | `MANUAL_VERIFICATION_REQUIRED` | Not established by tracked repository files. |

## Why the result is NOT_READY

Equivalent coverage has not been demonstrated for the historical workflow as a whole. The focused tests validate the auditor’s core calculations, but the following remain unique and material:

- both manual workflow inputs and their wiring;
- live daily-pipeline execution;
- Brave-backed environment configuration;
- CLI and file boundaries;
- versioned validation files;
- complete multi-file artifact inventory;
- GitHub Actions failure and upload behavior.

A final preservation run would not resolve the absence of equivalent current coverage by itself. Disablement remains unapproved.

## Requirements before reconsideration

Reconsider `READY_FOR_FINAL_PRESERVATION_RUN` only after focused tests or retained workflows demonstrate:

1. CLI parsing and configurable threshold behavior;
2. file read/write behavior, including missing file and invalid JSON failures;
3. opportunity-limit forwarding or an explicit decision that live-dataset generation remains uniquely historical;
4. secret non-disclosure and safe missing-secret behavior where applicable;
5. exact validation-output and artifact inventory expectations;
6. behavior when optional artifact files are absent.

## Future preservation evidence bundle

If the candidate later becomes ready, preserve at minimum:

- workflow run ID, run number, URL, branch, commit SHA, trigger actor, timestamps, duration, and conclusion;
- input values for `opportunity_limit` and `required_score`;
- job ID, step conclusions, and relevant non-secret logs;
- artifact ID, name, size, expiry, digest, and complete archive inventory;
- copies or hashes of both versioned validation JSON files;
- summary counts from the internal-score report;
- explicit confirmation that no secret value appears in logs or artifacts.

## Rollback

No workflow change occurs in Wave 4F. Any future reversible-disablement PR must retain the file at the same path, remain recoverable by reverting one commit, and document how to restore its previous trigger and behavior.

## External facts

The following remain `MANUAL_VERIFICATION_REQUIRED`:

- branch-protection dependence;
- external consumers;
- operator dependence;
- historical artifact links;
- repository-secret availability and ownership.

## Safety statement

This audit changes no workflow, production code, score formula, financial formula, threshold, persistence behavior, domain scope, recommendation, ranking, alert, purchase, bid, or contact behavior.
