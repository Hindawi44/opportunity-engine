# PS Auction Public Access Audit v2

**Audit date:** 2026-09-08
**Market:** Sweden (`SE`)  
**Domain:** `CLOTHING_INVENTORY`  
**Status:** bounded public-source pilot approved

## Public surfaces confirmed

PS Auction exposes public pages without requiring a login for reading:

- bankruptcy auction index: `https://psauction.se/auctions?bankruptcy=1`
- current auction pages: `https://psauction.se/auction/<numeric-id>/<slug>`
- legacy item pages: `https://psauction.se/item/view/<numeric-id>/<slug>`

Observed public auction and item pages include clothing lots, complete shop
clothing stock, workwear, shoes, accessories, location, auction deadline, bid
basis, VAT/service fee information, shipping or pickup information, and
bankruptcy notices.

This audit does **not** claim that every indexed page is active. The public item
page must be opened and verified before `ACTIVE`, `CONFIRMED_SALE`, analysis, or
Top-5 eligibility is allowed.

## Approved retrieval method

1. Read the approved public bankruptcy index once and extract only exact
   `/auction/<numeric-id>/<slug>` links.
2. If the lightweight request receives PS Auction's HTTP 202 AWS WAF challenge,
   render that same approved index once with the system Chromium available on
   the runner; fail closed when rendering is unavailable or still insufficient.
3. Keep two current-auction Brave queries on `site:psauction.se/auction` and the
   existing exact-lot fallback queries on `site:psauction.se/item/view`.
4. Accept the current auction route and legacy exact item route for discovery;
   recognize `/auction/ended/<numeric-id>/<slug>` only as ended-state evidence.
5. Require clothing evidence in the current auction card or legacy item title,
   plus explicit bulk evidence such as a lot, stock, assortment, pallet/carton
   count, or at least ten items/auction objects.
6. Pass accepted URLs through the existing Swedish lightweight public-page
   verifier.
7. When the exact public page returns HTTP 403 or insufficient content, render
   at most six accepted listing pages in one shared headless Chromium session.
8. Parse the rendered public HTML through the same bounded verification model.
9. Preserve ended, unavailable, rejected, access-blocked, and unresolved pages
   without manufacturing active opportunities.

## Rejected surfaces

The source gate rejects:

- the PS Auction home page;
- unapproved `/auctions` and category/index pages;
- editorial, contact, or generic pages;
- other domains;
- listing evidence without clothing inventory;
- shop fittings and fixtures without clothing inventory;
- individual clothing, shoe, or accessory items without bulk evidence.

## Browser fallback boundary

Chromium is used only after the primary verifier fails closed for one exact,
pre-approved PS Auction listing URL. The fallback:

- is limited to six pages per manually initiated run;
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
