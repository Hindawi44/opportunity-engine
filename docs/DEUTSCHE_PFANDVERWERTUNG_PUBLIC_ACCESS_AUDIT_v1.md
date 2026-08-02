# Deutsche Pfandverwertung public-access audit v1

## Decision

`GO_FOR_BOUNDED_INDEX_AND_ITEM_ADAPTER`

Deutsche Pfandverwertung exposes a public catalog overview, public catalog
links and public item detail pages without login. The source is relevant to the
Clothing Inventory domain because historical public auctions include explicit
commercial clothing inventories and multi-unit lots. The source must remain
`PLANNED` until a current active clothing catalog is observed and the complete
active catalog, exact item verification, unified report and SQLite persistence
pipeline is validated live.

## Audit date and current public evidence

Audit date: `2026-08-02`.

Public pages reviewed:

```text
https://deutsche-pfandverwertung.de/versteigerungen/
https://www.versteigerungen-deutsche-pfandverwertung.de/
https://www.versteigerungen-deutsche-pfandverwertung.de/blocks_overview.php
```

Observed behavior:

- the editorial auction page and the online catalog overview were publicly
  readable without login;
- the online overview exposed public catalog links and catalog item counts;
- nine ended catalog cards were visible during the audit;
- no active catalog remained on the public online overview on the audit date;
- public item pages exposed title, lot number, description, source-native EUR
  amount, bid count, lifecycle wording and approximate location;
- login or registration is required to participate in online bidding;
- bidding, registration and any authenticated behavior are outside project
  scope.

A zero-current-result run is therefore a valid outcome and must not be treated
as a collector failure.

## Historical clothing evidence

The source has strong historical evidence that it can publish relevant clothing
inventory opportunities.

### Shoe-store inventory

The editorial auction page published a landlord-lien auction for approximately
`3,741 pairs of shoes`, plus scarves, bags, socks, shoe-care products and store
fixtures. This proves that the source can expose complete retail clothing or
footwear inventory rather than only unrelated industrial assets.

Public editorial page:

```text
https://deutsche-pfandverwertung.de/versteigerungen/oeffentliche-versteigerung-aufgrund-%C2%A7-562-bgb-vermieterpfandrecht-konvolut-schuhe-mobiliar/
```

### Outdoor apparel bulk lot

A public ended item page with object ID `2175` described one commercial outdoor
lot containing, among many other products, `7,440 packs of functional
underwear`. The item page also exposed explicit bulk wording, quantities, an
ended lifecycle, 68 bids and a displayed sale price of EUR 80,000.

Stable item identity:

```text
dpv-object:2175
```

Public item URL:

```text
https://www.versteigerungen-deutsche-pfandverwertung.de/00-live-versteigerungen/1-konvolut-outdoor-artikel-neuware-der-marken-black-snake-und-noorsk-aufgrund-pfandrecht-des-lagerhalters--id-2175-item.html
```

The historical evidence is suitable for parser and lifecycle regression tests.
It is not a current buying opportunity and must never enter current Top 5.

## Public URL contract

Accepted online-auction hosts:

```text
www.versteigerungen-deutsche-pfandverwertung.de
versteigerungen-deutsche-pfandverwertung.de
```

Canonical catalog index:

```text
https://www.versteigerungen-deutsche-pfandverwertung.de/blocks_overview.php
```

Catalog URLs use a public numeric catalog block ID:

```text
/<slug>--search-1-block-<catalog-block-id>-browse.html
/<slug>--search-1-search_closed-y-block-<catalog-block-id>-browse.html
```

Public item pages use a numeric object ID:

```text
/<section>/<item-slug>--id-<object-id>-item.html
```

Query parameters and fragments are not identity.

## Identity contract

The public numeric catalog block ID is used for one auction-event identity:

```text
dpv-auction:<catalog-block-id>
```

The final numeric object ID from an item URL is used for exact item identity:

```text
dpv-object:<object-id>
```

Displayed lot numbers are catalog-scoped and must not be used as global item
identities.

## Clothing and bulk evidence

Positive clothing evidence must be explicit in a bounded auction or item
context. Examples include:

- `Bekleidung` or `Kleidung`;
- `Textilien`;
- `Schuhe`;
- `Unterwäsche`;
- jackets, trousers, coats, scarves, bags, socks or gloves;
- explicit `Modewaren` inventory.

Commercial bulk evidence may include:

- `Konvolut` or `Großkonvolut`;
- `Sachgesamtheit`;
- `Große Posten`;
- `Warenbestand`;
- pallet quantities;
- documented multi-unit quantities such as pairs, pieces or packs.

Brand rights, domains, company shares or a fashion-company name are not
physical clothing inventory.

## Aggregation policy

The future active adapter must use:

```text
AUCTION_EVENT_WITH_CHILD_LOTS
```

It must retain at most one parent opportunity per verified clothing auction,
retain ordinary garments as child evidence, and promote only explicit
commercial bulk lots after exact item-page verification. Ordinary single
items must never flood the report or Top 5.

## Lifecycle mapping

Conservative mapping:

- current catalog text containing `LIVE`, `Beginn`, or
  `Versteigerung startet am` -> `ACTIVE` when no ended marker is present;
- catalog URLs containing `search_closed-y`, overview cards stating
  `Versteigerung beendet`, or item pages stating `Los ist verkauft` -> `ENDED`;
- withdrawn or cancelled lots -> `ENDED` and ineligible;
- ambiguous pages -> `UNKNOWN` or `REQUIRES_VERIFICATION`.

Ended historical pages may be retained as market evidence only.

## Price semantics

The first adapter preserves source-native EUR observations only:

- an active `Startpreis` is not a final sale price;
- an ended `Verkaufspreis` may be retained as historical evidence only when the
  exact item page explicitly states sold or ended semantics;
- bid count and lifecycle remain separate fields;
- the published buyer premium is tiered and may change by auction;
- VAT is applied to the premium under the source terms;
- no EUR-to-NOK conversion, premium calculation, VAT calculation, customs,
  logistics, profit or ROI calculation is permitted in the initial adapter.

## Access and operational limits

- public HTTPS pages only;
- strict accepted-host validation;
- bounded response size and timeout;
- no login, registration, watch list, bidding, seller contact, purchase or
  payment;
- no hidden API discovery or use;
- no CAPTCHA solving, proxying, browser-fingerprint bypass or TLS bypass;
- stop and classify the source as blocked if public access starts requiring
  authentication or anti-automation circumvention.

## Activation requirements

Deutsche Pfandverwertung remains `PLANNED` until a dedicated follow-up proves:

1. a live public index run can identify a current clothing auction from explicit
   inventory evidence;
2. complete catalog pagination is resolved when a catalog contains multiple
   pages;
3. exact item parsing resolves object IDs and catalog-scoped lot numbers;
4. ordinary single garments remain child evidence;
5. explicit commercial bulk clothing lots are verified on exact item pages;
6. ACTIVE, ENDED, sold, withdrawn and cancelled lifecycle mappings are tested;
7. EUR source observations never enter NOK fields;
8. unified JSON and SQLite persistence work for positive and zero-result runs;
9. a bounded live workflow succeeds without login or access-control bypass;
10. no automatic bidding, purchase or financial action is introduced.
