# STOCKHURT_REDIRECT_AND_PARTIAL_CATALOG_RECOVERY_V1

## Purpose

Repair the live Stock-Hurt official-catalog lane when an official catalogue redirects within `stockhurt.com`, and preserve usable results when only one catalogue is protected or temporarily unavailable.

## Behavior

- Initial requests remain restricted to `robots.txt`, the two fixed catalogue pages, and selected official product pages.
- Final redirects are accepted only over HTTPS and only on `stockhurt.com` or `www.stockhurt.com`.
- Product requests must still end on an official `/en/product/...` page.
- Every catalogue fetch records `requested_url`, `final_url`, HTTP status, challenge state, and any retrieval error.
- A protected auction catalogue no longer cancels results from the accessible shop catalogue.

## Statuses

- `SUCCESS`: complete usable enrichment without partial-source problems.
- `PARTIAL_SUCCESS_WITH_SOURCE_PROTECTION`: candidates were preserved while another catalogue was challenge-protected.
- `PARTIAL_SUCCESS_WITH_RETRIEVAL_ERRORS`: candidates were preserved while another catalogue failed retrieval.
- `BLOCKED_SOURCE_PROTECTION`: protection prevented all useful catalogue/product enrichment.
- `BLOCKED_RETRIEVAL`: retrieval failures prevented all useful enrichment.
- `VALID_ZERO`: accessible catalogues were processed but contained no qualifying product links.

## Decision boundary

The lane remains read-only. Lot size is descriptive only, incomplete records remain visible, and the human operator retains all contact, bidding, purchase, and payment decisions.
