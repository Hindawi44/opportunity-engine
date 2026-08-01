# Riegermann Germany public-access audit v1

## Decision

`GO_FOR_BOUNDED_EVENT_ADAPTER`

Riegermann is suitable for a bounded Germany Clothing Inventory event adapter.
Public pages expose auction-level and item-level evidence without login. The
source must remain `PLANNED` until the adapter is implemented and validated.

The adapter must model one clothing liquidation auction as one parent market
event with child lots. It must not promote hundreds of ordinary single-garment
lots into independent opportunities or Top 5 records.

## Audit date and live evidence

Audit date: `2026-08-01`.

A current public auction was observed:

- auction: `Versteigerung Cabrini GmbH`;
- public auction ID: `908`;
- status: `Aktuell | Terminauktion` with public `Jetzt bieten` / `online` wording;
- location: `DE-55450 Langenlonsheim, An den Nahewiesen 12 + 13`;
- bidding opened: `2026-06-26 10:00`;
- awards begin: `2026-08-03 10:00`;
- clothing scope: women's leather jackets, women's leather coats, men's leather
  jackets, leather blazers and leather trousers;
- published buyer premium: `20%`;
- published VAT: `19%`;
- published pickup window: `2026-08-10 10:00-11:00`.

A public item example was also observed:

- object ID: `73457`;
- lot number: `410`;
- title: `Damen Lederjacke Größe 36`;
- manufacturer: `Cabrini`;
- material: `100 % Lamm Nappaleder`;
- color: `Schwarz`;
- category: `Vorräte / Waren`;
- minimum/start price: `1 EUR`;
- item end time: `2026-08-03 10:00`.

Reading these pages did not require authentication. Registration or login is
required for watch-list and bidding actions, which are outside project scope.

## Public URL contract

Accepted hosts:

```text
riegermann.de
www.riegermann.de
```

Auction indexes:

```text
https://www.riegermann.de/de/Auktionen/alle
https://www.riegermann.de/de/Auktionen/Auktionen
```

Auction information pages:

```text
/de/<auction-slug>/a/<auction-id>
```

Observed example:

```text
/de/2019_versteigerung_cabrini_gmbh/a/908
```

Auction catalog pages:

```text
/de/objekte/au-<auction-id>/<auction-slug>
```

Observed example:

```text
/de/objekte/au-908/versteigerung_cabrini_gmbh?Lstatus=1
```

Item detail pages:

```text
/de/l/<object-id>/<item-slug>
```

Observed example:

```text
/de/l/73457/damen_lederjacke_groesse_36
```

Query parameters used for sorting, pagination and return position must not be
part of canonical identity.

## Identity and deduplication contract

Auction identity:

```text
riegermann-auction:<auction-id>
```

Item identity:

```text
riegermann-object:<object-id>
```

The displayed lot number is auction-scoped and must not be treated as globally
unique. Item deduplication requires the numeric object ID from the `/de/l/`
path. Auction grouping requires the numeric auction ID from `/a/` or `/au-`.

## Aggregation policy

Riegermann frequently publishes large liquidation events as many individual
lots. For clothing inventory, the bounded adapter must use:

```text
AUCTION_EVENT_WITH_CHILD_LOTS
```

Required behavior:

- create one parent candidate for a verified clothing auction event;
- retain individual lots as child evidence and price/activity observations;
- do not promote an ordinary single jacket, coat, blazer or trouser lot to Top 5;
- allow an item-level opportunity only when the item is explicitly a commercial
  bulk lot, for example `Posten`, `Konvolut`, multiple units or a documented
  quantity;
- aggregate counts by auction ID before reporting inventory scale;
- prevent one auction with hundreds of garments from flooding the candidate
  report.

## Public auction fields observed

Auction pages can publicly expose:

- auction ID and title;
- status and auction type;
- location;
- bidding start time;
- award start and end time;
- pickup window;
- auction description and inventory categories;
- buyer premium;
- VAT wording;
- links to catalog, information and result pages.

## Public item fields observed

Catalog and detail pages can publicly expose:

- numeric object ID;
- auction-scoped lot number;
- item title;
- manufacturer, material, color, size and condition notes;
- category;
- minimum or start price in EUR;
- displayed current amount;
- bid count;
- end timestamp;
- explicit sold / not sold markers on ended records.

## Lifecycle mapping

Conservative mapping:

- `Vorschau` -> `UPCOMING`;
- `Aktuell`, `Jetzt bieten` or `online` -> `ACTIVE` only when the auction or item
  page itself contains the current status and a future end time;
- `Nachverkauf` -> `REQUIRES_VERIFICATION`, because availability and purchase
  terms must be confirmed at item level;
- `Abgeschlossen` or `Auktion beendet` -> `ENDED`;
- result pages may be retained as historical evidence only when identity and
  sold/price semantics are explicit.

## Price semantics

The adapter must preserve source-native EUR values and their meaning:

- `Startpreis` is a starting price, not a confirmed sale price;
- `Mindestpreis` is a minimum/reserve basis, not a confirmed sale price;
- an active displayed amount is a bid observation only when the bid count is
  also present;
- an ended value becomes a historical final price only when the page explicitly
  marks the lot as sold (`Verkauft`) and publishes `Preis`;
- `nicht verkauft` must never be treated as a zero price;
- the published `20%` premium and `19%` VAT are terms, not automatically computed
  total costs;
- no EUR-to-NOK conversion, VAT calculation, customs, logistics, profit or ROI
  calculation is allowed in the first adapter.

## False-positive and noise controls

Reject or retain only as non-opportunity evidence:

- generic auction index pages without a bounded auction card;
- category pages mixing unrelated auctions;
- ordinary retail product pages;
- articles or insolvency notices without a public sale event;
- single garment lots without bulk evidence when considered independently;
- closed lots presented without explicit sold/not-sold semantics;
- catalog links whose auction context cannot be resolved to a numeric auction ID.

## Access and operational limits

- public HTTPS pages only;
- no login, registration, watch-list interaction, bidding, contacting, purchase
  or payment;
- no hidden API discovery or use;
- no CAPTCHA solving, proxying, browser fingerprint bypass or TLS bypass;
- respect bounded pagination and request delays in any future live pilot;
- stop and classify the source as blocked if public access requires authentication
  or anti-automation circumvention;
- keep the source `PLANNED` until the dedicated adapter and fixtures pass.

## Adapter acceptance criteria

Before changing Riegermann from `PLANNED`, a dedicated PR must prove:

1. auction index parsing produces stable auction IDs and exact information URLs;
2. catalog parsing stays within one resolved auction context;
3. item parsing produces stable object IDs and preserves lot numbers separately;
4. Cabrini-style single garments remain child evidence and never flood Top 5;
5. explicit `Posten` or quantity-bearing clothing lots can become item-level
   candidates;
6. ACTIVE, UPCOMING, REQUIRES_VERIFICATION and ENDED mappings are fixture-tested;
7. EUR values never enter NOK fields;
8. start/minimum prices never become confirmed sale prices;
9. ended sold and not-sold outcomes are distinguished;
10. zero accepted opportunities remains a valid run result.
