# PS Auction Public Access Audit v1

**Audit date:** 2026-08-01  
**Market:** Sweden (`SE`)  
**Domain:** `CLOTHING_INVENTORY`  
**Status:** bounded public-source pilot approved

## Public surfaces confirmed

PS Auction exposes public pages without requiring a login for reading:

- auction index: `https://psauction.se/auctions`
- specific item pages: `https://psauction.se/item/view/<numeric-id>/<slug>`

Observed public item pages include clothing lots, complete shop clothing stock,
workwear, shoes, accessories, location, auction deadline, bid basis, VAT/service
fee information, shipping or pickup information, and bankruptcy notices.

This audit does **not** claim that every indexed page is active. The public item
page must be opened and verified before `ACTIVE`, `CONFIRMED_SALE`, analysis, or
Top-5 eligibility is allowed.

## Approved retrieval method

1. Use Brave with Swedish country targeting and explicit
   `site:psauction.se/item/view` queries.
2. Accept only the exact item path shape:
   `/item/view/<numeric-id>/<slug>`.
3. Require clothing evidence in the item title and explicit bulk-inventory
   evidence such as a lot, warehouse stock, assortment, pallet/carton count, or
   an item count of at least ten.
4. Pass accepted URLs through the existing Swedish lightweight public-page
   verifier.
5. When the exact public page returns HTTP 403 or insufficient content, render
   at most three accepted item pages in one shared headless Chromium session.
6. Parse the rendered public HTML through the same bounded verification model.
7. Preserve ended, unavailable, rejected, access-blocked, and unresolved pages
   without manufacturing active opportunities.

## Rejected surfaces

The source gate rejects:

- the PS Auction home page;
- `/auctions` and category/index pages;
- editorial, contact, or generic pages;
- other domains;
- PS Auction item titles without clothing evidence;
- shop fittings and fixtures without clothing inventory;
- individual clothing, shoe, or accessory items without bulk evidence.

## Browser fallback boundary

Chromium is used only after the primary verifier fails closed for one exact,
pre-approved PS Auction item URL. The fallback:

- is limited to three pages per manually initiated run;
- waits at least two seconds between rendered page reads;
- uses no login, account, cookie injection, proxy, CAPTCHA solver, or hidden API;
- does not continue when the rendered response remains blocked;
- records attempted URLs, success/failure, and errors in the run report.

## Safety boundary

The pilot performs no login, account creation, bidding, purchase, contact,
payment, access-control bypass, hidden API use, VAT calculation, customs
calculation, transport estimate, currency conversion, ROI estimate, or automatic
decision.

`PS Auction` remains a **pilot source** until one live GitHub Actions run proves
that the bulk source gate and bounded page verifier produce traceable artifacts.
