# Workflow Inventory Report v1.3

**Scope:** every `.yml` and `.yaml` file currently under `.github/workflows/`  
**Inventory date:** 2026-08-03  
**Workflow files represented:** 38  
**Change note:** adds the dedicated manual One Opportunity Commercial Analysis workflow; no existing workflow was deleted or disabled.

## Current-surface addendum — 2026-08-20

The historical v1.3 snapshot below remains at 38 represented workflows. The current live Actions surface additionally contains the manual-only MIND FORGE launcher:

- `.github/workflows/mind-forge-live-research-launcher.yaml`

This launcher has no automatic schedule and does not change ownership of the Multi-Market Daily Operator Checkpoint schedule.

## Operator surface

The principal general discovery workflow remains:

- `1 — Discover Clothing Inventory Opportunities`

The end-to-end review workflow remains:

- `2 — Review One Opportunity End to End`

`Multi-Market Daily Operator Checkpoint` remains the manual read-only NO/SE/DE consolidation workflow and is classified as `MULTI_MARKET_OPERATOR_CHECKPOINT`. It runs bounded Norway, Sweden, and Germany source paths, restores lifecycle SQLite state, emits one daily checkpoint, and selects no more than one human action.

`One Opportunity Commercial Analysis` is a separate manual read-only workflow classified as `ONE_OPPORTUNITY_COMMERCIAL_ANALYSIS`. It downloads the newest successful checkpoint artifact, requires an exact selected-opportunity identity match, accepts explicit commercial inputs, and invokes the existing conservative financial decision engine. It does not collect new opportunities and never contacts sellers, bids, buys, pays, reserves, or transfers funds.

The Germany Clothing Inventory open-web pilot, the Riegermann active-auction workflow, the VENTA active-catalog watch, and the Deutsche Pfandverwertung watch remain represented. A zero-result run remains a valid, reportable outcome.

## Complete file inventory

1. `.github/workflows/daily-opportunity-pipeline.yml`
2. `.github/workflows/discovery-v1-clothing-inventory.yml`
3. `.github/workflows/discovery-v1.1-live-search.yml`
4. `.github/workflows/discovery-v1.2-live-pilot.yml`
5. `.github/workflows/scheduled-agent.yml`
6. `.github/workflows/tests.yml`
7. `.github/workflows/v2.10-verified-financial-integration.yml`
8. `.github/workflows/v2.11-live-opportunity-validation.yml`
9. `.github/workflows/v2.6.6-live-dry-run.yml`
10. `.github/workflows/v2.7.1-real-dataset-validation.yml`
11. `.github/workflows/v2.7.2.2-internal-score-audit.yml`
12. `.github/workflows/v2.7.2.3-score-engine-trace-audit.yml`
13. `.github/workflows/v2.7.2.4.1-research-candidate-audit.yml`
14. `.github/workflows/v2.7.2.4.2-bootstrap-pipeline-integration.yml`
15. `.github/workflows/v2.7.2.4.3-external-evidence-execution-audit.yml`
16. `.github/workflows/v2.7.2.4.4-brave-transport-response-audit.yml`
17. `.github/workflows/v2.7.2.4.5-brave-response-content-audit.yml`
18. `.github/workflows/v2.7.2.4.7-comparable-acceptance-audit.yml`
19. `.github/workflows/v2.7.2.5-external-financial-final-score.yml`
20. `.github/workflows/v2.8.1-external-market-comparables.yml`
21. `.github/workflows/v2.8.2-comparable-evidence-integration.yml`
22. `.github/workflows/v2.8.2b-comparable-evidence-e2e-acceptance.yml`
23. `.github/workflows/v2.9-auction-cost-logistics-e2e.yml`
24. `.github/workflows/v30-multi-opportunity-ranking.yml`
25. `.github/workflows/v31-live-batch-validation.yml`
26. `.github/workflows/v3.2-continuous-opportunity-monitoring.yml`
27. `.github/workflows/v3.3-live-source-ingestion.yml`
28. `.github/workflows/v3.4-persistent-opportunity-state.yml`
29. `.github/workflows/v3.5-opportunity-alert-review-queue.yml`
30. `.github/workflows/v3.6-multi-source-ingestion.yml`
31. `.github/workflows/v3.7-production-pilot.yml`
32. `.github/workflows/dpv-active-clothing-watch.yaml`
33. `.github/workflows/germany-clothing-inventory-live.yaml`
34. `.github/workflows/multi-market-daily-operator-checkpoint.yaml`
35. `.github/workflows/one-opportunity-commercial-analysis.yaml`
36. `.github/workflows/riegermann-active-auctions-live.yaml`
37. `.github/workflows/sweden-clothing-inventory-live.yaml`
38. `.github/workflows/venta-active-clothing-watch.yaml`

## Classification summary

- `PRIMARY_DISCOVERY_CANDIDATE`: the existing general discovery workflow.
- `END_TO_END_REVIEW_CANDIDATE`: the existing V3.7 review workflow.
- `MULTI_MARKET_OPERATOR_CHECKPOINT`: the manual read-only NO/SE/DE consolidation workflow.
- `ONE_OPPORTUNITY_COMMERCIAL_ANALYSIS`: manual analysis of exactly one selected active opportunity using explicit human inputs.
- `GEOGRAPHIC_DISCOVERY_PILOT`: Sweden live pilot, Germany open-web pilot, bounded Riegermann active-auction workflow, VENTA active-catalog watch, and Deutsche Pfandverwertung active-catalog watch.
- All other classifications remain as documented in v1.0 through v1.2.

## Commercial-analysis controls

The new workflow enforces:

- exact opportunity identity matching against the newest successful checkpoint artifact;
- explicit confirmation of quantity and condition;
- explicit final payable price including auction fees and VAT;
- explicit pickup or transport amount in NOK;
- explicit conservative resale value and documented-comparable count;
- no assumption that a source price of zero is a real purchase price;
- output of total cost, expected profit, ROI, confidence, and maximum final payable price;
- no maximum source bid without a separately documented auction fee and VAT formula;
- no automatic contact, bid, purchase, reservation, or payment.

## Germany pilot controls

The Germany workflows continue to enforce market identity `DE`, source and report currency `EUR`, and no use of `price_nok` or `bid_price_nok` for German records. Source-native values remain separate from unsupported NOK conversions.

## Integrity statement

This report preserves the historical 38-workflow snapshot and records the current manual-only MIND FORGE launcher in the addendum above. The Sweden and Germany open-web workflows, the multi-market checkpoint, and the one-opportunity commercial analysis remain manually dispatchable where specified. Existing eligibility gates, source-access statuses, financial formulas, lifecycle state, and automatic-action prohibitions remain unchanged.
