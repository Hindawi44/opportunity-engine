# Norway Textile Keyword Pack V1

## Purpose

Expand Norwegian discovery supply without turning `opportunity-engine` into a
generic liquidation search engine.

The pack remains limited to the clothing, textile, tailoring, and sewing
ecosystem. It covers all categories defined by `Textile & Sewing Opportunity
Taxonomy V1`.

## Query contract

The pack contains 16 bounded queries. Every query records:

- a stable query ID;
- commercial scenario;
- intent;
- intended taxonomy category;
- commercial-event term;
- business-sector term;
- inventory or equipment term;
- rotation group;
- rendered public query.

Conceptual rule:

```text
commercial event + business sector + inventory/equipment + Norway
```

Examples:

```text
klesbutikk + varelager + selges
stoffruller + restlager + selges
industrisymaskiner + tekstilbedrift + auksjon
skredderverksted + utstyr + konkursbo
kleskjede + filial stenger + varelager
systue + avvikling + utstyr
butikkinnredning + klesbutikk + selges
```

## Covered opportunity categories

- small clothing-store liquidation;
- clothing-chain or branch closure;
- branded clothing inventory;
- clothing inventory;
- shoes, bags, and accessories inventory;
- fabric and textile stock;
- tailor-workshop liquidation;
- sewing-atelier liquidation;
- sewing-factory liquidation;
- sewing machinery;
- haberdashery and sewing notions;
- clothing-store fixtures with explicit clothing context.

## Norway-specific vocabulary adapter

The canonical taxonomy remains market-neutral. A conservative Norway adapter
recognizes three explicit local-language patterns that need market context:

1. `klesbutikk + varelager + direct sale`;
2. `kleskjede/butikkjede + closure`;
3. `klesmerke/merkevarer + inventory event`.

The adapter does not convert a generic liquidation into textile scope.

## Filtering and classification

The discovery filter now retains both:

- public sale candidates; and
- relevant early signals such as bankruptcy, closure, and liquidation.

The classifier emits the taxonomy category on every retained result. A closure
without a verified sale channel remains `CONTACT_REQUIRED`; it is never upgraded
to a confirmed sale merely because the business is closing.

Unrelated kitchen, construction, school-storage, vehicle-workshop,
agricultural, and generic warehouse inventory remains out of scope.

## Live pilot

Run manually with a configured Brave Search API key:

```bash
PYTHONPATH=src python scripts/run_norway_textile_discovery_pilot.py
```

Outputs:

```text
artifacts/norway-textile-discovery-report.json
artifacts/norway-textile-discovery-phone-report.txt
```

The pilot does not automatically open pages, contact sellers, bid, purchase, or
pay.

## Scope boundary

This V1 integrates the pack with the general live Discovery path. It does not yet
replace the older 16-query source-targeted Clothing Inventory contract used by
the strict page-verification pilot. That production-path migration must be a
separate change so URL gates, Playwright fallback, Top 5, and existing fixtures
remain stable.

## Next implementation step

Connect the Norway textile categories to the strict source-targeted retrieval and
bounded public-page verification path, preserving:

- source diversity;
- URL and page-role gates;
- active/ended detection;
- deduplication;
- Top 5 hard gate;
- zero-result safety;
- no automatic external action.
