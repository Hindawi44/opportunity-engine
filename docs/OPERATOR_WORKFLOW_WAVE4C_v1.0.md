# Operator Workflow Wave 4C — V2.6.6 Reversible Disablement v1.0

**Status:** APPROVED — CURRENT OPERATOR TASK  
**Scope:** reversible workflow disablement and documentation only

## Accepted prerequisite

Wave 4B preserved and accepted the final manual evidence for:

```text
.github/workflows/v2.6.6-live-dry-run.yml
```

The accepted decision is:

```text
FINAL_MANUAL_RUN_COMPLETE_THEN_REVERSIBLY_DISABLE
```

## Objective

Make the historical V2.6.6 production-readiness diagnostic non-routine through the smallest reversible repository change, while preserving the workflow file, its history, and the Wave 4B evidence.

## Approved mechanism

The workflow may remain available only for intentional manual execution through `workflow_dispatch`.

Any automatic or routine trigger must be absent. The workflow file must remain at its existing path and retain its historical diagnostic purpose.

## Required implementation

1. Inspect `.github/workflows/v2.6.6-live-dry-run.yml`.
2. Preserve `workflow_dispatch` so an operator can intentionally run the historical diagnostic.
3. Remove or disable any routine trigger if one exists.
4. Add an explicit workflow comment stating that the workflow is historical, manual-only, and preserved for rollback and evidence continuity.
5. Do not alter the diagnostic scripts, production code, financial formulas, secret handling, artifact contract, or domain scope.

## Reversal procedure

To reverse Wave 4C:

1. revert the Wave 4C commit or PR;
2. restore the previous trigger block exactly from Git history;
3. run repository checks;
4. record why routine execution is required again.

No new implementation is required for rollback because the workflow file and its history remain preserved.

## External checks

The following remain:

```text
MANUAL_VERIFICATION_REQUIRED
```

- branch-protection dependence on the workflow or job name;
- external dashboards, APIs, notifications, or compliance consumers;
- operators relying on the Actions entry;
- historical links outside tracked repository files.

## Prohibited changes

- Do not delete the workflow.
- Do not rename, relocate, or archive the workflow.
- Do not modify production code or financial formulas.
- Do not add a new domain.
- Do not change purchase, bid, contact, alert, or ranking behavior.
- Do not remove the Wave 4B evidence.

## Success criteria

Wave 4C succeeds only when:

1. the workflow file remains at its current path;
2. the workflow is manual-only and non-routine;
3. the disablement is reversible by reverting one focused change;
4. the rollback procedure is documented;
5. Wave 4B evidence remains preserved;
6. no production behavior or financial formula changes;
7. unresolved external facts remain `MANUAL_VERIFICATION_REQUIRED`;
8. all repository checks pass.
