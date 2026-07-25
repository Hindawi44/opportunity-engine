# Opportunity Engine — Project Status

**Last updated:** 2026-07-25  
**Status:** ACTIVE  
**Authoritative repository:** `Hindawi44/opportunity-engine`

## Session startup rule

Every new development session must begin by reading, in this order:

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

A third bridge artifact is required between them:

- **Opportunity Dossier:** gathers and organizes all available evidence about a discovered opportunity before financial analysis.

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

No new domain implementation is approved until the workflow-simplification checkpoint below is completed and accepted.

Blocked domains remain:

- Wedding dresses
- Sewing equipment
- Fabrics
- Store fixtures
- Other opportunity domains

## Completed and retained

- Blueprint v2.0 approved as strategic baseline.
- Repository Architecture Audit v2.0 merged.
- Discovery and Analysis ownership boundaries defined.
- Existing Analysis Engine V2.8–V3.7 retained and frozen.
- Legacy FINN/Auksjonen adapters retained as optional providers.
- Clothing Inventory selected as the reference MVP domain.
- Opportunity Dossier specification approved as the bridge evidence artifact.
- All ten Clothing Inventory knowledge cards approved and merged.
- Controlled End-to-End Clothing Inventory checkpoint merged in PR #206.
- Real Clothing Inventory case validation merged in PR #208.
- Operator Workflow Inventory merged in PR #210.
- Operator Workflow Cleanup Implementation Plan merged in PR #212.
- Operator Workflow Wave 1 display-name changes merged in PR #214.
- Operator Workflow Wave 2A prerequisite audit merged in PR #216.

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

Accepted path:

```text
Real public candidate
  -> AUCTION
  -> SALE_CONFIRMED
  -> Opportunity Dossier
  -> Eligibility Gate
  -> EVIDENCE_REQUIRED
```

## Accepted workflow simplification result

The accepted work establishes:

- all 31 workflow files are represented;
- exactly one primary discovery workflow is selected;
- exactly one end-to-end review workflow is selected;
- `tests.yml` remains the canonical repository-wide quality-gate candidate;
- every workflow change has risk, dependency, rollback, and verification requirements;
- Wave 1 changed only the two operator-facing display names;
- Wave 2A documented duplicated full-regression runs and the first reversible Discovery cleanup slice;
- branch-protection and exact required-check settings remain `MANUAL_VERIFICATION_REQUIRED`.

Approved operator surface:

```text
1 — Discover Clothing Inventory Opportunities
2 — Review One Opportunity End to End
```

## Current phase

**Phase:** Operator Workflow Simplification — Wave 2B Discovery Acceptance Cleanup  
**Current task:** Apply the first reversible trigger and regression cleanup to two Discovery acceptance workflows only.

## Current implementation checkpoint

```text
OPERATOR_WORKFLOW_WAVE2B_DISCOVERY_CLEANUP
```

Status: `NEXT`

Current task document:

```text
docs/OPERATOR_WORKFLOW_WAVE2B_v1.0.md
```

## Knowledge-card phase

Status: `COMPLETE`

All ten scenarios remain complete. No additional Clothing Inventory knowledge card is approved unless a verified gap is found.

## Non-negotiable rules

- Do not delete existing production code.
- Do not modify V2.8–V3.7 financial formulas unless a verified compatibility defect exists.
- Do not add a new domain in this task.
- Do not add a new fixed-source architecture.
- Do not invent missing values.
- Preserve source traceability.
- Do not make an automatic purchase, bid, or contact decision.
- Wave 2B may modify only:
  - `.github/workflows/discovery-v1-clothing-inventory.yml`
  - `.github/workflows/discovery-v1.1-live-search.yml`
- Retain `workflow_dispatch` and existing focused test commands.
- Do not change workflow display names, job identifiers, Python versions, dependency installation, permissions, secrets, schedules, artifacts, environment variables, or production code.
- `tests.yml` must remain unchanged and must pass the complete regression suite on the same commit.
- Repository-settings facts not visible in tracked files remain `MANUAL_VERIFICATION_REQUIRED`.

## Definition of current-task success

Wave 2B succeeds only when:

1. both approved Discovery workflows receive exact pull-request path scopes;
2. both retain manual dispatch;
3. both retain their focused Discovery tests;
4. duplicated complete `pytest -q` steps are removed only from those two workflows;
5. `tests.yml` runs and passes on the same commit;
6. YAML syntax remains valid;
7. no other workflow or production file changes;
8. rollback is a direct revert restoring the previous YAML blobs.

## Immediate next action

Execute Wave 2B only:

1. update the two approved Discovery workflow files;
2. add exact path filters from the task document;
3. remove their duplicated complete regression steps;
4. preserve focused tests and manual dispatch;
5. add focused verification for the permitted scope;
6. do not begin schedule cleanup or diagnostic archival.