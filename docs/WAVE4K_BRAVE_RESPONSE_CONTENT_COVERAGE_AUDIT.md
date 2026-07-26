# Wave 4K — Brave Response Content Coverage Audit

**Candidate:** `.github/workflows/v2.7.2.4.5-brave-response-content-audit.yml`  
**Decision:** `NOT_READY`  
**Scope:** documentation-only coverage audit; no workflow run or modification

## Executive conclusion

The repository retains the core implementation for inspecting Brave raw JSON response structure, sanitizing selected sensitive keys, writing numbered raw-response files, calculating SHA-256 digests, comparing `web.results` with the production parser, summarizing diagnoses, synchronizing investment files, and serializing the final audit report.

However, current tracked coverage does not reproduce the complete historical GitHub Actions contract. In particular, no focused tracked test was found for the end-to-end V2.7.2.4.5 audit path, and the live dataset, secret, environment-limit, CLI/file, raw-response safety, and artifact boundaries are not fully verified. The workflow is therefore not ready for a final preservation run.

## Historical workflow contract

The manual-only workflow requires these inputs:

| Input | Default |
|---|---:|
| `opportunity_limit` | `20` |
| `research_threshold` | `25` |
| `selection_limit` | `3` |

It requires `BRAVE_API_KEY`, configures `BRAVE_MAX_REQUESTS_PER_RUN=8`, `BRAVE_CACHE_TTL_HOURS=0`, and `EXTERNAL_RESEARCH_MAX_OPPORTUNITIES=0`, generates a fresh dataset, runs `scripts/run_brave_response_content_audit.py`, writes a structured report and raw-response files, prints the report when present, and uploads artifact `v2.7.2.4.5-brave-response-content-audit` with 14-day retention and `if-no-files-found: warn`.

## Retained implementation evidence

The current implementation provides:

- CLI defaults for dataset, report path, raw-response directory, investment-file directory, threshold, and selection limit.
- JSON dataset loading and investment-file synchronization.
- candidate evaluation through `PreliminaryResearchCandidateScorer`.
- selected-candidate execution through the existing research loop.
- report fields for selected and audited candidate counts, request records, parser totals, evidence, comparables, buyers, and loop errors.
- a live Brave provider wrapper that ignores cache use, increments request count, records HTTP metadata, decodes JSON, inspects known result paths, and calls the production parser.
- recursive redaction for configured sensitive key names.
- deterministic raw filenames in the form `response-001.json`.
- SHA-256 digest creation for each persisted raw response.
- diagnoses for present, empty, alternate, missing, or parser-rejected result paths.
- aggregate summary counts and final JSON output to disk and stdout.

## Coverage matrix

| Material behavior | Classification | Basis |
|---|---|---|
| Manual input names and defaults | `PARTIALLY_COVERED` | Present in workflow and corresponding CLI defaults, but not reproduced by a focused Actions/CLI integration test. |
| `opportunity_limit` fresh dataset generation | `NOT_COVERED` | Audit script consumes a dataset; it does not test the preceding live daily-pipeline step. |
| threshold and selection limit | `PARTIALLY_COVERED` | Passed into the retained scorer, but the complete workflow path is not tested here. |
| candidate eligibility, ranking, ordering, truncation | `PARTIALLY_COVERED` | Delegated to existing scorer behavior; no focused V2.7.2.4.5 end-to-end test was found. |
| missing-score behavior | `PARTIALLY_COVERED` | Delegated to scorer implementation rather than verified through this audit path. |
| Brave secret required when absent | `NOT_COVERED` | Implemented in GitHub Actions shell, not in the audit script or a focused test. |
| secret non-disclosure in Actions logs | `MANUAL_VERIFICATION_REQUIRED` | Tracked code does not prove hosted-log behavior. |
| `BRAVE_MAX_REQUESTS_PER_RUN=8` | `NOT_COVERED` | Provider wrapper counts requests but does not itself enforce or verify the workflow environment maximum. |
| `BRAVE_CACHE_TTL_HOURS=0` | `PARTIALLY_COVERED` | Audit provider forces live requests by ignoring `use_cache`; the environment contract and underlying provider interaction are not tested. |
| `EXTERNAL_RESEARCH_MAX_OPPORTUNITIES=0` effective meaning | `MANUAL_VERIFICATION_REQUIRED` | The direct audit path calls the loop for selected candidates; zero-limit behavior in the constructed loop is not proven by focused coverage. |
| HTTP status/content type/size capture | `COVERED` in implementation | Recorded by the response-content provider. |
| JSON decode and invalid-JSON failure | `COVERED` in implementation | Invalid UTF-8/JSON becomes a defined runtime error and diagnostic state. |
| expected `web.results` path inspection | `COVERED` in implementation | Existence, type, and count are recorded. |
| alternate result-path discovery | `COVERED` in implementation | Known Brave paths are inspected and counted. |
| production parser comparison | `COVERED` in implementation | Raw payload is passed to `parse_brave_results`; parser count and diagnosis are recorded. |
| titles, URLs, snippets, and individual missing fields | `NOT_COVERED` | The content audit records structural counts, not a field-by-field acceptance matrix. |
| provider/transport error classification | `PARTIALLY_COVERED` | Errors are retained as generic `transport_error`; detailed classifications belong to the prior transport audit. |
| recursive sensitive-key redaction | `PARTIALLY_COVERED` | Redaction code exists for a fixed key set; no focused test was found for nested, case, alias, or unexpected sensitive fields. |
| raw-response filename generation | `COVERED` in implementation | Sequential deterministic names are generated. |
| raw-response truncation or maximum size | `NOT_COVERED` | Full sanitized JSON is written; no size cap or truncation boundary is present. |
| raw-response privacy/safety boundary | `MANUAL_VERIFICATION_REQUIRED` | Key-based redaction cannot establish that arbitrary response content is safe to retain. |
| raw-response persistence failure | `NOT_COVERED` | No focused test was found for permissions, disk, partial writes, or cleanup. |
| raw-response SHA-256 digest | `COVERED` in implementation | Digest is computed after writing. |
| investment-file synchronization and persistence | `PARTIALLY_COVERED` | Calls are present; complete file outcomes and failure isolation are not reproduced. |
| per-candidate failure isolation | `NOT_COVERED` | An exception during one selected candidate can terminate the script; no focused isolation test was found. |
| CLI parsing and defaults | `PARTIALLY_COVERED` | Defined through argparse, without a focused subprocess/CLI test. |
| missing dataset file | `NOT_COVERED` | Native file exception behavior is not documented by a focused test. |
| malformed dataset JSON | `NOT_COVERED` | Native decode failure is not covered by a focused test. |
| output directory creation and report serialization | `COVERED` in implementation | Parent directory is created and formatted JSON is written and printed. |
| report-absent print fallback | `NOT_COVERED` | This behavior exists only in workflow shell and is not reproduced by tests. |
| exact artifact name and inventory | `NOT_COVERED` | Declared in workflow, not verified through a retained artifact contract test. |
| raw responses included through `data/validation/` | `PARTIALLY_COVERED` | Path inclusion is declared, but archive contents are not verified. |
| retention of 14 days | `MANUAL_VERIFICATION_REQUIRED` | GitHub-hosted artifact behavior requires a controlled run. |
| `if-no-files-found: warn` | `NOT_COVERED` | No focused Actions behavior test. |
| branch protection, external consumers, operator dependence, secret ownership, Brave billing/quota, hosted retention/privacy requirements | `MANUAL_VERIFICATION_REQUIRED` | Not determinable from tracked repository files. |

## Important safety finding

The sanitizer redacts values only when dictionary keys match the fixed sensitive-key set. It does not remove arbitrary personal, commercial, or query-derived content from Brave results, and it writes the entire sanitized decoded response without a size limit. This is not asserted as a defect in the historical diagnostic, but it prevents declaring the raw-response evidence boundary fully preserved or safe without controlled verification and an explicit retention/privacy decision.

## Readiness decision

```text
NOT_READY
```

The retained code is useful diagnostic evidence, but the complete workflow cannot yet be proposed for a final preservation run because material GitHub Actions and live-execution boundaries remain unverified.

## Evidence required before reconsideration

A later, separately approved task would need:

1. focused deterministic tests for response-path inspection, parser comparison, nested sensitive-key redaction, raw naming, digest, and summary behavior;
2. focused CLI tests for defaults, custom inputs, missing files, malformed JSON, output creation, and non-zero failures;
3. explicit tests for per-candidate error isolation or a documented fail-fast contract;
4. a controlled main-branch preservation run using non-sensitive bounded input;
5. proof that the missing-secret step fails and no secret value appears in logs or artifacts;
6. proof of the effective request limit `8`, cache-disabled behavior, and the zero external-research-limit meaning;
7. captured report and raw-response inventory with checksums, while confirming that no unsafe content is retained;
8. artifact metadata proving exact name, inventory, retention, and missing-file behavior;
9. a documented privacy/retention decision for raw external responses.

## Rollback

This audit changes documentation only. Rollback is removal or reversion of this document. The historical workflow, production code, formulas, thresholds, persistence behavior, domain scope, and external-research behavior remain unchanged.

## Final action boundary

No preservation run, disablement, archival, relocation, rename, or deletion is approved by this result. A separate accepted task is required before any such action.