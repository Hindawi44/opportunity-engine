# Klaravik Public Access Audit v1

## Decision

Klaravik is suitable for one bounded Sweden Clothing Inventory source pilot.

## Public surface verified

The source exposes public product-auction pages using this shape:

`https://www.klaravik.se/auktion/produkt/<slug>/`

Public pages can expose:

- a specific item title;
- `Objekt-id`;
- active or ended auction wording;
- item-specific `Översikt` text;
- city and Swedish county;
- pickup and freight information;
- explicit bankruptcy context when it belongs to the item;
- clothing and bulk-lot descriptions.

Examples discovered during the audit included:

- a large clothing and footwear lot;
- a second-hand clothing and footwear lot;
- clothing and shop fittings;
- new clothing, shoes and accessories;
- workwear, helmets and footwear.

## Source risks

Klaravik pages contain generic legal wording about bankruptcy sales. That text must
not classify every product as a bankruptcy. Commercial-event classification is
therefore restricted to the item title and item-specific `Översikt` section.

Search indexes can retain ended auctions. The provider globally suppresses an
exact product URL whenever any query result explicitly identifies it as ended or
sold. The public page verifier independently checks the final page again.

## Allowed behavior

- bounded Brave queries restricted to `klaravik.se/auktion/produkt`;
- exact public HTTPS product-page retrieval;
- ordinary redirects that remain on the exact Klaravik product path;
- extraction of public status, object identity, location and item overview;
- fail-closed handling when the page cannot be read or status cannot be proven.

## Prohibited behavior

- login, account creation or session reuse;
- CAPTCHA solving, proxy rotation or access-control bypass;
- seller contact, bidding, purchase or payment;
- hidden/private API discovery;
- VAT, customs, transport, FX, landed-cost, ROI or profitability calculations;
- treating SEK values as NOK fields;
- declaring an auction active from a search snippet alone.

## Acceptance rule

A page can become a confirmed active opportunity only when the exact public page
is readable and provides all of the following:

1. stable specific item identity;
2. explicit active-auction wording;
3. item-scoped clothing evidence;
4. item-scoped bulk-inventory evidence.

Otherwise it remains verification-only, historical, or rejected.
