# Clothing Inventory Discovery Operator Integration v1.0

**Task:** `CLOTHING_INVENTORY_DISCOVERY_OPERATOR_INTEGRATION`  
**Domain:** `CLOTHING_INVENTORY` only  
**Status:** Implemented in this pull request  
**Automatic commercial action:** Prohibited

## Purpose

Expose the merged structured Clothing Inventory Discovery search through the existing manual operator workflow:

```text
1 — Discover Clothing Inventory Opportunities
```

The operator must be able to select one independent operation:

```text
brave_discovery
active_clothing_scan
structured_clothing_discovery
```

The new operation runs:

```text
scripts/run_clothing_inventory_discovery_search.py
```

with the repository secret:

```text
BRAVE_SEARCH_API_KEY
```

and public-page verification enabled.

## Exact output contract

The operation writes and uploads:

```text
artifacts/clothing-inventory-discovery/
├── search-run-report.json
├── all-discovered-candidates.json
├── discovery-top5.json
└── operator-summary.txt
```

The workflow prints `operator-summary.txt` for phone review and fails when the required summary or artifact directory is absent.

## Boundaries

This task does not:

- add a schedule;
- run automatically;
- modify the Analysis Engine;
- calculate ROI, expected profit, or maximum bid;
- create `BUY_REVIEW`, `WATCH`, or investment `REJECT` decisions;
- contact a seller;
- bid, reserve, purchase, or pay;
- merge PR #309;
- add another opportunity domain.

## Acceptance criteria

1. The operator workflow exposes exactly three choices.
2. Each choice selects exactly one mutually exclusive job.
3. The new job receives `BRAVE_SEARCH_API_KEY` only from GitHub Secrets.
4. The new job runs the structured search with `--verify-pages`.
5. The four discovery artifacts are uploaded together.
6. The operator summary is printed even when later steps fail.
7. Focused tests cover the workflow contract and commercial-safety separation.
8. The existing review workflow remains separate.
9. No automatic commercial action is introduced.

## Immediate next action after merge

Run the workflow manually with:

```text
operation = structured_clothing_discovery
```

Then inspect `discovery-top5.json`. The strongest traceable active result may proceed to the existing Opportunity Dossier boundary.
