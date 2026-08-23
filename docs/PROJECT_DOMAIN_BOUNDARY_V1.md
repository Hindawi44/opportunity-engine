# PROJECT DOMAIN BOUNDARY V1

## Purpose

Restore the project scope before any further learning, source promotion, exact-lot qualification, or commercial analysis.

The authoritative commercial scope is:

- `CLOTHING_INVENTORY` — clothing, fashion, apparel, footwear and bridal garments when they are part of a commercial stock/liquidation opportunity;
- `FABRIC_PROCUREMENT` — fabric/textile stock in the existing bounded procurement lane.

Unrelated goods such as building materials, appliances and general merchandise are `OUT_OF_DOMAIN`.

## Required boundary

The same deterministic project-domain gate must be applied before:

1. external ground-truth cases can train source learning;
2. a promoted broad source can emit a production candidate;
3. a promoted learned query can emit a canonical opportunity;
4. Exa exact-lot verification can classify an item as an exact-lot candidate.

## Safety and architecture

- No automatic contact, bid, reservation, purchase or payment.
- No automatic source or query promotion.
- Out-of-domain evidence may be counted for diagnostics but must not train or enter commercial qualification.
- Fabric procurement remains a separate bounded lane; the canonical learned Core opportunity path remains clothing-inventory scoped.
- The repair does not add a workflow, provider, market or financial formula.

## Test-first rule

`tests/test_project_domain_boundary_v1.py` defines the RED contract before implementation.
