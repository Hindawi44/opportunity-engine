# FABRIC_DEADSTOCK_PROCUREMENT_FEED_V1

## Purpose

Add one bounded procurement-intelligence lane for the operator's tailoring shop.
This lane watches approved official supplier domains for premium deadstock and
bridal fabrics. It does not convert supplier products into clothing-liquidation
opportunities.

The Italy expansion starts with one bounded target: the Prato textile district.
Prato sources feed the same existing procurement artifact and unified market
intelligence river; there is no separate Italy engine, database, lifecycle, or
daily report.

## Approved sources

- `evaresource.com` — Italian premium deadstock fabrics.
- `fabrichouse.com` — Italian premium deadstock fabrics and samples.
- `tessutistockprato.it` — Verian, Prato-based wholesale and premium deadstock fabrics.
- `tessutiastock.com` — Eurostock, Prato-based stock fabrics sold in rolls and by the metre.
- `bridalfabrics.com` — specialist bridal lace, tulle, fabrics, trims, and samples.

Unverified names from brainstorming are not enabled.

## Daily budget

- 5 official-domain Brave queries.
- 1 query per approved source.
- 8 results requested per source by default.
- At most 5 accepted candidates per source.
- English and Italian search terms for Italian sources.
- No freshness restriction in the unified daily supplier-catalog run. Supplier stock pages are long-lived catalog pages rather than news pages; the official-domain and content gates remain mandatory.
- Existing `BRAVE_SEARCH_API_KEY`; no new secret or provider.

The standalone collector keeps its freshness argument configurable. The unified
daily CLI hook explicitly uses `freshness=None` so current supplier catalog pages
are not hidden by a one-month search filter.

## Unified daily integration

The established `build_domain_market_intelligence_feed.py` command remains the
single daily bulletin entrypoint. A bounded CLI hook runs after the base bulletin
has been written and before the existing unified-river projection:

`BASE BULLETIN -> FABRIC PROCUREMENT WATCH -> UNIFIED MARKET INTELLIGENCE RIVER -> COMPARABLES`

The hook writes `fabric-procurement-watch.json` into the same daily output
directory. The existing unified river already consumes that artifact and maps its
accepted rows to `FABRIC_PROCUREMENT_ITEM` records. Italy therefore enters the
same final intelligence river without becoming a separate engine or changing the
canonical NO/SE/DE opportunity-market completion contract.

## Prato scope

The first Italy target is intentionally narrow. It looks for textile stock and
deadstock language such as:

- `tessuti a stock`;
- `magazzino`;
- `pronta consegna`;
- `rotoli` / `al metro`;
- `fine pezza` / `fine serie`;
- wool / `lana`, silk / `seta`, linen / `lino`, cotton / `cotone`, lace / `pizzo`, velvet / `velluto`, and mohair.

Accepted Prato candidates carry `source_country: IT`, `location: Prato, IT`, and
`source_kind: PRATO_DEADSTOCK`, then continue through the existing
`fabric-procurement-watch.json` input to the unified market-intelligence river.

## Candidate gate

Every result must:

1. use HTTPS;
2. belong to the exact approved supplier domain or its subdomain;
3. contain a recognized English or Italian fabric term;
4. for deadstock suppliers, contain a stock, deadstock, sale, clearance, deal,
   sample, new-arrival, warehouse, ready-stock, roll, or end-of-series term;
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

The compact bulletin exposes the overall candidate count, the Prato candidate
count, up to five highest-scoring procurement candidates, and up to five Prato
candidates with source, location, URL, visible price/quantity, score, and the
required operator action.

## Operator rule

`COMPARE_PRICE_SAMPLE_COMPOSITION_AND_SHIPPING_BEFORE_ORDER`

A result is useful for supplier comparison and sample selection only. Before any
order, the operator must verify:

- exact composition;
- width and weight;
- color and sample;
- available metres;
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
