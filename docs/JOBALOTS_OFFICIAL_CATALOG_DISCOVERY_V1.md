# JOBALOTS_OFFICIAL_CATALOG_DISCOVERY_V1

## Goal

Discover official Jobalots product links without depending on search-engine indexing, then pass at most three links through the existing official product-page enrichment parser.

## Fixed public scope

The collector reads only:

1. `https://jobalots.com/robots.txt`
2. the first official clothing auction catalogue page
3. the first official all-auctions catalogue page
4. at most three `https://jobalots.com/en/products/...` pages

Maximum network requests per run: six.

## Discovery method

The collector extracts product links from normal anchors and embedded HTML/JSON path strings. Links from the clothing-specific catalogue receive priority even when the card text is empty. General-catalogue links are ranked using clothing and commercial-lot terms.

Duplicate product links are collapsed before page retrieval.

## Enrichment

Selected product pages are parsed by `jobalots_page_candidate_from_html`, preserving visible fields such as:

- current bid and currency
- reference retail value and reserve price
- quantity, pallet/box/lot type and weight
- condition, vendor, location and SKU
- auction end text
- manifest availability and manifest links

The final record also identifies the catalogue page that discovered the product and the catalogue-link context used for ranking.

## Safety and authority

- no API key is required
- no login or browser automation
- no contact, bid, reservation, purchase or payment
- no Top 5 or canonical-opportunity promotion
- lot size never causes rejection
- all decisions remain with `HUMAN_OPERATOR`
