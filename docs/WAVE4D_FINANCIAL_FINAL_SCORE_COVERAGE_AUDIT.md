# Wave 4D — V2.7.2.5 Financial Final-Score Coverage Audit

**Status:** COMPLETE — `NOT_READY`  
**Candidate:** `.github/workflows/v2.7.2.5-external-financial-final-score.yml`  
**Authoritative comparison target:** `.github/workflows/v2.10-verified-financial-integration.yml`

## Decision

```text
NOT_READY
```

The V2.10 implementation is authoritative for verified financial evidence integration and the no-automatic-purchase decision gate. It does not reproduce the complete historical V2.7.2.5 live pipeline, persistence lifecycle, score-generation path, normalization pass, or artifact bundle. Therefore the historical workflow is not yet eligible for a final preservation run or reversible disablement proposal.

## Historical contract

The V2.7.2.5 workflow is manual-only and accepts:

- `opportunity_limit`;
- `research_threshold`;
- `selection_limit`.

It performs:

1. Brave-secret verification;
2. restoration of persistent evidence and investment memory;
3. a live daily-pipeline run;
4. external evidence execution and scenario regeneration;
5. review-queue construction;
6. financial-score and final-investment-score construction;
7. incomplete-economics normalization to `EVIDENCE_REQUIRED`;
8. evidence-persistence auditing;
9. persistent-cache save;
10. upload of a multi-file artifact bundle named `v2.7.3-external-financial-final-score`.

## Coverage matrix

| Material behavior | V2.10 status | Classification | Evidence |
|---|---|---|---|
| Accept only verified market comparables and verified cost evidence | V2.10 validates verified comparables, required cost fields, URLs, and evidence completeness | `COVERED` | `verified_financial_integration.py`; focused V2.10 tests |
| Calculate true acquisition cost, conservative resale value, expected profit, and ROI | Deterministic V2.10 acceptance calculates all four values | `COVERED` | V2.10 workflow, acceptance script, focused tests |
| Block incomplete evidence from financial review | Missing evidence remains null and produces `EVIDENCE_REQUIRED` | `COVERED` | focused V2.10 tests |
| Prohibit automatic purchase decisions | V2.10 always records `automatic_purchase_decision = false` | `COVERED` | implementation and tests |
| Require three verified market comparables | Explicitly tested | `COVERED` | focused V2.10 tests |
| Persist and reload evidence records | Deterministic temporary repository persists and reloads nine evidence records | `PARTIALLY_COVERED` | V2.10 acceptance script |
| Restore and save hosted GitHub Actions cache across runs | V2.10 has no hosted cache lifecycle | `NOT_COVERED` | workflow comparison |
| Execute live daily discovery pipeline | V2.10 uses deterministic fixtures and does not run the live daily pipeline | `NOT_COVERED` | workflow comparison |
| Execute Brave-backed external research and scenario generation | V2.10 does not call the historical external execution audit | `NOT_COVERED` | workflow comparison |
| Build the historical opportunity review queue | V2.10 does not build `data/opportunity_review_queue.json` | `NOT_COVERED` | workflow comparison |
| Build historical `economic_evaluation_queue.json` and `scored_opportunities.json` | V2.10 returns a verified financial decision, not the historical score pipeline | `NOT_COVERED` | script and workflow comparison |
| Normalize incomplete recommendations in historical score and summary files | V2.10 enforces `EVIDENCE_REQUIRED` in its decision gate, but does not run the historical normalization script or mutate those files | `PARTIALLY_COVERED` | implementation comparison |
| Preserve the historical artifact name and complete multi-file bundle | V2.10 uploads one deterministic summary only | `NOT_COVERED` | workflow comparison |
| Secret non-disclosure | No secret is printed by either tracked workflow; hosted execution details remain external | `MANUAL_VERIFICATION_REQUIRED` | tracked files only |
| Branch protection, dashboards, APIs, operators, and historical links | Not verifiable from tracked repository files | `MANUAL_VERIFICATION_REQUIRED` | external facts |

## Unique historical behavior

The following V2.7.2.5 behaviors remain unique and materially outside V2.10 coverage:

- live opportunity acquisition through `run_daily_pipeline.py`;
- Brave-backed external evidence generation;
- persistent GitHub Actions cache restoration and save;
- review-queue generation;
- historical economic-evaluation and final-score file generation;
- post-processing through `normalize_incomplete_recommendations.py`;
- persistence-baseline and final persistence-audit outputs;
- the complete artifact contract containing validation files, snapshots, queues, scored opportunities, investment files, and evidence files.

These gaps do not invalidate V2.10 as the authoritative current financial decision gate. They prevent claiming equivalent end-to-end coverage for the historical diagnostic.

## Required work before reconsideration

A later task may reconsider readiness only after one of the following is approved and demonstrated:

1. current tests or a current acceptance workflow reproduce the unique historical behaviors; or
2. an explicit compatibility decision narrows the preservation requirement and accepts that those behaviors are historical-only.

Until then, do not request a final preservation run and do not modify, disable, rename, relocate, archive, or delete the historical workflow.

## Future final-run evidence bundle

If the candidate later becomes ready, the final manual run must preserve:

- run ID, run number, URL, triggering actor, branch, commit SHA, start/end timestamps, duration, status, workflow name, and job name;
- workflow-file SHA at the executed commit;
- input values for all three dispatch inputs;
- artifact ID, artifact name, size, expiry, and GitHub-provided digest;
- downloaded archive SHA-256 and complete archive inventory;
- daily-pipeline output;
- external-execution output;
- financial/final-score summary;
- persistence baseline and final persistence audit;
- opportunity snapshot, review queue, evidence payload, economic evaluation queue, scored opportunities, investment files, and evidence directory;
- proof that no secret value was disclosed;
- explicit recording of unresolved external consumers and repository settings as `MANUAL_VERIFICATION_REQUIRED`.

## Rollback approach

Wave 4D changes documentation only. Rollback is a single revert of the audit PR. The historical workflow remains unchanged and operationally available through `workflow_dispatch`.

## Prohibited follow-up

This audit does not authorize a preservation run, disablement, archival, rename, relocation, deletion, production-code change, financial-formula change, threshold change, domain expansion, or automatic purchase/contact behavior.
