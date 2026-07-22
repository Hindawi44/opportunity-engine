# Opportunity Engine – Project Audit v1.0

**Audit date:** 22 July 2026  
**Repository:** `Hindawi44/opportunity-engine`  
**Status:** Initial verified audit

## 1. Audit objective

Determine what exists in the current repository, what works, what is incomplete, and what must be completed before the project can produce economically verified opportunities.

## 2. Verified current state

The current GitHub repository is newer than the uploaded Windows v1.0 archive. The repository contains later merged work including:

- Web Discovery Engine v1.
- Reusable Norway source adapter framework.
- Targeted FINN business discovery.
- Official Politiet auction-event discovery.
- Source expansion roadmap and completion tracking.
- Discovery lead normalization, classification, deduplication, ranking, and reporting.
- Daily opportunity snapshots.

## 3. What is already working

- Core Python project structure.
- Opportunity ingestion and normalization.
- Classification and candidate filtering.
- Deduplication.
- Evidence-gated evaluation: missing economic facts remain `null`.
- Daily pipeline and generated snapshots.
- Auksjonen candidate collection.
- Initial FINN-targeted discovery support.
- Official police-auction event discovery.
- Reusable source-adapter architecture.
- Automated tests for several discovery components.

## 4. Most important verified limitation

The program can discover and rank candidates, but it cannot yet prove that a candidate is profitable when the required market and cost data are missing.

Current outputs may correctly use states such as:

- `EVIDENCE_REQUIRED`
- `SEARCH_REQUIRED`
- `REVIEW_REQUIRED`

These states mean that the system found a candidate but lacks enough verified data for a purchase recommendation.

## 5. Data gaps blocking final decisions

The principal remaining gap is data coverage, not a promise or guarantee from the machine. A final economic recommendation requires verified values for:

- Current or final purchase price.
- Auction commission and fees.
- VAT treatment.
- Dismantling cost.
- Transport cost to the user.
- Storage and repair costs.
- Quantity and condition of goods.
- Conservative resale value.
- Sufficient comparable market listings.

No missing value should be replaced by an invented estimate unless it is explicitly labelled as an assumption.

## 6. Difference between the uploaded archive and current GitHub

The uploaded Windows v1.0 archive represents an earlier operational package focused mainly on the local collector, analysis pipeline, database, reports, tests, Windows scripts, and dashboard.

The current GitHub repository has progressed beyond that archive through later source-discovery, source-adapter, FINN, Politiet, web-discovery, ranking, and daily-workflow additions.

Therefore, the GitHub `main` branch is now the technical source of truth. Uploaded archives remain historical release snapshots.

## 7. Preliminary module assessment

| Module | Current audit status | Main remaining issue |
|---|---|---|
| Core project structure | Working | Documentation alignment |
| Auksjonen discovery | Working | Wider and more reliable data extraction |
| FINN discovery | Partial | Authorized and stable data access |
| Politiet discovery | Working at event-lead level | Converting events into item-level opportunities |
| Web Discovery Engine | Implemented v1 | Search-provider configuration and real result coverage |
| Source adapters | Implemented | Add and validate more sources |
| Normalization | Working | Schema consistency across all sources |
| Deduplication | Working | Cross-source identity confidence |
| Evidence engine | Working defensively | Automated comparable evidence collection |
| Economic analysis | Partial | Verified total costs and resale evidence |
| Ranking | Working for prioritization | Must not be confused with proven profitability |
| Notifications | Incomplete | Notify only after quality/evidence gates |
| Dashboard | Existing but not final | Present evidence, uncertainty, and decisions clearly |

## 8. Preliminary completion judgment

The project is not a failed program. It is a functioning opportunity-discovery and candidate-prioritization system with an incomplete economic evidence layer.

The current product should be described as:

> A Norwegian opportunity discovery and evidence-gated review engine.

It should not yet be described as:

> A fully autonomous profitable-opportunity decision engine.

## 9. Critical priority

The next development phase must focus on **data completeness and evidence coverage**, not adding unrelated features.

Priority order:

1. Measure source coverage and identify why searches return zero or too few results.
2. Configure and validate the authorized web search provider within the agreed monthly budget.
3. Collect comparable market evidence and real transaction costs.
4. Complete the economic decision gate.
5. Produce one clear daily user report.

## 10. Audit rules

- No invented market prices.
- No green purchase recommendation without verified economics.
- Ranking strength means review priority, not guaranteed profit.
- GitHub `main` is the current technical source of truth.
- Strategic findings must be recorded in `docs/MASTER_BLUEPRINT.md` or this audit document.

## 11. Next audit checkpoint

Create a verified source-coverage matrix showing, for every configured source:

- Whether it runs.
- Number of searches issued.
- Number of raw results.
- Number normalized.
- Number removed as duplicates.
- Number rejected.
- Number needing evidence.
- Number economically reviewable.
- Errors and reason for zero-result runs.

This matrix is the next required deliverable before further feature development.
