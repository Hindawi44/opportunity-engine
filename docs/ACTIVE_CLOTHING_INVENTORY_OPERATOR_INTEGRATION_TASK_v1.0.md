# Active Clothing Inventory Operator Integration Task v1.0

**Task type:** Planning-only task definition  
**Domain:** `CLOTHING_INVENTORY`  
**Implementation status:** `NOT_STARTED`  
**Automatic commercial action:** Prohibited

## 1. Purpose

Define the minimum safe integration of:

```text
scripts/run_active_clothing_inventory_scan.py
```

into exactly one existing approved manual operator workflow.

This task-definition PR must create this document only. It must not modify any workflow, production code, test, fixture, state, cache, report, artifact, source adapter, scoring threshold, decision policy, or financial formula.

## 2. Existing approved operator workflows

### Workflow 1 — Discovery

```text
.github/workflows/discovery-v1.2-live-pilot.yml
Display name: 1 — Discover Clothing Inventory Opportunities
```

Observed contract:

- path-scoped `pull_request` validation;
- manual `workflow_dispatch` execution;
- Discovery-focused contract tests;
- one manual Brave live-pilot job;
- JSON and phone-readable artifacts.

### Workflow 2 — End-to-end review

```text
.github/workflows/v3.7-production-pilot.yml
Display name: 2 — Review One Opportunity End to End
```

Observed contract:

- manual-only `workflow_dispatch` execution;
- one deterministic V3.7 acceptance test;
- one production-pilot summary artifact.

## 3. Integration target decision

Select exactly this workflow:

```text
.github/workflows/discovery-v1.2-live-pilot.yml
```

Reason:

- the active scan determines whether a live Clothing Inventory opportunity exists;
- `ACTIVE_CANDIDATE_SELECTED` is a Discovery outcome that may create an Opportunity Dossier;
- `NO_ACTIVE_CANDIDATE` is a valid Discovery outcome with no opportunity available for review;
- integrating the scan into the end-to-end review workflow would incorrectly treat a no-candidate scan as an opportunity-review operation;
- the approved two-workflow operator surface remains unchanged.

The following workflow is explicitly not selected:

```text
.github/workflows/v3.7-production-pilot.yml
```

It must remain unchanged by the subsequent implementation PR.

## 4. Active scan runner contract

The existing runner must be reused without production-code modification:

```text
scripts/run_active_clothing_inventory_scan.py
```

Live command:

```bash
python scripts/run_active_clothing_inventory_scan.py \
  --output-dir artifacts/active-clothing-inventory-scan
```

The runner has two successful operational outcomes.

### Outcome A — active candidate

```text
scan_outcome: ACTIVE_CANDIDATE_SELECTED
```

Required outputs:

```text
artifacts/active-clothing-inventory-scan/opportunity-dossier.json
artifacts/active-clothing-inventory-scan/final-report.json
artifacts/active-clothing-inventory-scan/operator-summary.txt
```

Required preserved behavior:

- selected listing status is exactly `ACTIVE`;
- source URL, title, listing identifier, observed price, location, and observation time remain traceable when available;
- missing evidence remains unknown;
- the existing end-to-end path is reused;
- any `BUY_REVIEW` result remains human-review-only.

### Outcome B — no active candidate

```text
scan_outcome: NO_ACTIVE_CANDIDATE
final_decision: NO_DECISION
```

Required outputs:

```text
artifacts/active-clothing-inventory-scan/scan-report.json
artifacts/active-clothing-inventory-scan/operator-summary.txt
```

Required preserved behavior:

- the workflow succeeds operationally;
- analysis is not invoked;
- decision intelligence is not invoked;
- ended Clothing Inventory listings may remain traceable evidence;
- no Opportunity Dossier is manufactured;
- no ended listing is promoted as a live opportunity.

## 5. Manual operator mode

The subsequent implementation must preserve one approved Discovery workflow while separating its two manual operations through one `workflow_dispatch` choice input.

Approved input contract:

```yaml
workflow_dispatch:
  inputs:
    operation:
      description: Select the Discovery operation
      required: true
      default: brave_discovery
      type: choice
      options:
        - brave_discovery
        - active_clothing_scan
```

Rules:

- `brave_discovery` must retain the current Brave live-pilot behavior unchanged;
- `active_clothing_scan` must run only the active Clothing Inventory scan job;
- no schedule may be added;
- no automatic execution may be added;
- the two operations must not depend on one another;
- the active scan must not require `BRAVE_SEARCH_API_KEY`.

## 6. Minimum workflow implementation

The subsequent implementation PR may modify only the selected Discovery workflow and one focused workflow-contract test.

### Workflow changes

In:

```text
.github/workflows/discovery-v1.2-live-pilot.yml
```

The implementation must:

1. add the approved `operation` choice input under `workflow_dispatch`;
2. preserve the current `pull_request` trigger and existing Discovery path scope;
3. extend the path scope only with:

```text
scripts/run_active_clothing_inventory_scan.py
tests/test_active_clothing_inventory_scan.py
tests/test_active_clothing_inventory_operator_integration.py
```

4. preserve the existing `contract-tests` job and its three current test commands;
5. add this focused test command to `contract-tests`:

```bash
pytest tests/test_active_clothing_inventory_scan.py -q
```

6. restrict the existing Brave `live-pilot` job to the `brave_discovery` operation;
7. add one manual job named `active-clothing-inventory-scan` restricted to the `active_clothing_scan` operation;
8. use Python 3.11 and the repository's existing lightweight dependency installation pattern;
9. execute the approved runner command exactly once;
10. print `artifacts/active-clothing-inventory-scan/operator-summary.txt` with an `always()` step;
11. upload the entire directory:

```text
artifacts/active-clothing-inventory-scan/
```

12. use the stable artifact name:

```text
active-clothing-inventory-scan
```

13. treat missing scan outputs as an implementation failure rather than silently accepting an empty artifact.

### Focused workflow-contract test

Create:

```text
tests/test_active_clothing_inventory_operator_integration.py
```

The test must prove:

- the selected workflow display name remains `1 — Discover Clothing Inventory Opportunities`;
- `workflow_dispatch` exposes only the approved operation choices;
- the default operation preserves current Brave behavior;
- the Brave job and active-scan job are mutually selected by the operation input;
- the active scan command and output directory are exact;
- the operator summary is printed;
- the full active-scan directory is uploaded under the stable artifact name;
- both active-scan focused tests and existing Discovery tests remain in `contract-tests`;
- no schedule is introduced;
- `.github/workflows/v3.7-production-pilot.yml` is not modified;
- no purchase, bid, contact, or payment command is introduced.

## 7. Subsequent implementation PR scope

Exactly one implementation task may follow this document:

```text
ACTIVE_CLOTHING_INVENTORY_OPERATOR_INTEGRATION_IMPLEMENTATION
```

Expected changed files:

```text
.github/workflows/discovery-v1.2-live-pilot.yml
tests/test_active_clothing_inventory_operator_integration.py
```

No other file is approved for modification. If production-code changes are discovered to be necessary, implementation must stop and a separate compatibility task must be defined.

## 8. Required validation

The implementation PR must pass:

```bash
pytest tests/test_active_clothing_inventory_scan.py -q
pytest tests/test_active_clothing_inventory_operator_integration.py -q
pytest tests/test_discovery_v16_quality_engine.py -q
pytest tests/test_discovery_v15_result_filter.py -q
pytest tests/test_discovery_v12_live_pilot.py -q
```

The canonical repository regression suite must also pass.

A manual `workflow_dispatch` verification remains required after merge for both choices:

```text
brave_discovery
active_clothing_scan
```

If repository evidence cannot verify a GitHub setting, secret, external consumer, or hosted artifact behavior, classify it as:

```text
MANUAL_VERIFICATION_REQUIRED
```

## 9. Safety invariants

The implementation must preserve:

```text
automatic_purchase_decision: false
automatic_bid: false
automatic_contact: false
automatic_payment: false
```

It must also preserve:

- `BUY_REVIEW` requires human approval;
- only explicitly `ACTIVE` listings may enter live review;
- `ENDED` listings remain ineligible;
- missing values are never converted to zero or invented;
- source traceability remains intact;
- `NO_ACTIVE_CANDIDATE` and `NO_DECISION` are successful, non-commercial outcomes;
- no financial formula, scoring threshold, or decision policy changes.

## 10. Out of scope

The task does not approve:

- modifying the V3.7 end-to-end review workflow;
- adding a schedule;
- creating a third operator workflow;
- adding another source or domain;
- changing the runner or source adapter;
- adding automatic notifications;
- adding automatic purchase, bid, contact, payment, or financial action;
- changing state, cache, report, or artifact contracts outside the selected workflow integration;
- changing V2.8–V3.7 formulas or canonical decision thresholds.

## 11. Definition of done

This planning task is complete only when:

1. this is the only file changed in the task-definition PR;
2. exactly one existing approved workflow is selected;
3. the alternative workflow is explicitly excluded;
4. the manual input, job conditions, command, outputs, summary, and artifact contract are exact;
5. both successful scan outcomes are preserved;
6. focused and canonical tests are required;
7. all safety invariants are explicit;
8. exactly one subsequent implementation task is identified;
9. all repository checks pass.
