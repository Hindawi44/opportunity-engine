# Operator Workflow Wave 2A — Prerequisite Audit v1.0

**Status:** APPROVED — NEXT TASK  
**Scope:** audit and documentation only  
**Workflow behavior changes:** none

## Objective

Establish the evidence required before Wave 2 changes any pull-request trigger or removes duplicated full-regression commands from acceptance workflows.

Wave 2A exists because the accepted cleanup plan requires `tests.yml` to be confirmed as the canonical quality gate before another workflow stops running the complete `pytest -q` suite.

## Accepted Wave 1 result

PR #214 changed only the top-level displayed names of:

```text
.github/workflows/discovery-v1.2-live-pilot.yml
.github/workflows/v3.7-production-pilot.yml
```

Accepted operator labels:

```text
1 — Discover Clothing Inventory Opportunities
2 — Review One Opportunity End to End
```

No trigger, schedule, permission, secret, job, command, environment variable, artifact, or production behavior changed.

## Canonical quality-gate candidate

```text
.github/workflows/tests.yml
```

Tracked-file facts to verify and document:

- displayed workflow name;
- job identifier;
- `push` and `pull_request` branch coverage;
- Python and dependency installation behavior;
- full-suite command;
- pytest-log artifact name and path;
- final failure propagation behavior.

Repository-settings facts that may not be available from tracked files must be recorded as:

```text
MANUAL_VERIFICATION_REQUIRED
```

These include:

- whether the `tests.yml` check is required by branch protection;
- the exact required check name stored in repository settings;
- whether changing another workflow's displayed name affects required checks;
- whether any external automation depends on current check names.

## First Wave 2 implementation candidate

The safest initial implementation slice is Discovery Engine acceptance cleanup, limited to:

```text
.github/workflows/discovery-v1-clothing-inventory.yml
.github/workflows/discovery-v1.1-live-search.yml
```

Current overlap:

- both run focused Discovery tests;
- both also run the complete repository regression suite;
- `tests.yml` independently runs the complete repository regression suite.

Proposed future behavior — not applied in Wave 2A:

### `discovery-v1-clothing-inventory.yml`

- retain manual dispatch;
- path-scope pull requests to the Opportunity Map, classifier, related tests, and the workflow file;
- retain focused Discovery V1 tests;
- remove the duplicated complete `pytest -q` step only after quality-gate confirmation.

### `discovery-v1.1-live-search.yml`

- retain manual dispatch;
- path-scope pull requests to live-search/provider files, related tests, and the workflow file;
- retain the focused adapter test;
- remove the duplicated complete `pytest -q` step only after quality-gate confirmation.

## Required audit output

Create:

```text
docs/WORKFLOW_WAVE2A_PREREQUISITE_AUDIT_REPORT_v1.0.md
```

The report must contain:

1. Canonical `tests.yml` identity and behavior.
2. A table of workflows currently running full `pytest -q` on pull requests.
3. The exact proposed path scopes for the two Discovery workflows.
4. The focused tests that remain in each workflow.
5. Check-name and branch-protection status:
   - `CONFIRMED`,
   - `UNCONFIRMED`, or
   - `MANUAL_VERIFICATION_REQUIRED`.
6. Risk assessment.
7. Rollback instructions.
8. Verification bundle for the future implementation PR.
9. Confirmation that no workflow file changed during the audit.

## Risk

Overall risk for this audit is `LOW` because it changes documentation only.

The later implementation is `MEDIUM` because trigger narrowing or removal of duplicated regression commands can alter pull-request check coverage.

## Future rollback requirement

For every later workflow change:

- preserve the exact pre-change blob SHA;
- restore the previous YAML through a revert if focused checks or branch protection are insufficient;
- restore the complete regression command if the canonical gate does not run or is not required;
- restore the previous pull-request trigger if path scoping omits a relevant file.

## Future verification bundle

Before merging the first Wave 2 implementation PR, require:

- YAML syntax validation;
- focused tests passing in each changed workflow;
- `tests.yml` complete regression passing on the same commit;
- pytest-log artifact still uploaded by `tests.yml`;
- manual dispatch retained for both Discovery workflows;
- check-name and branch-protection review completed;
- no change to production code, financial formulas, domains, sources, purchase, bidding, or contact behavior.

## Scope lock

Wave 2A must not:

- modify `.github/workflows/`;
- change branch protection;
- remove regression commands;
- add path filters;
- change schedules;
- change operator workflow names;
- modify production code;
- add domains or source adapters;
- begin Wave 3 or Wave 4.

## Acceptance criteria

Wave 2A passes only when:

- the prerequisite audit report is complete;
- uncertainty about repository settings is stated honestly;
- the first implementation slice is exact and reversible;
- no workflow behavior changed;
- all repository checks pass.