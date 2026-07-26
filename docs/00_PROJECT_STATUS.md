# Opportunity Engine — Project Status

**Last updated:** 2026-07-26  
**Status:** ACTIVE  
**Authoritative repository:** `Hindawi44/opportunity-engine`

## Session startup rule

Every development session must begin by reading, in this order:

1. `docs/00_PROJECT_STATUS.md`
2. `docs/Opportunity_Discovery_Analysis_Blueprint_v2.0.md`
3. `docs/REPOSITORY_ARCHITECTURE_AUDIT_v2.0.md`
4. The current-task document named below, when one is approved

The conversation is not the source of truth. The repository is the source of truth.

## Product principle

The project has two independent engines:

- **Discovery Engine:** discovers opportunities.
- **Analysis Engine:** analyzes confirmed opportunities.

Neither engine may perform the other engine's responsibility.

The bridge between them is the **Opportunity Dossier**, which gathers and organizes available evidence before financial analysis.

## Approved end-to-end path

```text
Opportunity Map
  -> Discovery Engine
  -> Opportunity Dossier
  -> Existing Analysis Engine
  -> Final Investment Report or Evidence-Required Outcome
```

## Current scope lock

The only validated domain is:

```text
CLOTHING_INVENTORY
```

Blocked domains remain:

- Wedding dresses
- Sewing equipment
- Fabrics
- Store fixtures
- Other opportunity domains

No new domain implementation is approved until the workflow-simplification checkpoint is completed and accepted.

## Completed and retained

- Blueprint v2.0 approved as strategic baseline.
- Repository Architecture Audit v2.0 merged.
- Existing Analysis Engine V2.8–V3.7 retained and frozen.
- Clothing Inventory selected as the reference MVP domain.
- Opportunity Dossier specification approved.
- All ten Clothing Inventory knowledge cards approved and merged.
- Controlled End-to-End Clothing Inventory checkpoint merged in PR #206.
- Real Clothing Inventory case validation merged in PR #208.
- Operator Workflow Inventory merged in PR #210.
- Operator Workflow Cleanup Implementation Plan merged in PR #212.
- Wave 1 operator display names merged in PR #214.
- Wave 2A prerequisite audit merged in PR #216.
- Wave 2B Discovery cleanup merged in PR #218.
- Wave 2C primary Discovery cleanup merged in PR #220.
- Wave 3A V3.7 schedule/dependency audit merged in PR #222.
- Wave 3B V3.7 manual-only conversion merged in PR #223.
- Wave 3C V3.2 monitoring ownership audit merged in PR #225.
- Wave 3D V3.2 pull-request trigger scoping merged in PR #227.
- Wave 3E V3.3 live-source ingestion ownership audit merged in PR #229.
- Wave 4A V2.6.6 historical diagnostic audit merged in PR #231.
- Wave 4B preservation-evidence definition merged in PR #232.
- Wave 4B initial evidence document merged in PR #233.
- Wave 4B final preservation run accepted with run ID `30175512518`, artifact ID `8624093715`, complete archive inventory, and artifact digest `sha256:57cc918d719a1aafa6720bff486035daf157a5e09e641f6e61214b6c8ff89420`.
- Wave 4C reversible disablement merged in PR #234: `.github/workflows/v2.6.6-live-dry-run.yml` remains preserved at the same path, is manual-only through `workflow_dispatch`, and includes an explicit historical-diagnostic notice and documented rollback procedure.
- Post-Wave 4C checkpoint merged in PR #235; no second workflow change was started before selecting one exact next task.

## Accepted Clothing Inventory result

The merged real case proves:

- one public Clothing Inventory candidate is preserved with source traceability;
- the candidate is classified using the approved Opportunity Map;
- a complete Opportunity Dossier is produced;
- unsupported values remain unknown rather than invented;
- the eligibility gate blocks incomplete evidence from financial analysis;
- the result reaches an honest `EVIDENCE_REQUIRED` outcome;
- no automatic purchase, bid, or contact action occurs;
- all repository checks pass.

## Accepted operator surface

```text
1 — Discover Clothing Inventory Opportunities
2 — Review One Opportunity End to End
```

The primary Discovery workflow is path-scoped and retains manual live execution. The end-to-end review workflow is manual-only and retains its focused test, deterministic summary, and artifact.

## Accepted monitoring conclusion

Tracked repository evidence establishes:

- V3.2 is the primary continuous-monitoring owner;
- its hourly schedule `17 * * * *` is collision-free relative to V3.7 and should remain;
- stateful duplicate protection works when prior state is supplied;
- V3.2 and V3.3 share a state-file path but use separate cache namespaces;
- the V3.2 pull-request trigger is scoped to its six tracked dependencies;
- V3.3 remains the temporary repository-owned Auksjonen ingestion and snapshot-refresh workflow;
- the continued operational need for V3.3's hourly schedule remains `MANUAL_VERIFICATION_REQUIRED`;
- external consumers, branch protection, and hosted cache continuity remain `MANUAL_VERIFICATION_REQUIRED`.

## Accepted historical-diagnostic conclusion

Tracked repository evidence establishes:

- V2.6.6 is a preserved, manual-only historical production-readiness diagnostic;
- no tracked current workflow reproduces its exact live two-run evidence bundle and artifact contract;
- unit tests cover readiness, secret non-disclosure, missing-secret failure, and repeat-protection comparison;
- the final manual run completed successfully on `main`;
- its run metadata, artifact metadata, archive digest, complete inventory, readiness evidence, and repeat-protection evidence were preserved;
- the workflow is non-routine through a reversible repository change and remains available only for intentional manual execution;
- the workflow file was not deleted, renamed, relocated, or archived;
- branch protection, external consumers, operator dependence, and historical artifact links remain `MANUAL_VERIFICATION_REQUIRED`;
- deletion remains unapproved.

## Current phase

**Phase:** Operator Workflow Simplification — Wave 4 Historical Diagnostics  
**Current task:** Audit whether current V2.10 coverage is equivalent to the historical V2.7.2.5 financial final-score workflow, and define its preservation requirements before any disablement proposal.

## Current implementation checkpoint

```text
OPERATOR_WORKFLOW_WAVE4D_V2725_FINANCIAL_FINAL_SCORE_COVERAGE_AUDIT
```

Status: `NEXT`

Current task document:

```text
docs/OPERATOR_WORKFLOW_WAVE4D_v1.0.md
```

## Selection rationale

Exactly one remaining Wave 4 candidate is selected:

```text
.github/workflows/v2.7.2.5-external-financial-final-score.yml
```

The candidate is selected because the repository already identifies V2.10 as the authoritative verified-financial integration and decision gate, while the historical workflow remains manual-only and has a bounded artifact and financial-score contract suitable for direct coverage comparison.

Selection does not mean the candidate is ready for disablement. Wave 4D must first classify it honestly as `READY_FOR_FINAL_PRESERVATION_RUN` or `NOT_READY`.

## Non-negotiable rules

- Do not delete existing production code.
- Do not modify V2.8–V3.7 financial formulas unless a verified compatibility defect exists.
- Do not add a new domain.
- Do not invent missing values.
- Preserve source traceability.
- Do not make an automatic purchase, bid, or contact decision.
- Wave 4D is a coverage audit and preservation-planning task only.
- Do not modify, disable, archive, rename, relocate, or delete `.github/workflows/v2.7.2.5-external-financial-final-score.yml` in Wave 4D.
- Do not select or change a second historical workflow.
- Repository-setting facts and external consumers not visible in tracked files remain `MANUAL_VERIFICATION_REQUIRED`.

## Definition of current-task success

Wave 4D succeeds only when:

1. the historical V2.7.2.5 workflow contract is documented accurately;
2. each material behavior is mapped to current V2.10 tests or workflows;
3. coverage is classified as `COVERED`, `PARTIALLY_COVERED`, `NOT_COVERED`, or `MANUAL_VERIFICATION_REQUIRED`;
4. unique historical behavior and artifact differences are recorded without assumptions;
5. the candidate is classified `READY_FOR_FINAL_PRESERVATION_RUN` or `NOT_READY`;
6. the exact final-run evidence bundle and rollback approach are defined;
7. unresolved external facts remain `MANUAL_VERIFICATION_REQUIRED`;
8. no workflow, production code, financial formula, or operator behavior changes;
9. all repository checks pass for the Wave 4D audit PR.

## Immediate next action

Execute Wave 4D only:

1. inspect `.github/workflows/v2.7.2.5-external-financial-final-score.yml` and its scripts;
2. inspect the authoritative V2.10 workflow and focused tests;
3. build a behavior-by-behavior coverage matrix;
4. document gaps, unique persistence or artifact behavior, and external unknowns;
5. classify readiness for a later final preservation run;
6. do not modify or disable the workflow in this task.
