# Wave 4I — External Evidence Execution Coverage Audit

**Candidate:** `.github/workflows/v2.7.2.4.3-external-evidence-execution-audit.yml`  
**Decision:** `NOT_READY`  
**Scope:** documentation-only coverage audit and preservation planning

## Executive conclusion

Current repository code preserves the historical external-evidence execution implementation and tracing model, but tracked tests and retained workflows do not reproduce the complete GitHub Actions contract of V2.7.2.4.3.

The candidate is therefore:

```text
NOT_READY
```

No final preservation run, disablement, archival, rename, relocation, or deletion is approved.

## Historical workflow contract

The workflow is manual-only and exposes:

```text
opportunity_limit = 20
research_threshold = 25
selection_limit = 3
```

It requires `BRAVE_API_KEY`, fails explicitly when the secret is absent, prints only a configured/missing status, generates a fresh opportunity dataset, executes the external-evidence audit CLI, prints the report when available, and uploads a 14-day artifact named:

```text
v2.7.2.4.3-external-evidence-execution-audit
```

The artifact boundary includes:

- `data/validation/`
- `data/todays_opportunities.json`
- `data/investment_files/`
- `data/evidence/`
- `data/brave_cache/`
- `data/brave_usage.jsonl`

The workflow also configures:

```text
BRAVE_MAX_REQUESTS_PER_RUN = 6
BRAVE_CACHE_TTL_HOURS = 0
EXTERNAL_RESEARCH_MAX_OPPORTUNITIES = 0
```

and uses `if-no-files-found: warn`.

## Current implementation behavior

`scripts/run_external_execution_audit.py`:

1. parses dataset, output, investment-file directory, threshold, and selection-limit arguments;
2. reads JSON from the requested dataset path;
3. synchronizes investment files;
4. selects preliminary candidates through `PreliminaryResearchCandidateScorer`;
5. builds the external-evidence loop;
6. wraps its search provider with `TracingSearchProvider`;
7. runs selected candidates through the external loop;
8. persists modified investment files;
9. records search counts, cache counts, returned results, explicit-price results, evidence, comparables, buyers, events, errors, and diagnoses;
10. writes and prints a deterministic JSON report.

`external_execution_audit.py` provides transparent Brave search tracing and diagnostic summaries. It records request and cache counters before and after each search, result counts, HTTPS rows, explicit NOK prices, titles, errors, and post-adapter price enrichment.

## Coverage matrix

| Boundary | Classification | Evidence and gap |
|---|---|---|
| Manual-only trigger | `COVERED` | Historical YAML contains only `workflow_dispatch`. |
| `opportunity_limit` input and live-pipeline forwarding | `NOT_COVERED` | No focused test reproduces GitHub input interpolation into `run_daily_pipeline.py`. |
| Configurable research threshold | `PARTIALLY_COVERED` | Candidate scorer accepts a threshold, but the complete workflow/CLI path is not tested. |
| Configurable selection limit | `PARTIALLY_COVERED` | Candidate selection supports limiting, but GitHub input-to-CLI behavior is not reproduced. |
| Candidate ranking, tie ordering, and truncation | `PARTIALLY_COVERED` | Implemented by the scorer; no focused execution-audit contract test was found. |
| Fresh live dataset generation | `NOT_COVERED` | Current unit-level coverage does not execute the real daily pipeline. |
| Required Brave secret | `PARTIALLY_COVERED` | Workflow explicitly fails when absent; no retained focused test reproduces this workflow step. |
| Secret non-disclosure | `PARTIALLY_COVERED` | YAML prints only configured/missing status, but no workflow-level log assertion is preserved. |
| Brave request maximum `6` | `NOT_COVERED` | No focused test proves the effective provider limit through this workflow. |
| Cache TTL `0` | `NOT_COVERED` | No focused test proves cache bypass or resulting cache counters in this path. |
| Effective `EXTERNAL_RESEARCH_MAX_OPPORTUNITIES=0` | `MANUAL_VERIFICATION_REQUIRED` | The variable is set by YAML, but the effective downstream behavior must be observed in a controlled run. |
| Actual Brave execution tracing | `PARTIALLY_COVERED` | Tracing implementation exists; no focused test suite for the full audit path was found. |
| Provider exception trace | `PARTIALLY_COVERED` | Wrapper records and re-raises provider exceptions, but workflow behavior is not reproduced. |
| Evidence creation/update accounting | `PARTIALLY_COVERED` | Report fields exist and are populated from loop results; live persistence is not reproduced. |
| Comparable and buyer accounting | `PARTIALLY_COVERED` | Report records both counts; adapter and live-search boundaries are not covered end to end here. |
| Per-candidate failure isolation | `NOT_COVERED` | This CLI loop does not locally catch candidate exceptions; failure semantics need explicit tests and controlled evidence. |
| Investment-file synchronization | `NOT_COVERED` | The CLI invokes synchronization, but no focused file-boundary test was found. |
| Investment-file persistence | `NOT_COVERED` | Live repository load/save behavior is not reproduced by a focused audit test. |
| Dataset missing or unreadable | `NOT_COVERED` | Standard file exception behavior exists but is not asserted. |
| Invalid JSON | `NOT_COVERED` | Standard JSON failure behavior exists but is not asserted. |
| CLI defaults and overrides | `NOT_COVERED` | No subprocess or parser-boundary test was found. |
| Output directory creation | `PARTIALLY_COVERED` | Implemented with `mkdir(parents=True, exist_ok=True)` but not tested through the CLI. |
| Deterministic JSON serialization | `PARTIALLY_COVERED` | Uses sorted, indented JSON; no output-contract test was found. |
| Report print behavior | `NOT_COVERED` | CLI prints JSON, but stdout behavior is not tested. |
| Workflow absent-report message | `NOT_COVERED` | Defined only in YAML. |
| Artifact name | `COVERED` | Exact name is preserved in YAML. |
| Complete artifact inventory | `NOT_COVERED` | No current test or workflow reproduces and validates the whole archive. |
| 14-day retention | `COVERED` | Explicit in YAML, but not independently observed. |
| `if-no-files-found: warn` | `COVERED` | Explicit in YAML, but runtime behavior is not preserved as evidence. |
| Branch protection, external consumers, operator dependence, hosted cache, Brave quota/billing | `MANUAL_VERIFICATION_REQUIRED` | These facts are outside tracked repository evidence. |

## Material schema observation

The historical workflow and output filename identify version `2.7.2.4.3`, while `ExternalExecutionAuditReport.schema_version` is currently `2.7.2.4.10`.

This audit does not classify that difference as a defect because no compatibility contract or consumer expectation has been demonstrated. It must be included in any later preservation comparison.

## Why the candidate is not ready

A final preservation run is not justified until current coverage proves or intentionally preserves:

1. all three GitHub inputs and their CLI forwarding;
2. fresh daily-dataset generation;
3. explicit missing-secret failure and log non-disclosure;
4. request-limit and zero-TTL behavior;
5. the effective meaning of `EXTERNAL_RESEARCH_MAX_OPPORTUNITIES=0`;
6. candidate execution, failure semantics, and persistence;
7. CLI file, JSON, output, and stdout behavior;
8. the exact report schema/version boundary;
9. complete artifact inventory, cache/usage evidence, and missing-file behavior.

## Required coverage before reconsideration

A later task should add focused, deterministic tests for:

- scorer ordering, threshold inclusivity, ties, and selection truncation;
- tracing success, cache counters, enriched price recounting, and provider errors;
- execution-audit report aggregation and diagnosis;
- one candidate failure and queue-level failure semantics;
- CLI defaults, overrides, malformed JSON, missing files, output creation, and stdout;
- investment-file synchronization and persistence using temporary directories;
- secret status without exposing the secret;
- request and cache environment configuration;
- artifact manifest validation.

These tests must not perform uncontrolled external research.

## Future preservation evidence

If later coverage closes the gaps, a separately approved preservation run must capture:

- exact commit SHA and workflow path;
- workflow run ID, run number, branch, conclusion, timestamps, and duration;
- sanitized input values;
- proof that no secret value appeared in logs or artifacts;
- step outcomes, especially secret verification, dataset generation, and audit execution;
- report file and schema version;
- selected and audited candidate counts;
- Brave request/cache counters and usage log;
- evidence, comparable, buyer, and error summaries;
- complete artifact ZIP, artifact ID, size, retention, file inventory, and SHA-256 digest;
- explicit observation of the effective zero external-research limit;
- any empty or missing expected paths and the resulting warning behavior.

## Rollback

No operational change occurs in Wave 4I. Future disablement must remain reversible by reverting the exact change commit or restoring the workflow from its preserved pre-change SHA at the same path.

Deletion remains unapproved.

## External facts

The following remain:

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
- Brave quota and billing state.

## Final decision

```text
NOT_READY
```

The workflow remains unchanged and is not approved for a final preservation run or any disablement action.