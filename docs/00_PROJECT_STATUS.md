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
- `tests.yml` remains the canonical repository-wide quality gate;
- every future workflow change has a defined risk, dependency, rollback, verification requirement, and implementation wave;
- Wave 1 changed only the two top-level displayed workflow names;
- no trigger, schedule, permission, secret, job, command, environment variable, artifact, or production behavior changed in Wave 1.

Approved operator surface:

```text
1 — Discover Clothing Inventory Opportunities
2 — Review One Opportunity End to End
```

Files:

```text
.github/workflows/discovery-v1.2-live-pilot.yml
.github/workflows/v3.7-production-pilot.yml
.github/workflows/tests.yml
```

## Current phase

**Phase:** Operator Workflow Simplification — Wave 2A Prerequisite Audit  
**Current task:** Verify the canonical quality-gate and check-name dependencies required before any duplicated full-regression step or broad pull-request trigger is removed. This task is audit and documentation only.

## Current implementation checkpoint

```text
OPERATOR_WORKFLOW_WAVE2A_PREREQUISITE_AUDIT
```

Status: `NEXT`

Current task document:

```text
docs/OPERATOR_WORKFLOW_WAVE2A_v1.0.md
```

## Knowledge-card phase

Status: `COMPLETE`

All ten scenarios remain complete. No additional Clothing Inventory knowledge card is approved unless a verified gap is found.

## Non-negotiable rules

- Do not delete existing production code.
- Do not modify V2.8–V3.7 financial formulas unless a verified compatibility defect exists.
- Do not add a new domain in this task.
- Do not add a new fixed-source architecture.
- Do not reject a valid discovery merely because analysis data is missing.
- Do not invent missing values.
- Preserve source traceability.
- Do not make an automatic purchase, bid, or contact decision.
- Do not change any workflow trigger, schedule, permission, secret, job, command, environment variable, or artifact during Wave 2A prerequisite audit.
- Do not remove a duplicated `pytest -q` step until `tests.yml` is confirmed as the canonical required quality gate and check-name dependencies are documented.
- Do not change branch protection in this task.

## Definition of current-task success

Wave 2A prerequisite audit succeeds only when:

1. The canonical `tests.yml` workflow name, job name, triggers, artifact, and observed check identity are documented.
2. Pull-request checks that duplicate the complete regression suite are identified.
3. Workflows suitable for the first focused Wave 2 implementation slice are selected.
4. Required check-name and branch-protection dependencies are explicitly marked as confirmed, unconfirmed, or requiring manual repository-settings verification.
5. A rollback and verification bundle is defined for the first Wave 2 implementation PR.
6. No file under `.github/workflows/` is changed.
7. All repository checks pass.

## Immediate next action

Execute Wave 2A prerequisite audit only:

1. inspect `tests.yml` and the Discovery acceptance workflows;
2. document duplicated full-regression steps and current pull-request triggers;
3. identify the safest first implementation slice, grouped by Discovery Engine ownership;
4. record any repository-settings information that cannot be verified from tracked files as `MANUAL_VERIFICATION_REQUIRED`;
5. define exact future path scopes and focused tests without applying them;
6. preserve all workflow behavior;
7. do not begin scheduled-workflow cleanup or historical diagnostic archival.