# Wave 2J — V3.5 Trigger and Regression Audit

**Result:** `READY_FOR_PATH_SCOPING`  
**Scope:** documentation-only prerequisite audit  
**Workflow:** `.github/workflows/v3.5-opportunity-alert-review-queue.yml`

## Executive conclusion

The V3.5 opportunity-alert and review-queue acceptance workflow has a finite, traceable repository-owned execution boundary and is ready for a separate trigger-only path-scoping implementation.

The workflow retains manual dispatch, runs one focused V3.5 acceptance test, uses no schedule, secret, permission elevation, cache, hosted state, report upload, artifact upload, or broad repository-wide regression step. The focused test exercises duplicate-safe alert generation, material-update alerts, queue-status preservation, eligibility gating, deterministic queue ordering, and the no-automatic-purchase contract.

No workflow or production code was modified or run during this audit.

## Current workflow contract

The workflow currently:

- triggers on every pull request to `main`;
- retains `workflow_dispatch`;
- uses Python 3.11 with repository `src` and root on `PYTHONPATH`;
- installs only `pytest`;
- runs `pytest tests/test_v35_opportunity_alert_review_queue.py -q`;
- has no schedule, cache, secret, write permission, report-generation step, state-file write step, or artifact upload step;
- fails when the focused pytest command fails.

## Dependency trace

### Focused test

`tests/test_v35_opportunity_alert_review_queue.py`:

- imports `set_queue_status` and `update_review_queue` from `src/opportunity_engine/opportunity_review_queue.py`;
- constructs all candidate records and state payloads inline, so no tracked fixture is required;
- verifies ineligible candidates are excluded from the review queue;
- verifies eligible candidates create queue items and initial alerts;
- verifies repeat processing produces no new alert and preserves alert fingerprints;
- verifies a material evidence update creates exactly one `MATERIAL_UPDATE` alert;
- verifies a `SNOOZED` queue status survives a later material update;
- verifies queue ordering places the higher-priority opportunity first;
- verifies `duplicate_alerts` remains zero;
- verifies `automatic_purchase_decision` remains `False`;
- verifies a successful report has status `PASS`.

### V3.5 review-queue implementation

`src/opportunity_engine/opportunity_review_queue.py`:

- defines the authoritative eligibility gate `READY_FOR_FINANCIAL_REVIEW`;
- requires a stable `opportunity_id`, at least three verified comparables, at least six verified cost components, numeric expected profit, numeric ROI, and `automatic_purchase_decision: false`;
- fingerprints the opportunity ID, decision gate, expected profit, ROI, evidence counts, and evidence version;
- suppresses alerts when the current fingerprint matches the previous fingerprint or an already-seen alert fingerprint;
- classifies first alerts as `NEWLY_ELIGIBLE` and changed fingerprints as `MATERIAL_UPDATE`;
- preserves valid queue states `PENDING_REVIEW`, `SNOOZED`, `IGNORED`, and `REVIEWED`;
- assigns deterministic `HIGH`, `MEDIUM`, or `NORMAL` priority;
- sorts the queue deterministically by priority, ROI, expected profit, and opportunity ID;
- stores JSON-serializable state schema version `3.5`;
- uses only Python standard-library dependencies;
- preserves `automatic_purchase_decision: false` in every queue item and report.

### CLI entrypoint

`scripts/run_v35_opportunity_alert_review_queue.py`:

- imports `update_review_queue` from `src/opportunity_engine/opportunity_review_queue.py`;
- reads ranked candidates from `data/validation/v3.0-multi-opportunity-ranking.json` by default;
- reads and writes explicit V3.5 review-queue state;
- writes the V3.5 report and next state as deterministic JSON;
- exits non-zero only when report errors exist.

The focused workflow does not execute this CLI. Therefore its default input, state, and report paths are runtime CLI defaults rather than deterministic inputs required by the current workflow acceptance boundary. The CLI file remains part of the owned V3.5 surface because it is the repository entrypoint for the implementation protected by the focused test.

### Upstream and downstream contract boundaries

V3.5 consumes already-evaluated opportunity records. It does not calculate comparables, logistics costs, verified financial results, or ranking inside the focused workflow. The acceptance test supplies those record fields inline and therefore does not import V3.0, V2.10, V2.9, or V2.8 code.

The review queue is a human-review boundary. It creates no purchase, bid, contact, payment, or financial decision and has no downstream execution dependency inside the focused test.

## Coverage matrix

| Audit question | Finding |
|---|---|
| Current trigger | Broad `pull_request` to `main`, plus `workflow_dispatch` |
| Manual dispatch preservable | Yes |
| Focused command | `pytest tests/test_v35_opportunity_alert_review_queue.py -q` |
| Failure behavior | Pytest failure returns a non-zero workflow step |
| Eligibility boundary | Only complete `READY_FOR_FINANCIAL_REVIEW` records enter the queue |
| Duplicate-alert behavior | Unchanged fingerprints create no new alert |
| Material-update behavior | Changed fingerprints create one `MATERIAL_UPDATE` alert |
| Queue-status behavior | Valid human-review statuses survive later updates |
| State schema | JSON-serializable V3.5 items and alert fingerprints |
| Deterministic fixture ownership | Inline test candidates and state; no external fixture required |
| Generated files/artifacts | None generated or uploaded by the current workflow |
| Cache/hosted continuity | None used by the current workflow |
| Secrets/permissions | None |
| Broad regression duplication | No; only one focused test runs |
| Canonical full regression | `.github/workflows/tests.yml` remains the owner |
| Automatic action | Explicitly prohibited and remains `False` |
| Trigger-only rollback | Exact revert restoring the current broad PR trigger |

## Proposed minimal pull-request path scope

```text
.github/workflows/v3.5-opportunity-alert-review-queue.yml
tests/test_v35_opportunity_alert_review_queue.py
scripts/run_v35_opportunity_alert_review_queue.py
src/opportunity_engine/opportunity_review_queue.py
```

This four-path set covers the workflow definition, focused test, repository CLI entrypoint, and V3.5 implementation.

The default CLI input, state, and report JSON paths are not included because the accepted workflow does not execute the CLI and the focused test constructs deterministic candidates and state inline. Changes to upstream ranking or financial code remain covered by their own focused workflows and by the canonical repository regression gate. A future change that makes this workflow execute the CLI or consume tracked fixtures would require a separate scope review.

## Preserved behavior required in a future implementation

A separate implementation PR must preserve:

- `workflow_dispatch`;
- `branches: [ main ]`;
- workflow display name and job identifier;
- Python version, environment, and dependency installation;
- focused V3.5 test command;
- eligibility requirements and missing-evidence honesty;
- fingerprint fields and duplicate-alert suppression;
- `NEWLY_ELIGIBLE` and `MATERIAL_UPDATE` reasons;
- priority thresholds and deterministic queue ordering;
- queue statuses and status preservation;
- V3.5 state schema and serialization;
- inline test data and assertions;
- no report, cache, state persistence, or artifact contract added to the workflow;
- `automatic_purchase_decision: false` and all no-automatic-action protections.

## Canonical regression ownership

This workflow does not execute `pytest -q` across the repository. `.github/workflows/tests.yml` remains the canonical full-regression owner. A future path-scoping implementation must not add a duplicate broad regression step.

## External facts

The following remain:

```text
MANUAL_VERIFICATION_REQUIRED
```

- branch-protection required-check dependence;
- external consumers of the workflow or check name;
- operator dependence on the broad pull-request trigger;
- external consumers of the generated CLI report or state paths;
- historical check links and repository-level retention expectations.

Hosted cache or external-state continuity is not part of the current workflow contract because the workflow does not restore, persist, or upload state.

## Rollback

Rollback is an exact revert of the future trigger-only implementation, restoring:

- `pull_request.branches: [ main ]` without `paths`;
- the exact pre-change workflow blob.

## Final classification

```text
READY_FOR_PATH_SCOPING
```

A separate Wave 2K task-definition PR and a later implementation PR may add the four-path owned-file scope documented above. No workflow change is included in this audit.
