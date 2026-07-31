# Textile & Sewing Opportunity Taxonomy V1

## Purpose

This contract expands discovery within the clothing, textile, tailoring, and
sewing ecosystem without turning `opportunity-engine` into a generic
liquidation search engine.

The taxonomy is a detached classification boundary. It does not change the
opportunity lifecycle, economic scoring, ranking, Top 5, alerts, persistence,
or purchase decisions.

## Stable categories

Primary categories:

- `SMALL_CLOTHING_STORE_LIQUIDATION`
- `CLOTHING_CHAIN_OR_BRANCH_CLOSURE`
- `BRAND_INVENTORY_LIQUIDATION`
- `CLOTHING_INVENTORY`
- `SHOES_BAGS_ACCESSORIES_INVENTORY`
- `FABRIC_TEXTILE_STOCK`
- `TAILOR_WORKSHOP_LIQUIDATION`
- `SEWING_ATELIER_LIQUIDATION`
- `SEWING_FACTORY_LIQUIDATION`
- `SEWING_MACHINERY`
- `HABERDASHERY_AND_NOTIONS`

Secondary category:

- `CLOTHING_STORE_FIXTURES`

Fixtures qualify only when the public text explicitly connects them to a
clothing, textile, tailoring, or sewing business.

## Signal model

Classification records four separate evidence groups:

1. Commercial event signals such as bankruptcy, closure, liquidation, auction,
   surplus, and sale.
2. Business-sector signals such as clothing shop, chain, tailor workshop,
   sewing atelier, and garment factory.
3. Inventory or equipment signals such as clothing stock, fabric rolls,
   industrial sewing machines, notions, and shop fixtures.
4. Unrelated-sector rejection signals such as kitchen production, construction,
   school storage, vehicle workshops, agriculture, and generic warehouse racks.

A broad term such as `varelager` or `auksjon` never qualifies a candidate by
itself.

## Audit output

`build_textile_taxonomy_audit` accepts public candidate objects and produces:

- included and rejected counts;
- category counts;
- one decision per candidate;
- matched signals and rejection reasons;
- a valid zero-candidate result;
- explicit safety flags confirming that other engines are unchanged.

The CLI can build an audit from a JSON list, a single candidate object, or an
object containing `candidates`, `results`, or `opportunities`:

```bash
PYTHONPATH=src python scripts/build_textile_taxonomy_audit.py \
  --input data/discovery_leads.json \
  --output data/textile_taxonomy_audit_v1.json
```

## Conservative behavior

- Missing public text fails closed.
- Ordinary retail pages and discount campaigns are out of scope.
- Generic inventory, shelving, kitchen, furniture, school, vehicle, and
  agricultural listings remain out of scope without explicit textile evidence.
- Mixed listings retain unrelated co-signals for human review rather than
  silently hiding them.
- No automatic contact, bidding, or purchase is enabled.

## Next step

After this taxonomy is merged, the next implementation step is the Norway
keyword-pack upgrade. It should replace broad standalone queries with structured
combinations of:

```text
commercial event + business sector + inventory or equipment
```

Sweden and Denmark market profiles and keyword packs follow only after the
Norway mapping is validated against real candidates.
