# Workflow Simplification Checkpoint Review Task v1.0

**Status:** PROPOSED — PLANNING ONLY  
**Repository:** `Hindawi44/opportunity-engine`  
**Scope:** checkpoint review only; no workflow or product implementation change

## 1. Purpose

Decide whether the workflow-simplification checkpoint is complete enough to return to the approved product path:

```text
Opportunity Map
  -> Discovery Engine
  -> Opportunity Dossier
  -> Existing Analysis Engine
  -> Final Investment Report or Evidence-Required Outcome
```

This task must prevent two opposite errors:

1. continuing speculative workflow cleanup without a proven blocker;
2. declaring the checkpoint accepted while a repository-evidenced blocker still prevents the Clothing Inventory end-to-end path.

## 2. Authoritative evidence

The review must use tracked repository evidence, including:

- `docs/00_PROJECT_STATUS.md`;
- `docs/Opportunity_Discovery_Analysis_Blueprint_v2.0.md`;
- `docs/REPOSITORY_ARCHITECTURE_AUDIT_v2.0.md`;
- `docs/WORKFLOW_CLEANUP_IMPLEMENTATION_PLAN_v1.0.md`;
- accepted Wave 1, Wave 2, Wave 3, and Wave 4 documents;
- the merged Controlled End-to-End Clothing Inventory checkpoint;
- the merged real Clothing Inventory case validation;
- the current two-workflow operator surface;
- current workflow YAML, tests, scripts, source modules, reports, state contracts, and artifacts.

Conversation text is not authoritative evidence.

## 3. Required classification

Every remaining concern must be placed in exactly one class.

### 3.1 PROVEN_PRODUCT_BLOCKER

Use only when tracked repository evidence proves that the approved Clothing Inventory path cannot be executed or cannot produce an honest output.

A blocker must identify:

- the exact file or contract;
- the exact failing or missing behavior;
- how it prevents Discovery, Dossier construction, eligibility gating, Analysis, or final reporting;
- the smallest reversible correction;
- objective verification and rollback criteria.

### 3.2 MONITORED_OPERATIONAL_UNKNOWN

Use for facts not provable from tracked files, including:

- branch-protection settings;
- external consumers;
- hosted-cache continuity;
- external source availability or markup changes;
- secret availability;
- operational cadence assumptions.

These remain `MANUAL_VERIFICATION_REQUIRED` and do not block checkpoint acceptance unless tracked evidence proves that the product path depends on them immediately.

### 3.3 OPTIONAL_FUTURE_CLEANUP

Use for safe improvements that do not prevent the Clothing Inventory path, including additional trigger optimization, naming cleanup, schedule refinement, archival, or consolidation.

Optional cleanup must not become the next task during this checkpoint.

## 4. Decision criteria

### 4.1 SIMPLIFICATION_ACCEPTED

Return this decision only when all of the following are true:

1. the two-workflow operator surface remains available;
2. `tests.yml` remains the canonical repository-wide regression gate;
3. the approved Clothing Inventory Discovery path exists and remains test-covered;
4. one candidate can be preserved with source traceability;
5. the Opportunity Dossier contract exists and can be produced;
6. unsupported values remain unknown rather than invented;
7. the eligibility gate prevents unsupported financial analysis;
8. the existing Analysis Engine can return either a supported investment report or an honest `EVIDENCE_REQUIRED` outcome;
9. no automatic purchase, bid, contact, payment, or financial action occurs;
10. no `PROVEN_PRODUCT_BLOCKER` remains.

Operational unknowns and optional future cleanup may remain documented.

### 4.2 NOT_READY

Return this decision only when at least one `PROVEN_PRODUCT_BLOCKER` is documented with repository evidence and the exact blocked product stage.

`NOT_READY` must not be based only on:

- possible external consumers;
- unknown branch protection;
- hosted-cache uncertainty;
- optional cleanup;
- preference for more refactoring;
- absence of a perfect BUY recommendation;
- an honest `EVIDENCE_REQUIRED` result.

## 5. Required next task if accepted

If the decision is `SIMPLIFICATION_ACCEPTED`, select exactly one product-facing task:

```text
CLOTHING_INVENTORY_SINGLE_CASE_END_TO_END_EXECUTION_TASK_DEFINITION
```

That next task must execute one concrete Clothing Inventory case through the already approved path:

```text
one source-traceable candidate
  -> classification
  -> Opportunity Dossier
  -> eligibility gate
  -> Existing Analysis Engine
  -> final investment report or EVIDENCE_REQUIRED
```

The task must reuse existing contracts before adding new architecture.

It must not:

- add wedding dresses, fabrics, sewing equipment, store fixtures, or another domain;
- invent market values, costs, demand, or profit;
- force a BUY/WATCH/REJECT result when evidence is incomplete;
- modify frozen financial formulas without a verified compatibility defect;
- create another workflow-cleanup wave.

## 6. Required next task if not ready

If the decision is `NOT_READY`, select exactly one smallest correction task tied to one documented `PROVEN_PRODUCT_BLOCKER`.

No broad refactor, multi-workflow cleanup, or new-domain work is permitted.

## 7. Deliverable

Create one separate checkpoint-result document, proposed name:

```text
docs/WORKFLOW_SIMPLIFICATION_CHECKPOINT_REVIEW_RESULT_v1.0.md
```

It must contain:

- evidence reviewed;
- reconciliation of Waves 1–4;
- classification of every remaining concern;
- one explicit decision:
  - `SIMPLIFICATION_ACCEPTED`, or
  - `NOT_READY`;
- exactly one subsequent task;
- safety and rollback boundaries.

## 8. Prohibited changes in this task-definition PR

Do not modify or run:

- any file under `.github/workflows/`;
- production code;
- tests or fixtures;
- source adapters;
- state or cache contracts;
- reports or artifacts;
- financial formulas;
- source or domain scope.

Do not create an implementation issue, workflow, script, parser, analyzer, or automated purchase recommendation in this PR.

## 9. Success criteria

This task-definition PR succeeds only when:

1. exactly this one planning document is added;
2. the blocker classification is objective and repository-evidence-based;
3. the acceptance criteria protect honest `EVIDENCE_REQUIRED` outcomes;
4. no speculative cleanup wave is authorized;
5. checkpoint acceptance leads to one Clothing Inventory end-to-end execution task;
6. all repository checks pass.
