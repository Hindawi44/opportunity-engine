# Operator Workflow Wave 4A — V2.6.6 Historical Diagnostic Audit v1.0

**Status:** APPROVED — NEXT AUDIT TASK  
**Scope:** documentation and verification only

## Accepted prerequisite

Wave 3E completed the V3.3 live-source ingestion ownership audit without changing workflow or production behavior.

## Objective

Audit the historical diagnostic workflow:

```text
.github/workflows/v2.6.6-live-dry-run.yml
```

before any disablement, archival, rename, relocation, or trigger change.

## Required audit questions

1. What exact diagnostic purpose does V2.6.6 still serve?
2. Which scripts, fixtures, reports, artifacts, inputs, and secrets does it reference?
3. Which current tests or workflows provide equivalent coverage?
4. Does any tracked workflow, documentation, branch protection rule, or external operator depend on its check or artifact names?
5. Can it be safely disabled or archived after one final verified manual run?
6. What exact pre-change commit SHA and artifact evidence must be preserved?
7. What repository-setting or external-consumer facts remain `MANUAL_VERIFICATION_REQUIRED`?

## Permitted changes

Wave 4A may add only:

- one V2.6.6 historical-diagnostic audit report under `docs/`;
- one focused verification test for that report.

## Prohibited changes

Do not modify:

- `.github/workflows/v2.6.6-live-dry-run.yml`;
- any workflow trigger, job, command, permission, report, or artifact;
- production code or financial formulas;
- domain scope;
- purchase, bid, or contact behavior.

Do not delete or disable any historical workflow in this audit task.

## Required evidence

The audit must inspect the V2.6.6 workflow and every directly referenced script, test, fixture, report, artifact, input, and secret contract. It must compare that evidence with current repository coverage and distinguish tracked facts from external operational facts.

## Success criteria

Wave 4A succeeds only when:

1. the V2.6.6 diagnostic contract is documented precisely;
2. equivalent current coverage is demonstrated or gaps are identified honestly;
3. tracked and external consumers are classified;
4. the pre-change commit SHA and artifact-preservation requirements are explicit;
5. a future keep, disable, or archive recommendation is documented without implementation;
6. rollback and verification requirements are explicit;
7. no workflow or production-code change occurs;
8. all repository checks pass.
