# Opportunity Engine — Project Status

**Last updated:** 2026-07-25  
**Status:** ACTIVE  
**Authoritative repository:** `Hindawi44/opportunity-engine`

## Session startup rule

Every development session must begin by reading, in this order:

1. `docs/00_PROJECT_STATUS.md`
2. `docs/Opportunity_Discovery_Analysis_Blueprint_v2.0.md`
3. `docs/REPOSITORY_ARCHITECTURE_AUDIT_v2.0.md`
4. The current-task document named below

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

- V2.6.6 is a manual historical production-readiness diagnostic;
- no tracked current workflow reproduces its exact live two-run evidence bundle and artifact contract;
- unit tests cover readiness, secret non-disclosure, missing-secret failure, and repeat-protection comparison;
- the approved decision is `FINAL_MANUAL_RUN_THEN_DISABLE_IN_SEPARATE_PR`;
- the workflow must not be disabled, archived, relocated, renamed, or deleted before preservation evidence is recorded;
- branch protection, external consumers, operator dependence, secret availability, and historical artifact links remain `MANUAL_VERIFICATION_REQUIRED`.

## Current phase

**Phase:** Operator Workflow Simplification — Wave 4 Historical Diagnostics  
**Current task:** Run V2.6.6 manually one final time and preserve its evidence before any disablement action.

## Current implementation checkpoint

```text
OPERATOR_WORKFLOW_WAVE4B_V266_FINAL_PRESERVATION_RUN
```

Status: `NEXT`

Current task document:

```text
docs/OPERATOR_WORKFLOW_WAVE4B_v1.0.md
```

## Non-negotiable rules

- Do not delete existing production code.
- Do not modify V2.8–V3.7 financial formulas unless a verified compatibility defect exists.
- Do not add a new domain.
- Do not invent missing values.
- Preserve source traceability.
- Do not make an automatic purchase, bid, or contact decision.
- Wave 4B is manual execution, evidence capture, and documentation only.
- Do not change, disable, archive, rename, relocate, or delete `.github/workflows/v2.6.6-live-dry-run.yml` in Wave 4B.
- Preserve run metadata, artifact checksum, file inventory, and the honest repeat-protection result.
- Repository-setting facts and external consumers not visible in tracked files remain `MANUAL_VERIFICATION_REQUIRED`.

## Definition of current-task success

Wave 4B succeeds only when:

1. V2.6.6 is run manually from `main` with the input value recorded;
2. run ID, URL, commit SHA, times, conclusion, and job name are recorded;
3. artifact `v2.6.6-live-dry-run` is downloaded before expiry;
4. archive checksum and file inventory are recorded;
5. both dry-run summaries and `production_readiness_final.json` are inspected;
6. `repeat_protection_observed` is recorded honestly;
7. secret values are not exposed;
8. unresolved external facts remain `MANUAL_VERIFICATION_REQUIRED`;
9. no workflow or production-code change occurs;
10. all repository checks pass for the evidence PR.

## Immediate next action

Execute Wave 4B only:

1. merge the status-definition PR after all checks pass;
2. open GitHub Actions and select `V2.6.6 Live Dry Run`;
3. run it manually on `main` with `opportunity_limit=2` unless another value is explicitly recorded;
4. wait for completion and inspect the honest result;
5. download artifact `v2.6.6-live-dry-run` before its 14-day expiry;
6. record run metadata, checksum, file inventory, JSON validity, dry-run comparison, and missing-file or source errors;
7. do not disable or delete the workflow yet.