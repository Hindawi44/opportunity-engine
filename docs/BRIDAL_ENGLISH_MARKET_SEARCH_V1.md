# BRIDAL_ENGLISH_MARKET_SEARCH_V1

## Product purpose

Add an English-language search lane to the existing bridal-liquidation tributary without adding a new country or rebuilding the engine.

The original local-language searches remain active in:

- Norway
- Sweden
- Germany

The companion lane executes one English query for each same market so international wholesalers, cross-border liquidation pages, and English-language business notices can enter the existing market-intelligence flow.

## Query coverage

Each market now has two bounded search lanes:

1. Local market language
2. English market language

The English queries cover phrases such as:

- bridal shop liquidation
- bridal boutique closing down
- wedding dress stock clearance
- bridal inventory lot
- sample wedding dresses

Each query also includes the target country name so the search remains geographically bounded.

## Daily limits

- 3 existing markets only
- 1 local query per market
- 1 English query per market
- 6 Brave requests maximum per run
- 8 results requested per query by default
- one-year freshness window
- existing `BRAVE_SEARCH_API_KEY`
- no new provider or secret

## Commercial acceptance gate

An English result is accepted only when the title or snippet contains all three groups:

1. A bridal or wedding-dress term
2. A commercial store, inventory, stock, collection, batch, or lot term
3. A closure, insolvency, liquidation, surplus, clearance, or auction term

A private person selling one wedding dress remains rejected.

## Identity and deduplication

Local and English lanes use the same stable signal identity:

`market + canonical URL`

The same page found through both languages remains one durable market signal. Different pages remain separate signals.

## Existing downstream flow

Accepted English signals use the existing `MarketSignalRecord` contract and enter:

- country market-signal artifacts
- SQLite persistence
- cross-run continuity
- daily market-intelligence bulletin
- OpenAI hunt-case grouping
- targeted Brave follow-up
- human verification workflow

## Safety boundary

Every accepted link remains an unverified early signal.

The English lane cannot:

- promote a result directly to an opportunity
- make it Top 5 or analysis eligible
- contact a seller
- bid
- reserve
- purchase
- pay

Source-page verification remains mandatory.
