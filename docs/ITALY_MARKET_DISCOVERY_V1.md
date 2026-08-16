# ITALY_MARKET_DISCOVERY_V1

## Scope of this step

This is step 1 of turning Italy into a real core opportunity market. It builds a
bounded national discovery radar only. It does **not** yet add Italy to the daily
NO/SE/DE operator checkpoint, persistence/follow-up memory, exact source-page
verification, logistics, or Top-5 opportunity ranking.

Keeping this boundary is intentional: first prove that the Italian radar can
retrieve useful and diversified signals, then connect the successful output to
the existing lifecycle one layer at a time.

## National query pack

The first bounded pack has seven Italian intents:

1. official judicial sales on `pvp.giustizia.it`;
2. fashion insolvency / judicial liquidation;
3. shop closure / total clearance;
4. clothing stocklots / warehouse remainders / end-of-line stock;
5. auction and bankruptcy-sale lots;
6. bridal atelier / wedding-dress sample-stock liquidation;
7. warehouse clearance / unsold clothing stock.

Default budget: 7 requests, up to 10 search results per request. The provider is
restricted to country `IT` and uses the existing Brave Search secret.

## Official source foundation

The first official source is the Italian Ministry of Justice **Portale delle
Vendite Pubbliche (PVP)**. The public portal exposes judicial/public sale notices
and has movable-goods and company categories. Its public advanced-search taxonomy
includes `Abbigliamento E Calzature`, so it is a strong exact-source candidate for
later lot verification.

The official PVP query is domain-locked: a result from another host cannot pass
as an official-source signal merely because Brave returned it for the query.

## Acceptance gate

A search result must include:

- clothing/fashion or bridal context; and
- a commercial event such as insolvency, closure, warehouse surplus, stocklot,
  liquidation, or auction.

Ordinary retail collection pages are rejected.

All accepted rows remain `MarketSignalRecord` objects with:

- `source_country: IT`;
- `status: WATCH`;
- explicit query intent;
- canonical source URL;
- source scope (`OFFICIAL_JUDICIAL_SALES` or `PUBLIC_WEB_DISCOVERY`);
- `source_page_verification_required: true`;
- no opportunity promotion.

## Safety boundary

This step never:

- contacts a seller or company;
- bids;
- reserves;
- buys;
- pays;
- promotes a search hit into an opportunity;
- marks a hit Top-5 eligible.

## Output

Standalone runner:

`python scripts/build_italy_market_discovery.py`

Default artifact:

`artifacts/italy-market-discovery.json`

The report exposes per-query statistics, accepted/rejected/duplicate counts,
independent-domain count, intent counts, and all unverified signals.

## Gate before step 2

Step 2 should happen only after tests are green and one live run is inspected.
The live run should answer:

- Did all seven intents execute?
- How many signals were accepted?
- How many independent domains appeared?
- Did PVP produce usable clothing/footwear lots or pages?
- Did bridal discovery produce real commercial signals rather than private single
  dresses?
- Which intents are noisy or weak?

Only then should Italy be wired into durable entity memory and cross-day
follow-up.
