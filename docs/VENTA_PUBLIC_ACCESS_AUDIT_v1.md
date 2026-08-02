# VENTA Germany public-access audit v1

## Decision

`GO_FOR_BOUNDED_INDEX_AND_CATALOG_ADAPTER`

VENTA Industrieversteigerungen exposes a public auction index, public catalog
pages and public item pages without login. The source is suitable for a bounded
Germany Clothing Inventory adapter, but it must remain `PLANNED` until a live
catalog with explicit clothing inventory is observed and the complete catalog
and item pipeline is validated.

## Audit date and public evidence

Audit date: `2026-08-02`.

Observed public behavior:

- the public index was readable at `https://auction.venta24.de/`;
- five current catalog cards were visible during the audit;
- none of the current cards contained explicit clothing-inventory evidence;
- the public category browser showed `Textil (0)` during the audit;
- catalog pages exposed auction metadata, pagination, public lot links, EUR
  amounts and bid counts without login;
- the site published an auctioneer fee of `18%` plus statutory VAT;
- the site stated that bidding participation is restricted to commercial
  bidders; login and bidding are outside project scope.

## Important false-positive evidence

A closed catalog was titled:

```text
Insolvenz-Versteigerung der Multiply Apparel GmbH, Dortmund
```

The public catalog contained only one lot:

```text
Porsche 911 Targa 4 GTS, Cabriolet, Hybrid Benzin/Elektro
```

The catalog number was `5214` and the public catalog reported one object. This
proves that a company name containing `Apparel`, `Mode`, `Textil` or a similar
business term is not sufficient clothing evidence. The adapter must require an
explicit inventory summary, catalog description or clothing lot evidence.

## Public URL contract

Accepted host:

```text
auction.venta24.de
```

Auction indexes:

```text
https://auction.venta24.de/
https://auction.venta24.de/index.html
```

Active auction catalog pages:

```text
/browse/search/1/block/<catalog-slug>_<catalog-block-id>.html
```

Closed auction catalog pages:

```text
/browse/search/1/block/<catalog-slug>_<catalog-block-id>/search_closed/y.html
```

Public item pages:

```text
/item/id/<auction-number>_<lot-number>_<item-slug>_<object-id>.html
```

Query parameters used for sorting or navigation are not part of canonical
identity.

## Identity contract

The numeric value at the end of the catalog URL is a public catalog-block ID. It
is useful for index deduplication but is provisional:

```text
venta-catalog-block:<catalog-block-id>
```

The stable auction identity must use `Auktion Nr.` from the exact catalog page:

```text
venta-auction:<auction-number>
```

The stable item identity must use the final numeric object ID from the item URL:

```text
venta-object:<object-id>
```

The displayed lot number is auction-scoped and is not globally unique.

## Clothing filter contract

Positive evidence may include explicit wording such as:

- `Bekleidung`;
- `Kleidung`;
- `Textilien` or `Textilwaren`;
- `Modewaren`;
- `Konfektion`;
- `Schuhe`;
- `Lederbekleidung`;
- `Boutique` when accompanied by sale inventory context.

Required behavior:

- do not treat the company name as inventory evidence;
- do not select a catalog because its title contains `Apparel`, `Mode` or
  `Textil` alone;
- require explicit clothing wording in the inventory summary, catalog
  description or lot titles;
- keep zero selected clothing auctions as a valid run result;
- verify the exact catalog before creating an opportunity candidate.

## Aggregation policy

The future adapter must use:

```text
AUCTION_EVENT_WITH_CHILD_LOTS
```

It must create at most one parent candidate for a verified clothing auction,
retain ordinary garments as child evidence, and promote only explicit
commercial bulk lots such as `Posten`, `Konvolut`, multi-unit stock or lots with
a documented quantity. Ordinary single garments must never flood the report or
Top 5.

## Lifecycle mapping

Conservative mapping:

- current index cards with a public future start/end context -> `ACTIVE`;
- catalog pages containing `Erster Artikel endet` or
  `Auslauf der Versteigerung` -> `ACTIVE` when the timing is current;
- cards under `Vergangene Auktionen`, URLs containing `search_closed/y`, or
  pages stating `Auktion beendet` -> `ENDED`;
- ambiguous pages -> `UNKNOWN` or `REQUIRES_VERIFICATION`.

## Price semantics

The first adapter must preserve source-native EUR observations only:

- a displayed active amount is not a confirmed final sale price;
- bid count and item lifecycle must be preserved separately;
- ended values require explicit sale semantics before becoming historical final
  prices;
- the published `18%` fee and statutory VAT are terms, not automatically
  calculated totals;
- no EUR-to-NOK conversion, VAT calculation, customs, logistics, profit or ROI
  calculation is allowed in the first adapter.

## Access and operational limits

- public HTTPS pages only;
- no login, registration, watch-list, bidding, contact, purchase or payment;
- no hidden API discovery or use;
- no CAPTCHA solving, proxying, browser-fingerprint bypass or TLS bypass;
- bounded pagination and response-size limits;
- stop and classify the source as blocked if public access begins requiring
  authentication or anti-automation circumvention.

## Activation requirements

VENTA remains `PLANNED` until a dedicated follow-up PR proves:

1. a live index run can select an auction only from explicit clothing inventory
   evidence;
2. the `Multiply Apparel` catalog remains rejected as a company-name false
   positive;
3. exact catalog parsing resolves `Auktion Nr.` and complete pagination;
4. exact item parsing resolves object IDs and auction-scoped lot numbers;
5. ordinary single garments remain child evidence;
6. explicit bulk clothing lots can become item candidates;
7. ACTIVE and ENDED mappings are fixture-tested and live-validated;
8. EUR observations never enter NOK fields;
9. SQLite and unified-report persistence work for both positive and zero-result
   runs;
10. no login, bidding, purchase or financial action is introduced.
