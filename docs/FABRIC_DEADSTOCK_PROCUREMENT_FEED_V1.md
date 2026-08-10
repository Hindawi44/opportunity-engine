# FABRIC_DEADSTOCK_PROCUREMENT_FEED_V1

## Purpose

Add one bounded procurement-intelligence lane for the operator's tailoring shop.
This lane watches approved official supplier domains for premium deadstock and
bridal fabrics. It does not convert supplier products into clothing-liquidation
opportunities.

The Italy textile expansion now covers three bounded districts inside the same
procurement artifact and unified market-intelligence river: Prato, Como, and
Biella. There is no separate Italy engine, database, lifecycle, workflow, or
daily report.

## Approved sources

Established base sources:

- `evaresource.com` — Italian premium deadstock fabrics.
- `fabrichouse.com` — Italian premium deadstock fabrics and samples.
- `tessutistockprato.it` — Verian, Prato-based wholesale and premium deadstock fabrics.
- `tessutiastock.com` — Eurostock, Prato-based stock fabrics sold in rolls and by the metre.
- `bridalfabrics.com` — specialist bridal lace, tulle, fabrics, trims, and samples.

Bounded district expansion used by the unified daily run:

- `silklabitaly.com` — Como silk and luxury-fabric stock service, including ready stock sold by the metre.
- `texitbiella.com` — Biella wholesale stock fabrics for designers, tailors, retailers, and manufacturers.

Unverified names from brainstorming are not enabled.

## Daily budget

- 7 official-domain Brave queries in the unified daily run.
- 1 query per approved source.
- 8 results requested per source by default.
- At most 5 accepted candidates per source.
- English and Italian search terms for Italian sources.
- No freshness restriction in the unified daily supplier-catalog run. Supplier stock pages are long-lived catalog pages rather than news pages; the official-domain and content gates remain mandatory.
- Existing `BRAVE_SEARCH_API_KEY`; no new secret or provider.

The standalone base collector keeps its original five-source contract and its
freshness argument configurable. The unified daily wrapper adds Como and Biella
for that run only and explicitly uses `freshness=None`, so current supplier
catalog pages are not hidden by a one-month search filter.

## Unified daily integration

The established `build_domain_market_intelligence_feed.py` command remains the
single daily bulletin entrypoint. A bounded CLI hook runs after the base bulletin
has been written and before the existing unified-river projection:

`BASE BULLETIN -> FABRIC PROCUREMENT WATCH -> UNIFIED MARKET INTELLIGENCE RIVER -> COMPARABLES`

The hook writes `fabric-procurement-watch.json` into the same daily output
directory. The existing unified river consumes that artifact and maps accepted
rows to `FABRIC_PROCUREMENT_ITEM` records. Italy therefore enters the same final
intelligence river without becoming a separate engine or changing the canonical
NO/SE/DE opportunity-market completion contract.

## Italian textile district scope

### Prato

Prato remains the broad stock/deadstock lane. It looks for language such as:

- `tessuti a stock`;
- `magazzino`;
- `pronta consegna`;
- `rotoli` / `al metro`;
- `fine pezza` / `fine serie`;
- wool / `lana`, silk / `seta`, linen / `lino`, cotton / `cotone`, lace / `pizzo`, velvet / `velluto`, and mohair.

Accepted Prato candidates carry:

- `source_country: IT`
- `location: Prato, IT`
- `source_kind: PRATO_DEADSTOCK`

### Como

Como is the silk and luxury-fabric lane. The first bounded source is Silk Lab
Italy and targets stock-service language around silk, satin, georgette, crepe de
chine, velvet, viscose, ready stock, and sale by the metre.

Accepted Como candidates carry:

- `source_country: IT`
- `location: Como, IT`
- `source_kind: COMO_SILK_STOCK`

### Biella

Biella is the wool and high-end suiting lane. The first bounded source is Texit
and targets wholesale stock around wool, cashmere, silk, linen, warehouse stock,
and ready availability.

Accepted Biella candidates carry:

- `source_country: IT`
- `location: Biella, IT`
- `source_kind: BIELLA_WOOL_STOCK`

All three districts continue through the same `fabric-procurement-watch.json`
artifact into the unified market-intelligence river.

## Candidate gate

Every result must:

1. use HTTPS;
2. belong to the exact approved supplier domain or its subdomain;
3. contain a recognized English or Italian fabric term;
4. for stock/deadstock suppliers, contain a stock, deadstock, sale, clearance,
   sample, warehouse, ready-stock, roll, metre, or related availability term;
5. for Bridal Fabrics, contain bridal or wedding context.

The watch extracts visible price and currency when present, records fabric and
bridal terms, extracts explicit metre quantities when visible, and assigns a
bounded procurement relevance score.

## Output

The unified daily run writes:

- `fabric-procurement-watch.json`
- `fabric-procurement-watch.txt`
- a compact `fabric_procurement_watch` section in
  `domain-market-intelligence-brief.json`
- a readable section in `domain-market-intelligence-brief.txt`
- fabric procurement items and cases inside the existing unified market-intelligence river artifacts.

The compact bulletin exposes overall candidate count plus separate
`prato_candidate_count`, `como_candidate_count`, and `biella_candidate_count`
values, along with top candidates for each district. Source, location, URL,
visible price/quantity, score, and required operator action remain visible.

## Operator rule

`COMPARE_PRICE_SAMPLE_COMPOSITION_AND_SHIPPING_BEFORE_ORDER`

A result is useful for supplier comparison and sample selection only. Before any
order, the operator must verify:

- exact composition;
- width and weight;
- color and sample;
- available metres;
- minimum order where applicable;
- price and VAT basis;
- shipping, customs, and import cost to Norway;
- return conditions.

## Trust and safety boundary

- no opportunity promotion;
- no Top 5 or financial-analysis eligibility;
- no OpenAI-generated supplier identity;
- no automatic contact;
- no automatic reservation;
- no automatic purchase;
- no automatic payment.

A zero-candidate result is valid and must remain visible as `VALID_ZERO`.
