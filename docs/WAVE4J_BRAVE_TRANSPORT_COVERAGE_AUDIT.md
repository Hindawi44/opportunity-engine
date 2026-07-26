# Wave 4J — Brave Transport & Response Coverage Audit

**Candidate:** `.github/workflows/v2.7.2.4.4-brave-transport-response-audit.yml`  
**Decision:** `NOT_READY`

## Scope

Documentation-only coverage audit. No workflow was modified, run, disabled, archived, renamed, relocated, or deleted. No production code, formula, threshold, persistence rule, secret value, or domain scope was changed.

## Historical contract

The historical workflow is manual-only and exposes:

- `opportunity_limit=20`
- `research_threshold=25`
- `selection_limit=3`

It requires `BRAVE_API_KEY`, fails explicitly when the secret is absent, prints only configuration status, configures `BRAVE_MAX_REQUESTS_PER_RUN=4`, `BRAVE_CACHE_TTL_HOURS=0`, and `EXTERNAL_RESEARCH_MAX_OPPORTUNITIES=0`, generates a fresh dataset, runs `scripts/run_brave_transport_audit.py`, writes and prints the validation report, and uploads artifact `v2.7.2.4.4-brave-transport-response-audit` for 14 days with `if-no-files-found: warn`.

Artifact boundary:

- `data/validation/`
- `data/todays_opportunities.json`
- `data/investment_files/`
- `data/evidence/`
- `data/brave_usage.jsonl`

## Retained implementation behavior

`run_brave_transport_audit.py`:

- parses the dataset, output, investment-file directory, threshold, and selection-limit arguments;
- synchronizes investment files;
- selects preliminary candidates;
- wraps the existing Brave provider with `AuditedBraveSearchProvider`;
- executes only selected candidates;
- records request, response, error, result, evidence, comparable, and buyer fields;
- writes deterministic JSON with schema `2.7.2.4.4` and prints it.

`AuditedBraveSearchProvider`:

- forces live transport by ignoring `use_cache`;
- records endpoint, header names, timestamps, HTTP status, duration, size, content type, body preview, stage, and errors;
- classifies HTTP 401, 403, and 429, timeout, DNS, SSL, empty-body, and JSON parsing failures;
- counts requests and transport outcomes;
- does not intentionally serialize header values or the API key.

## Coverage matrix

| Material behavior | Classification | Basis |
|---|---|---|
| Manual input defaults | `PARTIALLY_COVERED` | Workflow and CLI defaults are tracked; no focused GitHub-input execution test found. |
| Threshold, ordering, selection, truncation | `PARTIALLY_COVERED` | Reuses tested candidate scorer, but not the complete historical execution path. |
| Fresh live dataset generation | `NOT_COVERED` | No retained deterministic test reproduces `run_daily_pipeline.py` plus this audit. |
| Secret presence and missing-secret failure | `NOT_COVERED` | Workflow shell gate exists; no focused retained test reproduces it. |
| Secret non-disclosure | `PARTIALLY_COVERED` | Code records header names, not values; complete Actions-log verification is absent. |
| Request limit `4` | `MANUAL_VERIFICATION_REQUIRED` | Environment contract is tracked; effective provider enforcement requires controlled execution. |
| Cache TTL `0` | `PARTIALLY_COVERED` | Audit wrapper forces live transport, but complete hosted behavior and usage evidence are not reproduced. |
| `EXTERNAL_RESEARCH_MAX_OPPORTUNITIES=0` | `MANUAL_VERIFICATION_REQUIRED` | Effective interaction with this direct execution path is not established by tracked tests. |
| HTTP request and response accounting | `PARTIALLY_COVERED` | Implementation exists; no focused tests for the complete audit module were found. |
| HTTP/provider error classification | `PARTIALLY_COVERED` | Explicit code paths exist, but focused regression coverage was not found. |
| Response parsing and result counts | `PARTIALLY_COVERED` | Implemented through `parse_brave_results`; historical live response behavior is not reproduced. |
| Investment-file synchronization and persistence | `PARTIALLY_COVERED` | Executed by CLI, but complete file-boundary test is absent. |
| CLI parsing, JSON reading/writing, printing | `PARTIALLY_COVERED` | Implemented directly; missing-file, invalid-JSON, and write-failure tests were not found. |
| Usage log generation | `NOT_COVERED` | Artifact expects `data/brave_usage.jsonl`; complete generation and contents are not reproduced. |
| Exact artifact inventory and name | `NOT_COVERED` | No retained test reconstructs the archive contract. |
| 14-day retention | `MANUAL_VERIFICATION_REQUIRED` | GitHub Actions metadata only. |
| `if-no-files-found: warn` | `MANUAL_VERIFICATION_REQUIRED` | Requires Actions-level verification. |
| Branch protection, external consumers, operator dependence, historical links, secret ownership, quota/billing | `MANUAL_VERIFICATION_REQUIRED` | Not established by tracked repository files. |

## Readiness decision

`NOT_READY`

The retained code preserves substantial diagnostic behavior, but current tracked coverage does not reproduce the complete historical GitHub Actions contract. A final preservation run is not approved, and disablement, archival, relocation, rename, or deletion remain unapproved.

## Requirements before reconsideration

Before `READY_FOR_FINAL_PRESERVATION_RUN` can be considered, evidence must cover:

1. all three workflow inputs and defaults;
2. fresh dataset generation with bounded opportunity count;
3. explicit missing-secret failure and log non-disclosure;
4. request-limit and cache behavior;
5. effective zero external-research-limit behavior;
6. successful and failed HTTP/parse paths;
7. CLI missing-file, invalid-JSON, output, and persistence behavior;
8. exact report schema and contents;
9. complete artifact inventory, usage log, name, retention, and missing-file behavior.

## Future preservation evidence

A separately approved controlled run must preserve:

- workflow run ID, run number, branch, commit SHA, inputs, conclusion, and duration;
- job and step conclusions;
- secret-presence success without secret disclosure;
- transport report and daily-pipeline report;
- request/cache/usage evidence;
- complete artifact inventory, artifact ID, size, retention, and SHA-256 digest;
- confirmation of no automatic purchase, bid, contact, or recommendation behavior.

## Rollback

No repository behavior changed in this audit. A future workflow change must remain reversible by reverting its exact commit or restoring the previous workflow file and trigger from the recorded commit SHA.
