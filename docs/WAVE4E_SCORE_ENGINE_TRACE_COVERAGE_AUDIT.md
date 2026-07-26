# Wave 4E — V2.7.2.3 Score Engine Trace Coverage Audit

**Candidate:** `.github/workflows/v2.7.2.3-score-engine-trace-audit.yml`  
**Audit result:** `NOT_READY`  
**Scope:** documentation-only coverage audit and preservation planning

## Executive conclusion

The retained unit tests cover the core parsing and score-trace calculations implemented by `ScoreEngineTraceAuditor`, including serialized score breakdowns, missing-breakdown diagnosis, explicit score components, penalty subtraction, and decision-cap expectations.

However, no retained current workflow reproduces the complete historical V2.7.2.3 execution contract: manual limit input, generation of a fresh daily dataset, trace execution against that generated file, complete validation/investment artifact bundle, and the workflow-level failure and artifact behavior.

Therefore the candidate is **not ready** for a final preservation run or reversible disablement proposal.

## Historical workflow contract

The historical workflow is manual-only through `workflow_dispatch` and accepts one required input:

- `opportunity_limit`, default `20`.

It then:

1. checks out the repository;
2. installs Python 3.11 dependencies;
3. verifies the package import;
4. creates `data/validation` and `data/investment_files`;
5. runs `scripts/run_daily_pipeline.py --limit <input>` and redirects stdout to `data/validation/v2.7.2.3-daily-pipeline-run.json`;
6. runs `scripts/run_score_engine_trace_audit.py data/todays_opportunities.json`;
7. writes `data/validation/v2.7.2.3-score-engine-trace.json`;
8. prints the trace when present and prints a warning when absent;
9. uploads artifact `v2.7.2.3-score-engine-trace-audit` containing:
   - `data/validation/`
   - `data/todays_opportunities.json`
   - `data/investment_files/`
10. retains the artifact for 14 days and uses `if-no-files-found: warn`.

The workflow sets `EXTERNAL_RESEARCH_MAX_OPPORTUNITIES=0`; it does not require Brave or another external-provider secret.

## Trace schema and behavior

The report schema version is `2.7.2.3` and includes:

- `dataset_path`
- `record_count`
- `scoring_function_called_count`
- `breakdown_serialized_count`
- `missing_breakdown_count`
- `records`

Each record includes:

- `opportunity_id`
- `title`
- `total_score`
- `decision`
- `score_breakdown_present`
- `parsed_components`
- `raw_score_breakdown`
- `component_sum_before_penalty`
- `calculated_raw_score`
- `cap_expected`
- `cap_applied`
- `trace_stage`
- `diagnosis`

The auditor accepts rows from list payloads or from `rows`, `opportunities`, `items`, `results`, or `data`. It reads score values from `score`, then `internal_score`, then `opportunity_score`. It parses serialized components or explicit `score_components`, subtracts `risk_penalty`, and diagnoses whether the breakdown reached the dataset boundary.

Decision-cap expectations are diagnostic only:

- `reject` -> expected cap `39.0`
- `monitor` -> expected cap `59.0`

The module explicitly does not alter scores, thresholds, recommendations, or external-research eligibility.

## Coverage matrix

| Historical behavior | Current evidence | Classification | Notes |
|---|---|---|---|
| Parse dashboard `score_breakdown` strings | `tests/test_score_engine_trace.py::test_trace_parses_dashboard_score_breakdown` | `COVERED` | Verifies components, sums, raw score, and serialization stage. |
| Detect total score with missing breakdown | `test_trace_identifies_projection_loss_when_only_total_survives` | `COVERED` | Verifies missing breakdown count and dashboard-projection diagnosis. |
| Support explicit `score_components` | `test_trace_supports_explicit_score_components` | `COVERED` | Verifies component sum, raw score, cap expectation, and cap state. |
| Score value fallback across `score`, `internal_score`, `opportunity_score` | Implementation present; focused test coverage is incomplete | `PARTIALLY_COVERED` | Tests exercise `score` and `opportunity_score`, not all fallback paths. |
| Input container aliases (`rows`, `opportunities`, `items`, `results`, `data`, list) | Implementation present; tests cover only `rows` and `opportunities` | `PARTIALLY_COVERED` | Remaining aliases are not directly verified by focused tests. |
| Penalty parsing for evidence-gap, warning, and risk penalties | One test supplies all three; arithmetic uses only `risk_penalty` | `PARTIALLY_COVERED` | Parsing is exercised, but explicit assertions do not cover every penalty field. |
| Decision-cap logic for `reject` and `monitor` | Tests cover both decisions | `COVERED` | No production score or threshold is changed. |
| Missing score and inability to confirm invocation | Implementation present; no focused test identified | `NOT_COVERED` | No direct assertion for `score_value_missing` / `scoring_invocation`. |
| File input and JSON decoding through `audit_file` | No focused file-I/O test identified | `NOT_COVERED` | Malformed JSON and missing-file behavior are also untested. |
| Report write path and directory creation | No focused `write_report` test identified | `NOT_COVERED` | Unit tests operate in memory. |
| CLI defaults and argument behavior | No focused CLI/script test identified | `NOT_COVERED` | Default dataset/output paths and exit behavior are not verified. |
| Manual `opportunity_limit` input | No current equivalent workflow/test identified | `NOT_COVERED` | This is a workflow-level contract. |
| Fresh dataset generation via `run_daily_pipeline.py` | Not reproduced by trace unit tests | `NOT_COVERED` | Current tests use deterministic in-memory fixtures. |
| Daily-pipeline stdout preservation | No current equivalent identified | `NOT_COVERED` | Historical validation file is unique. |
| Complete trace artifact name and inventory | No current equivalent identified | `NOT_COVERED` | Unit tests do not upload artifacts. |
| Upload on failure through `if: always()` | Workflow YAML only; no current equivalent verification | `MANUAL_VERIFICATION_REQUIRED` | Requires an actual workflow run or dedicated workflow test. |
| `if-no-files-found: warn` behavior | Workflow YAML only | `MANUAL_VERIFICATION_REQUIRED` | Requires GitHub Actions behavior verification. |
| Secret non-disclosure | Workflow does not inject secrets | `COVERED` | Environment contains only `PYTHONPATH` and a non-secret limit control. |
| External consumers, branch protection, operator dependence, historical links | Not visible in tracked repository files | `MANUAL_VERIFICATION_REQUIRED` | Must remain unresolved unless verified through repository settings and operator records. |

## Unique historical behavior not reproduced today

The following material behavior remains unique to the historical workflow:

1. operator-supplied opportunity limit;
2. live generation of `data/todays_opportunities.json` before tracing;
3. preservation of daily-pipeline stdout in a versioned validation file;
4. trace against the generated dataset rather than deterministic fixtures;
5. upload of all validation files, the daily dataset, and investment files as one artifact;
6. GitHub Actions `always()` printing and upload behavior;
7. warning rather than failure when artifact paths are absent;
8. the exact artifact name and 14-day retention contract.

These differences prevent an honest equivalence claim.

## Readiness decision

```text
NOT_READY
```

The candidate must remain unchanged. A final preservation run is not approved by this audit because equivalent current coverage has not been demonstrated for the complete workflow and artifact contract.

## Requirements before reconsideration

At minimum, a later task must establish one of the following:

1. focused tests for file input, missing/malformed files, report writing, CLI defaults, all payload aliases, missing-score diagnosis, and score fallback paths; and
2. a retained current workflow that reproduces the dataset-generation and complete artifact contract;

or an explicit compatibility decision that formally accepts preservation of those historical behaviors only in the final archived evidence bundle.

Repository-setting facts and external consumers must remain `MANUAL_VERIFICATION_REQUIRED` until directly verified.

## Future final-run evidence bundle

If the candidate later becomes ready, the preservation run must record:

- workflow file path and pre-change blob SHA;
- commit SHA and branch;
- workflow run ID, run number, URL, actor, trigger input, timestamps, conclusion, and duration;
- job ID, step names, conclusions, and logs;
- exact `opportunity_limit` used;
- artifact ID, name, size, retention/expiry, digest when GitHub provides it, and downloaded archive SHA-256;
- complete archive inventory with file sizes and individual SHA-256 values;
- full contents or summarized assertions for:
  - `v2.7.2.3-daily-pipeline-run.json`
  - `v2.7.2.3-score-engine-trace.json`
  - `data/todays_opportunities.json`
  - every preserved investment file;
- record counts and trace counters;
- confirmation that no secret value appears in logs or artifacts;
- all unresolved external facts explicitly marked `MANUAL_VERIFICATION_REQUIRED`.

## Rollback approach

No rollback is required for this audit because no workflow or production behavior changed.

For any later reversible-disablement PR, rollback must be possible by reverting that single PR and restoring the exact pre-change workflow blob at the same path. Deletion, relocation, or renaming remains unapproved in the first cleanup pass.

## Safety confirmation

This audit:

- modifies no workflow;
- runs no preservation workflow;
- changes no production code;
- changes no score or financial formula;
- changes no threshold, recommendation, ranking, persistence, or domain behavior;
- adds no purchase, bid, contact, or alert action;
- selects no second historical workflow.
