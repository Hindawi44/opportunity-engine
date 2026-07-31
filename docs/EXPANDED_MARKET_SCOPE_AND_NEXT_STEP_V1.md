# Expanded Market Scope and Next Step V1

## Decision

`opportunity-engine` will remain a focused opportunity-intelligence system for the clothing, textile, tailoring, and sewing ecosystem. The project will expand in two coordinated directions:

1. Geographic expansion beyond Norway.
2. Sector expansion within the same commercial ecosystem.

The project will not become a generic inventory, machinery, or liquidation search engine.

## Updated product objective

Discover, track, verify, and qualify liquidation, bankruptcy, closure, surplus-stock, and inventory-sale opportunities connected to:

- clothing retailers and boutiques;
- clothing chains and branch closures;
- branded clothing inventory;
- shoes, bags, accessories, and related retail stock;
- fabric, textile rolls, remnants, and haberdashery;
- tailor shops, sewing ateliers, and alteration workshops;
- garment-production workshops and factories;
- industrial sewing machines and textile-production equipment;
- sewing notions and supplies;
- clothing-store fixtures when their sector connection is explicit.

Each opportunity must ultimately be evaluated for Mahmoud / Namsos using verified sale status, quantity, price, fees, VAT, transport, handling, import costs where applicable, conservative resale value, expected profit, and risk.

## Geographic expansion order

1. Norway
2. Sweden
3. Denmark
4. Finland
5. Germany and wider Europe after Nordic validation

Each market profile must define:

- local language and terminology;
- local liquidation and bankruptcy event terms;
- relevant source types;
- currency and conversion to NOK;
- VAT and import assumptions;
- transport to Namsos;
- market-specific risks;
- qualification rules.

## Opportunity taxonomy

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

The secondary category is eligible only when the listing is explicitly connected to a clothing, textile, tailoring, or sewing business.

## Search design

Search must not depend on one broad term such as `varelager`.

Queries should combine three signal groups:

1. Commercial event signal
2. Business-sector signal
3. Inventory or equipment signal

Conceptual pattern:

```text
commercial event + business sector + stock/equipment
```

Examples:

```text
konkurs + klesbutikk + varelager
avvikling + systue + industrisymaskiner
opphør + stoffbutikk + stofflager
butikk stenger + klær + hele varelageret
konkurs + kleskjede + lager
```

Keyword packs must evolve by:

- language;
- country;
- opportunity category;
- source type;
- false-positive history;
- discovered local terminology.

## Small businesses and known brands

Both are in scope.

### Small shop or workshop

Usually offers faster direct contact, negotiable terms, smaller quantities, and potentially better fit for Mahmoud.

### Known chain or brand

Often begins as an early news signal and may later become a public sale, auction, estate-manager sale, or warehouse liquidation.

The system must preserve the difference between:

- a closure announcement;
- evidence that stock exists;
- an active public or private sale channel;
- a fully qualified purchase opportunity.

## Opportunity lifecycle

```text
EARLY_SIGNAL
→ CANDIDATE
→ REQUIRES_VERIFICATION
→ ACTIVE_OPPORTUNITY
→ QUALIFIED_OPPORTUNITY
→ CLOSED / REJECTED
```

Examples:

- Store closure news: `EARLY_SIGNAL`
- Inventory is reported to exist: `CANDIDATE`
- Quantity, price, or sale channel is missing: `REQUIRES_VERIFICATION`
- Active listing or verified seller channel exists: `ACTIVE_OPPORTUNITY`
- Economics and risk are acceptable: `QUALIFIED_OPPORTUNITY`

## Out of scope

Unless there is explicit textile-sector evidence:

- kitchen inventory;
- construction materials;
- general office furniture;
- school storage equipment;
- generic warehouse shelving;
- vehicle workshops;
- agricultural machinery;
- unrelated industrial equipment.

A generic liquidation or inventory term is never sufficient on its own.

## Current validation lesson

The current engine has demonstrated that it can run the live workflow, preserve zero-result reporting, reject unverified opportunities, and avoid false positive alerts. The latest Norway-only live run did not produce a qualified clothing opportunity. This does not invalidate the product idea; it shows that the available opportunity supply is insufficient for a fair commercial test.

The correct response is to increase relevant opportunity supply by expanding geography, sources, terminology, and in-sector categories while preserving strict evidence gates.

## Immediate next implementation step

### Textile & Sewing Opportunity Taxonomy V1

Build the canonical in-sector taxonomy before adding Sweden or Denmark sources.

The implementation should:

1. Define the primary and secondary categories above as stable machine-readable values.
2. Map current Norway terms and source results into those categories.
3. Separate commercial-event signals from sector and inventory signals.
4. Add explicit unrelated-sector rejection rules.
5. Preserve valid zero-result runs.
6. Preserve lifecycle, evidence, scoring, Top 5, alerts, and persistence behavior.
7. Add fixtures for clothing stock, fabric stock, tailor-workshop liquidation, sewing machinery, a clothing-chain closure, and unrelated general inventory.
8. Produce a category audit explaining why each candidate was included or rejected.

## Next sequence after taxonomy

1. Norway keyword pack upgrade
2. Sweden market profile and Swedish keyword pack
3. Swedish source integration
4. Denmark market profile and Danish keyword pack
5. Danish source integration
6. Multi-country live validation
7. Landed-cost comparison to Namsos
8. Operator workflow and product interface

## Validation target

A meaningful market test requires enough relevant supply, not merely a technically successful run.

Target funnel:

```text
30–50 relevant early signals
→ 10 clear textile/clothing inventory candidates
→ 5 active contactable opportunities
→ 2–3 opportunities with verified price and transport inputs
→ at least 1 negotiation or purchase decision
```

The project should not claim commercial validation before this funnel is observed with real data.
