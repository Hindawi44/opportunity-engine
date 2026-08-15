# SIGNAL_FOLLOW_UP_SOURCE_VERIFICATION_V1

## Purpose

Bridge persistent follow-up search leads into the exact public item-page verifiers that already exist in the project.

The flow is:

`PERSISTENT FOLLOW-UP LEAD -> EXACT SOURCE ROUTE -> SOURCE-SPECIFIC VERIFIER -> EXPLICIT COMMERCIAL / LOGISTICS FACTS`

V1 supports only URLs that can be proven to be exact public item pages for:

- VENTA (`auction.venta24.de/item/id/...`)
- Auksjonen.no (`ny.auksjonen.no/auksjon/.../<object_id>`)

Generic webpages, catalog pages, company homepages and unsupported domains are not fetched by this bridge. They remain unverified until a source-specific exact verifier exists.

## Facts exposed

When explicitly published on the exact source page, the output can expose:

- title / condition
- quantity
- weight
- dimensions
- pallet count
- pickup / source location
- start or minimum price
- displayed bid
- buy-now price when a supported parser exposes one
- buyer premium
- VAT
- currency
- response hash / source verification provenance

Missing values remain missing. The bridge does not estimate values from images or infer absent shipping data.

## Identity boundary

An exact item page being reachable does not by itself prove that the item belongs to the persistent company case. The bridge separately records whether the persistent entity tokens are present in the exact source-page content.

Therefore these are distinct facts:

1. `source_page_verified`
2. `entity_link_verified`
3. `commercial_facts_confirmed`

None of them automatically promotes the record to a purchasable opportunity.

## Safety boundary

The bridge never:

- logs in;
- bypasses CAPTCHA or access controls;
- contacts a seller;
- bids;
- reserves;
- purchases;
- pays;
- invents a lot URL from a search result;
- promotes a search hit automatically.

The human operator remains the decision owner.

## Daily checkpoint integration

The existing post-bulletin hook now executes:

1. unified market intelligence river;
2. cross-run signal follow-up continuity;
3. bounded exact source verification.

The new artifact is:

`signal-follow-up-source-verification.json`

A compact verification summary is also attached to the domain market intelligence brief.
