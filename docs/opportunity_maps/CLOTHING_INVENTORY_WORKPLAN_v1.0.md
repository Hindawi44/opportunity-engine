# Clothing Inventory Opportunity Map — Work Plan v1.0

**Status:** ACTIVE  
**Development method:** One scenario at a time

## Objective

Build a complete, testable knowledge map explaining how Clothing Inventory opportunities appear in the real Norwegian market before adding broad automation.

## Scenario order

| Order | Scenario | Status |
|---:|---|---|
| 1 | `STORE_CLOSING` | COMPLETE |
| 2 | `BANKRUPTCY` | COMPLETE |
| 3 | `INVENTORY_LIQUIDATION` | COMPLETE |
| 4 | `LARGE_LOT` | COMPLETE |
| 5 | `WAREHOUSE_SURPLUS` | COMPLETE |
| 6 | `IMPORTER_CLEARANCE` | READY FOR REVIEW |
| 7 | `FACTORY_SURPLUS` | NOT STARTED |
| 8 | `BUSINESS_CHANGE` | NOT STARTED |
| 9 | `AUCTION` | NOT STARTED |
| 10 | `BRANCH_CLOSURE` | NOT STARTED |

## Required knowledge card for each scenario

Each scenario is complete only when its card defines:

1. **Real-world event** — what is happening commercially.
2. **Seller motivation** — why inventory becomes available.
3. **Opportunity forms** — complete stock, partial stock, mixed lot, auction, contact lead, etc.
4. **Norwegian language signals** — strong, medium, and weak signals.
5. **Context combinations** — which signals together indicate a real commercial opportunity.
6. **False positives** — ordinary discounts, single garments, services, jobs, expired pages, and unrelated news.
7. **Likely publication channels** — described as channels, not governing sources.
8. **Minimum discovery data** — facts needed to preserve the candidate.
9. **Possible missing data** — fields that must remain unknown rather than causing rejection.
10. **Dossier evidence targets** — text, images, attachments, company records, sale terms, inventory evidence.
11. **Qualification outcomes** — confirmed sale, contact required, rejected, expired.
12. **Example fixtures** — positive, ambiguous, negative, and duplicate examples.
13. **Acceptance tests** — observable rules that code can later implement.

## Completion rule

After one card is approved:

1. Mark it complete in this work plan.
2. Update `docs/00_PROJECT_STATUS.md`.
3. Set exactly one next scenario.
4. Commit the checkpoint before beginning another scenario.

## Current task

Review and approve:

```text
docs/opportunity_maps/IMPORTER_CLEARANCE_KNOWLEDGE_CARD_v1.0.md
```

No broad query generator, new provider, market valuation, or financial code is part of this task.

After merge, `FACTORY_SURPLUS` becomes the only next scenario.
