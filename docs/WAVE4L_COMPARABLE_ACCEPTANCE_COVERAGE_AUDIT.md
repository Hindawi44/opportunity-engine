# Wave 4L — Comparable Acceptance Coverage Audit

**Candidate:** `.github/workflows/v2.7.2.4.7-comparable-acceptance-audit.yml`  
**Audit type:** Documentation-only coverage audit  
**Result:** `NOT_READY`

## Executive conclusion

The retained implementation preserves meaningful comparable-acceptance diagnostics, including candidate selection, row limiting, adapter acceptance, engine acceptance, rejection reasons, comparable counts, investment-file synchronization, report serialization, and deterministic V2.8.2B evidence persistence coverage.

Current tracked coverage does not reproduce the complete historical GitHub Actions contract. The workflow is therefore **not ready for a final preservation run** and is not approved for disablement, archival, relocation, rename, or deletion.

## Historical workflow contract

The historical workflow is manual-only and exposes four required inputs:

| Input | Default |
|---|---:|
| `opportunity_limit` | `20` |
| `research_threshold` | `25` |
| `selection_limit` | `3` |
| `row_limit` | `20` |

It requires `BRAVE_API_KEY`, generates a fresh dataset, runs `scripts/run_comparable_acceptance_audit.py`, writes a structured validation report, prints the report when present, and uploads an artifact containing validation, opportunity, investment, evidence, and Brave usage files with 14-day retention and `if-no-files-found: warn`.

Configured Brave environment boundaries are:

```text
BRAVE_MAX_REQUESTS_PER_RUN=8
BRAVE_CACHE_TTL_HOURS=0
EXTERNAL_RESEARCH_MAX_OPPORTUNITIES=0
```

## Coverage matrix

| Boundary | Classification | Evidence and gap |
|---|---|---|
| Four workflow inputs and defaults | `PARTIALLY_COVERED` | Workflow and CLI defaults are visible. No focused test reproduces GitHub Actions input plumbing or invalid-input behavior. |
| Fresh dataset generation with `opportunity_limit` | `NOT_COVERED` | The audit script consumes an existing dataset; it does not generate the daily dataset. |
| Threshold and selection limit | `PARTIALLY_COVERED` | The script delegates to `PreliminaryResearchCandidateScorer`; no focused Wave 4L test reproduces threshold boundaries, ties, missing scores, and truncation through the workflow. |
| Deterministic ranking and missing-score handling | `PARTIALLY_COVERED` | Delegated production behavior exists, but the complete historical workflow contract is not re-executed by focused tests. |
| `row_limit` enforcement | `COVERED` | `ComparableAcceptanceAuditedProvider` clamps the value to at least one and inspects `rows[:row_limit]`. |
| Non-list provider response | `COVERED` | A non-list response is treated as an empty row collection. |
| Comparable adapter acceptance | `PARTIALLY_COVERED` | The wrapper calls the configured production adapter and records accepted URLs, but no focused test covers malformed and duplicate rows across the historical path. |
| Comparable engine acceptance | `PARTIALLY_COVERED` | The wrapper calls the retained comparables engine and records accepted and rejected rows. Full equivalence with the historical live path is not demonstrated. |
| Missing title | `COVERED` | Recorded as `missing_title`. |
| Invalid or non-HTTPS URL | `COVERED` | Recorded as `invalid_https_url`. |
| Missing or invalid price | `COVERED` | Recorded as `missing_price` or `invalid_price`. |
| Non-NOK currency | `COVERED` | Recorded as `currency_not_nok`. |
| Low similarity | `COVERED` | Similarity below `0.65` is recorded as `low_similarity`. |
| Duplicate comparable behavior | `NOT_COVERED` | URL sets influence audit classification, but duplicate handling and evidence-upsert behavior are not focused-tested for this workflow. |
| Evidence creation and update | `PARTIALLY_COVERED` | Loop results record counts and V2.8.2B deterministically persists evidence. The live audit path and update/idempotency boundary are not equivalently covered. |
| Investment-file synchronization | `PARTIALLY_COVERED` | The CLI synchronizes and saves files, but filesystem failure, malformed payload, and partial-write behavior are not focused-tested. |
| V2.8.2/V2.8.2B equivalence | `PARTIALLY_COVERED` | V2.8.2B proves deterministic acceptance, persistence, reload, and financial collection for three valid candidates. It does not reproduce live Brave selection, row limiting, rejected rows, usage logging, or the historical artifact. |
| Missing Brave secret failure | `NOT_COVERED` | The workflow shell step requires the secret, but no focused tracked test reproduces the hosted failure path. |
| Secret non-disclosure | `PARTIALLY_COVERED` | The workflow prints configured/missing status only. Hosted logs and dependency error output remain unverified. |
| Request maximum `8` | `NOT_COVERED` | The environment value is configured, but focused tests do not prove enforcement across the complete Wave 4L path. |
| Cache TTL `0` | `NOT_COVERED` | The workflow configures zero TTL; focused tests do not prove effective cache bypass or hosted cache behavior. |
| Effective `EXTERNAL_RESEARCH_MAX_OPPORTUNITIES=0` | `MANUAL_VERIFICATION_REQUIRED` | The effective meaning depends on `build_loop` and runtime configuration; no final live-equivalence evidence is recorded. |
| Brave usage log | `NOT_COVERED` | The artifact expects `data/brave_usage.jsonl`, but generation, request accounting, malformed lines, and absence behavior are not reproduced. |
| Provider failures and per-candidate isolation | `PARTIALLY_COVERED` | Loop errors are recorded, but the CLI has no explicit candidate-level exception boundary around load/run/save. |
| Dataset file missing | `NOT_COVERED` | Standard file exceptions propagate; no focused contract test exists. |
| Malformed dataset JSON | `NOT_COVERED` | `json.loads` exceptions propagate; no focused contract test exists. |
| CLI type validation | `PARTIALLY_COVERED` | `argparse` validates numeric types, but boundary values and workflow-string input behavior are not focused-tested. |
| Output directory and JSON serialization | `COVERED` | Parent directory is created and sorted UTF-8 JSON is written and printed. |
| Report-absent print behavior | `NOT_COVERED` | Implemented in workflow shell, not in the CLI or focused tests. |
| Artifact name and inventory | `NOT_COVERED` | YAML defines the contract; no current test creates and inventories the exact archive. |
| Artifact retention 14 days | `NOT_COVERED` | GitHub Actions-only setting, not reproduced by tests. |
| `if-no-files-found: warn` | `NOT_COVERED` | GitHub Actions-only behavior, not reproduced by tests. |
| Branch protection, external consumers, operator dependence, historical links | `MANUAL_VERIFICATION_REQUIRED` | Not derivable from tracked repository files. |
| Secret ownership, Brave quota/billing, hosted cache continuity, privacy/retention policy | `MANUAL_VERIFICATION_REQUIRED` | External operational facts remain unverified. |

## Important implementation observations

1. `row_limit` is clamped to a minimum of one rather than rejecting zero or negative values.
2. Audit acceptance is associated by URL sets. This is useful diagnostically but does not prove duplicate-row identity behavior.
3. The provider returns the original response after auditing; production search semantics are preserved.
4. The CLI processes selected candidates sequentially without an explicit candidate-level exception guard around repository load, loop execution, and save.
5. V2.8.2B is deterministic and proves a narrower evidence boundary; it is not equivalent to the historical live workflow.

These observations are recorded as preservation boundaries, not asserted as production defects.

## Readiness decision

```text
NOT_READY
```

The workflow must remain unchanged. No final preservation run, disablement, archival, relocation, rename, or deletion is approved.

## Exact future preservation evidence required

A future separately approved task would need all of the following on one accepted `main` commit:

1. focused automated tests for candidate threshold, ties, ordering, missing scores, selection limiting, and row-limit boundaries;
2. malformed, missing-field, duplicate, rejected, and accepted comparable-row tests;
3. evidence create/update/idempotency and investment-file synchronization tests;
4. missing-secret failure and hosted-log non-disclosure evidence;
5. verified request-limit `8`, cache TTL `0`, zero external-research-limit meaning, and Brave usage accounting;
6. CLI tests for missing files, malformed JSON, filesystem failures, output, and exit behavior;
7. equivalence comparison against retained V2.8.2 and V2.8.2B boundaries;
8. one controlled manual preservation run with run ID, commit SHA, inputs, status, job logs, artifact ID, archive inventory, retention evidence, and SHA-256 digest;
9. confirmation that no secret or unsafe external response appears in logs or artifacts;
10. explicit acceptance in a separate PR before any disablement action.

## Rollback boundary

No rollback is required for this audit because no workflow or production code changed. Any future workflow change must preserve the pre-change commit SHA and be reversible by restoring the exact file at the same path.

## External facts

The following remain `MANUAL_VERIFICATION_REQUIRED`:

- branch-protection dependence;
- external consumers;
- operator dependence;
- historical artifact links;
- repository-secret availability and ownership;
- Brave account quota and billing state;
- hosted cache continuity;
- privacy or retention requirements for external evidence and usage logs.
