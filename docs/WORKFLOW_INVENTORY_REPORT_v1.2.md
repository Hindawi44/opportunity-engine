# Workflow Inventory Report v1.2

**Scope:** every `.yml` and `.yaml` file currently under `.github/workflows/`  
**Inventory date:** 2026-08-02  
**Workflow files represented:** 37  
**Change note:** the manual three-market operator checkpoint, the Germany Clothing Inventory open-web pilot, and the daily Riegermann, VENTA, and Deutsche Pfandverwertung watches are represented; no existing workflow was deleted or disabled.

## Operator surface

The principal general discovery workflow remains:

- `1 — Discover Clothing Inventory Opportunities`

The end-to-end review workflow remains:

- `2 — Review One Opportunity End to End`

`Multi-Market Daily Operator Checkpoint` is a manual, read-only supporting workflow. It runs bounded existing paths for Norway (`Auksjonen.no`), Sweden (`Blinto`), and Germany (`Riegermann`, `VENTA`, and `Deutsche Pfandverwertung`), then emits one structured report and one phone-readable summary. It distinguishes source failure from a valid zero result, deduplicates identities, reconciles JSON and SQLite counts where persistence is enabled, and selects no more than one human action.

The Sweden and Germany pilots are bounded geographic-expansion workflows. They reuse the existing discovery, public-page verification, lifecycle classification, unified reporting, SQLite persistence, and safety contracts.

The Germany open-web mode remains available. The source-specific Riegermann workflow reads the public active-auction index, selects only auctions with explicit clothing evidence, and delegates their exact catalog and information pages to the bounded Riegermann adapter. It runs daily at `05:17 UTC` and remains available through manual dispatch.

The VENTA watch reads the public auction index, inspects every selected active catalog instead of trusting the company name, completes bounded public pagination, and emits a parent auction lead only when the catalog heading or lot titles provide explicit clothing evidence. It runs daily at `05:47 UTC`, remains manually dispatchable, and treats zero clothing results as valid. VENTA remains `PLANNED` until a live clothing catalog and exact bulk item-page verification are validated.

The Deutsche Pfandverwertung watch reads the public catalog overview, completes bounded catalog pagination, verifies explicit bulk clothing lots on exact public item pages, and keeps source-native EUR amounts out of normalized price fields. It runs daily at `06:17 UTC`, remains manually dispatchable, and treats a zero-active-catalog result as valid. The source remains `PLANNED` until a current live clothing catalog validates the complete main-branch watch and persistence path.

None of these workflows contacts sellers, bids, buys, pays, or estimates unsupported FX, VAT, customs, logistics, profit, or ROI values. A zero-result run remains a valid, reportable outcome.

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
35. `.github/workflows/riegermann-active-auctions-live.yaml`
36. `.github/workflows/sweden-clothing-inventory-live.yaml`
37. `.github/workflows/venta-active-clothing-watch.yaml`

## Classification summary

- `PRIMARY_DISCOVERY_CANDIDATE`: the existing general discovery workflow.
- `END_TO_END_REVIEW_CANDIDATE`: the existing V3.7 review workflow.
- `MULTI_MARKET_OPERATOR_CHECKPOINT`: the manual read-only NO/SE/DE consolidation workflow.
- `GEOGRAPHIC_DISCOVERY_PILOT`: Sweden live pilot, Germany open-web pilot, bounded Riegermann active-auction workflow, VENTA active-catalog watch, and Deutsche Pfandverwertung active-catalog watch.
- All other classifications remain as documented in v1.0.

## Multi-market checkpoint controls

The checkpoint enforces:

- exactly the completed market foundations `NO`, `SE`, and `DE`;
- source-native currencies `NOK`, `SEK`, and `EUR`;
- no undocumented foreign-currency value in `price_nok` or `bid_price_nok`;
- source failure distinct from a valid zero-result run;
- active, upcoming, historical, ended, and unresolved counts;
- cross-source identity deduplication;
- JSON and SQLite count reconciliation where persistence is enabled;
- no more than one immediate human action;
- manual dispatch only, with no schedule;
- no contact, bid, purchase, reservation, payment, or other external action.

## Germany pilot controls

The Germany workflows enforce:

- market identity `DE`;
- report and persistence currency `EUR`;
- source modes `OPEN_WEB`, `RIEGERMANN`, `RIEGERMANN_ACTIVE`, `VENTA_ACTIVE_WATCH`, and `DPV_ACTIVE_WATCH`;
- exact public Riegermann, VENTA, and Deutsche Pfandverwertung index, catalog, pagination, and item URL contracts;
- explicit clothing evidence before an auction event is emitted;
- company names, brand rights, and zero-count category labels are not clothing inventory evidence;
- ordinary single garments remain child evidence instead of standalone opportunities;
- VENTA bulk lots remain blocked until exact item-page verification;
- Deutsche Pfandverwertung bulk lots are exactly verified but remain blocked from promotion while the source is `PLANNED`;
- source-native EUR observations do not enter normalized price or NOK fields;
- no use of `price_nok` or `bid_price_nok` for German records;
- valid JSON, unified report, SQLite, and historical evidence artifacts even when no opportunity is found.

## Integrity statement

This report represents all 37 workflow files, including both supported filename extensions. The Sweden and Germany open-web workflows and the multi-market checkpoint remain manual. Riegermann runs daily at `05:17 UTC`, VENTA at `05:47 UTC`, and Deutsche Pfandverwertung at `06:17 UTC`; all three watches remain manually dispatchable and preserve the existing evidence and safety gates. Existing eligibility gates, source-access statuses, financial formulas, and automatic-action prohibitions remain unchanged.
