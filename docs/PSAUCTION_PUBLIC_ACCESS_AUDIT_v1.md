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
3. Require clothing evidence plus lot, inventory, auction, sale, store, or
   bankruptcy evidence in the public search result.
4. Pass accepted URLs through the existing Swedish public-page verifier.
5. Preserve ended, unavailable, rejected, and unverified pages without
   manufacturing active opportunities.

## Rejected surfaces

The source gate rejects:

- the PS Auction home page;
- `/auctions` and category/index pages;
- editorial, contact, or generic pages;
- other domains;
- PS Auction item pages without clothing evidence;
- clothing pages without lot, inventory, sale, auction, store, or bankruptcy
  evidence.

## Safety boundary

The pilot performs no login, account creation, bidding, purchase, contact,
payment, browser automation, hidden API use, VAT calculation, customs
calculation, transport estimate, currency conversion, ROI estimate, or automatic
decision.

`PS Auction` remains a **pilot source** until one live GitHub Actions run proves
that the public source gate and page verifier produce traceable artifacts.
