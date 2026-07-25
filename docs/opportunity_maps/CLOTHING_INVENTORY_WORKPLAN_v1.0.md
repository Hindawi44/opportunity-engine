# Clothing Inventory Opportunity Map — Work Plan v1.0

**Status:** COMPLETE  
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
| 6 | `IMPORTER_CLEARANCE` | COMPLETE |
| 7 | `FACTORY_SURPLUS` | COMPLETE |
| 8 | `BUSINESS_CHANGE` | COMPLETE |
| 9 | `AUCTION` | COMPLETE |
| 10 | `BRANCH_CLOSURE` | COMPLETE |

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

## Completion checkpoint

The Clothing Inventory Opportunity Map is complete.

All ten scenario knowledge cards are approved and merged into `main`.

No additional card may be added unless the end-to-end implementation checkpoint reveals a verified knowledge gap.

## Next approved task

```text
END_TO_END_CLOTHING_INVENTORY_MVP
```

Current task document:

```text
docs/END_TO_END_CLOTHING_INVENTORY_CHECKPOINT_v1.0.md
```

The next task is to prove one complete cycle:

```text
Discovery
  -> Opportunity classification
  -> Opportunity Dossier
  -> Existing Analysis Engine
  -> Final Investment Report or evidence-required outcome
```

No broad query generator, new provider, new domain, or new financial formula is approved before this checkpoint succeeds.
